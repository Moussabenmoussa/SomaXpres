import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات CoinGecko ----------------
# لا نحتاج لتوكن أو مفاتيح، هو مجاني ومفتوح
SCAN_LIMIT = 50  # سنفحص أفضل 50 عملة
# --------------------------------------------------

app = Flask(__name__)
signals_history = []

# إضافة إشارة ترحيبية لتتأكد أن التطبيق يعمل
start_signal = {
    "symbol": "APP-READY",
    "price": 1.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 100, 
    "time": "NOW"
}
signals_history.append(start_signal)

@app.route('/')
def home():
    return "✅ SomaScanner (Gecko Edition) is Running!"

@app.route('/api/signals')
def get_signals():
    # ترتيب الإشارات لتظهر الأحدث أولاً
    return jsonify(signals_history)

def get_coingecko_data():
    # رابط يجلب أفضل العملات مع بيانات السعر والتغير
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc", # ترتيب حسب الفوليوم
        "per_page": SCAN_LIMIT,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h" # نحتاج تغير آخر ساعة
    }
    
    try:
        # إضافة User-Agent مهم جداً
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"⚠️ Gecko Error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return []

def run_scanner():
    print("🦎 SomaScanner Gecko Edition Started...")
    
    while True:
        try:
            coins = get_coingecko_data()
            
            if coins:
                print(f"🔍 Scanned {len(coins)} coins...")
                
                for coin in coins:
                    symbol = coin['symbol'].upper()
                    current_price = coin['current_price']
                    
                    # الانتباه: كوين جيكو يعطي نسبة التغير كـ null أحياناً
                    price_change_1h = coin.get('price_change_percentage_1h_in_currency')
                    if price_change_1h is None: price_change_1h = 0.0
                    
                    # الشروط: ارتفاع أكثر من 1% في آخر ساعة (Pump)
                    # يمكنك تعديل الرقم 1.0 لجعله أصعب أو أسهل
                    is_pump = float(price_change_1h) > 1.0 
                    
                    if is_pump:
                        # صناعة التوصية
                        signal_data = {
                            "symbol": f"{symbol}/USD",
                            "price": current_price,
                            "tp1": current_price * 1.02, # هدف 2%
                            "tp2": current_price * 1.05, # هدف 5%
                            "sl": current_price * 0.98,  # وقف 2%
                            "vol": round(float(price_change_1h), 1), # سنعرض نسبة الارتفاع مكان الفوليوم
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # إضافة للقائمة ومنع التكرار
                        exists = any(d['symbol'] == signal_data['symbol'] for d in signals_history)
                        if not exists:
                            signals_history.insert(0, signal_data)
                            # نحذف إشارة الترحيب إذا وجدنا إشارات حقيقية
                            if signals_history[-1]['symbol'] == "APP-READY":
                                signals_history.pop()
                            if len(signals_history) > 30: signals_history.pop()
                            print(f"🚀 Signal: {symbol} (+{price_change_1h}%)")
            
            # كوين جيكو يطلب الانتظار قليلاً (Rate Limit)
            time.sleep(30) 
            
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

# تشغيل الخيط
t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
