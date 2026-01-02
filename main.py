
import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات القنص (Sniper Settings) ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"

SCAN_LIMIT = 50       # فحص أعلى 50 عملة سيولة
PUMP_THRESHOLD = 2.0  # ⚠️ رفعنا الشرط: يجب أن ترتفع 2% في ساعة واحدة
# -----------------------------------------------------------------

# 🚫 قائمة التجاهل (عملات مستقرة لا فائدة من تداولها)
IGNORED_COINS = ['USDT', 'USDC', 'FDUSD', 'DAI', 'WBTC', 'WETH', 'STETH', 'TUSD']

app = Flask(__name__)
signals_history = []

# إشارة النظام (للتأكد من العمل فقط)
signals_history.append({
    "symbol": "SYSTEM-READY",
    "price": 0.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 100, "time": "NOW"
})

@app.route('/')
def home():
    return "✅ SomaScanner Sniper V2 is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_coingecko_data():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc", 
        "per_page": SCAN_LIMIT,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h" # نطلب بيانات 24 ساعة أيضاً للفلترة
    }
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200: return resp.json()
        return []
    except: return []

def run_scanner():
    print("🚀 Sniper V2 Started...")
    send_telegram_alert("🦅 **تم تفعيل وضع القنص V2!**\n- تم تفعيل فلتر العملات المستقرة.\n- الحد الأدنى للدخول: 2% ارتفاع.\n- فلتر توافق الترند يعمل.")
    
    while True:
        try:
            coins = get_coingecko_data()
            if coins:
                print(f"🔍 Filtering {len(coins)} coins...")
                
                for coin in coins:
                    symbol = coin['symbol'].upper()
                    
                    # 1. فلتر العملات المستقرة
                    if symbol in IGNORED_COINS: continue
                    
                    current_price = coin['current_price']
                    
                    # بيانات التغير
                    change_1h = coin.get('price_change_percentage_1h_in_currency')
                    change_24h = coin.get('price_change_percentage_24h')
                    
                    if change_1h is None: change_1h = 0.0
                    if change_24h is None: change_24h = 0.0
                    
                    change_1h = float(change_1h)
                    change_24h = float(change_24h)
                    
                    # 🔥 شروط القنص الصارمة 🔥
                    # 1. ارتفاع قوي في آخر ساعة (أكثر من 2%)
                    is_pump = change_1h >= PUMP_THRESHOLD
                    
                    # 2. الترند العام ليس هابطاً (لتجنب "مسك السكين الساقطة")
                    is_uptrend = change_24h > 0
                    
                    if is_pump and is_uptrend:
                        # حساب الأهداف
                        tp1 = current_price * 1.03 # طمع قليل 3%
                        tp2 = current_price * 1.07 # طمع متوسط 7%
                        sl = current_price * 0.97  # وقف خسارة 3%
                        
                        signal_data = {
                            "symbol": symbol,
                            "price": current_price,
                            "tp1": tp1, "tp2": tp2, "sl": sl,
                            "vol": round(change_1h, 1), # نعرض قوة البمب
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # منع التكرار
                        exists = any(d['symbol'] == symbol for d in signals_history)
                        
                        if not exists:
                            # تحديث التطبيق
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 20: signals_history.pop()
                            
                            # تنظيف رسالة النظام
                            if len(signals_history) > 1 and signals_history[-1]['symbol'] == "SYSTEM-READY":
                                signals_history.pop()

                            # إرسال تيليجرام
                            msg = f"""
🦅 **SomaSniper Signal**
💎 العملة: #{symbol}
🔥 الزخم: +{change_1h:.1f}% (1h)
📊 الترند اليومي: +{change_24h:.1f}% (24h)
💰 السعر: {current_price}$

🎯 **أهداف:** {tp1:.4f} - {tp2:.4f}
🛡️ **وقف:** {sl:.4f}
                            """
                            send_telegram_alert(msg)
                            print(f"🎯 Sniper Hit: {symbol}")
            
            time.sleep(60) # فحص كل دقيقة (لإعطاء السوق وقتاً للتحرك)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
