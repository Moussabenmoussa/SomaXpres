import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات البوت ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"
# سنفحص 10 عملات فقط للتجربة السريعة
SCAN_LIMIT = 10
TIMEFRAME = "5m"
# سنقبل أي فوليوم لكشف الاتصال
VOLUME_MULTIPLIER = 0.0
# -----------------------------------------------

app = Flask(__name__)
signals_history = []

@app.route('/')
def home():
    return "✅ SomaScanner API is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def get_top_gainers():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        # إضافة User-Agent لنتظاهر بأننا متصفح ولسنا روبوت
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        # 👇👇 كشف الخطأ 👇👇
        if resp.status_code != 200:
            print(f"❌ خطأ باينانس: {resp.status_code}")
            return ["ERROR-BINANCE"] # نرسل رمز خطأ
            
        data = resp.json()
        usdt_pairs = []
        for item in data:
            symbol = item['symbol']
            if symbol.endswith("USDT") and "UP" not in symbol and "DOWN" not in symbol:
                usdt_pairs.append(item)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
        return [x['symbol'] for x in sorted_pairs[:SCAN_LIMIT]]
    except Exception as e:
        print(f"❌ خطأ اتصال: {e}")
        return ["ERROR-NET"]

def get_market_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=21"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200: return resp.json()
    except: pass
    return []

def run_scanner():
    print(f"🕵️ SomaScanner Diagnostic Mode...")
    
    while True:
        try:
            dynamic_symbols = get_top_gainers()
            
            # 🛑 إذا كان هناك حظر، أرسل رسالة للتطبيق فوراً
            if dynamic_symbols and dynamic_symbols[0] == "ERROR-BINANCE":
                error_signal = {
                    "symbol": "BLOCKED ❌",
                    "price": 0.0, "tp1": 0, "tp2": 0, "sl": 0,
                    "vol": 0.0,
                    "time": "IP BAN"
                }
                if not any(d['symbol'] == "BLOCKED ❌" for d in signals_history):
                     signals_history.insert(0, error_signal)
                time.sleep(10)
                continue

            if dynamic_symbols:
                for symbol in dynamic_symbols:
                    candles = get_market_data(symbol)
                    if candles and len(candles) > 20:
                        # بما أننا وضعنا المضاعف 0.0 سيقبل أي شيء
                        current_candle = candles[-1]
                        close_price = float(current_candle[4])
                        
                        signal_data = {
                            "symbol": symbol,
                            "price": close_price,
                            "tp1": close_price * 1.01,
                            "tp2": close_price * 1.02,
                            "sl": close_price * 0.99,
                            "vol": 1.0, # رقم ثابت للتجربة
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # نمنع التكرار المزعج
                        exists = any(d['symbol'] == symbol for d in signals_history)
                        if not exists:
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 20: signals_history.pop()
                            
                    time.sleep(0.2)
            time.sleep(15)
        except Exception as e:
            print(f"Error Loop: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
