
import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات CoinGecko ----------------
SCAN_LIMIT = 50  # سنفحص أفضل 50 عملة عالمياً
# --------------------------------------------------

app = Flask(__name__)
# 👇 هذه الإشارة ستظهر لك فوراً لتتأكد أن التطبيق متصل
signals_history = [
    {
        "symbol": "APP-CONNECTED",
        "price": 100.0, "tp1": 102.0, "tp2": 105.0, "sl": 98.0, 
        "vol": 99.9, 
        "time": "NOW"
    }
]

@app.route('/')
def home():
    return "✅ SomaScanner (Gecko Edition) is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def get_coingecko_data():
    # جلب البيانات من السوق العالمي
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc", 
        "per_page": SCAN_LIMIT,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h"
    }
    
    try:
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
                print(f"🔍 Scanned {len(coins)} coins globally...")
                
                for coin in coins:
                    symbol = coin['symbol'].upper()
                    current_price = coin['current_price']
                    
                    # نأخذ نسبة التغير في آخر ساعة
                    price_change_1h = coin.get('price_change_percentage_1h_in_currency')
                    if price_change_1h is None: price_change_1h = 0.0
                    
                    # الشرط: أي ارتفاع إيجابي (ولو بسيط) سنعرضه للتجربة
                    is_pump = float(price_change_1h) > 0.5 
                    
                    if is_pump:
                        signal_data = {
                            "symbol": f"{symbol}",
                            "price": current_price,
                            "tp1": current_price * 1.02,
                            "tp2": current_price * 1.05,
                            "sl": current_price * 0.98,
                            "vol": round(float(price_change_1h), 1), # نعرض نسبة الارتفاع
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # إضافة للقائمة ومنع التكرار
                        exists = any(d['symbol'] == signal_data['symbol'] for d in signals_history)
                        if not exists:
                            signals_history.insert(0, signal_data)
                            # حذف إشارة الاختبار القديمة
                            if len(signals_history) > 0 and signals_history[-1]['symbol'] == "APP-CONNECTED":
                                signals_history.pop()
                            if len(signals_history) > 30: signals_history.pop()
                            print(f"🚀 Signal Found: {symbol}")
            
            time.sleep(45) # كوين جيكو يحتاج راحة أطول قليلاً
            
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
