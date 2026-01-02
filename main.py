import time
import requests
import threading
from flask import Flask

# ---------------- إعدادات البوت ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"
SCAN_LIMIT = 20
TIMEFRAME = "5m"
VOLUME_MULTIPLIER = 3.0
# -----------------------------------------------

# إعداد سيرفر وهمي لإبقاء البوت مستيقظاً
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ SomaScanner Bot is Running 24/7!"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_top_gainers():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        usdt_pairs = []
        for item in data:
            symbol = item['symbol']
            if symbol.endswith("USDT") and "UP" not in symbol and "DOWN" not in symbol and "USDC" not in symbol:
                usdt_pairs.append(item)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
        return [x['symbol'] for x in sorted_pairs[:SCAN_LIMIT]]
    except: return []

def get_market_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=21"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200: return resp.json()
    except: pass
    return []

# --- وظيفة البوت الرئيسية (تعمل في الخلفية) ---
def run_scanner():
    print(f"💎 SomaScanner VIP (Render Version) يعمل الآن...")
    send_telegram_alert("✅ **تم تفعيل البوت على Render!** 🚀")
    
    last_alert_times = {}
    
    while True:
        try:
            # print("🔄") # إخفاء الطباعة لتخفيف الضغط
            dynamic_symbols = get_top_gainers()
            
            if dynamic_symbols:
                for symbol in dynamic_symbols:
                    candles = get_market_data(symbol)
                    
                    if candles and len(candles) > 20:
                        current_candle = candles[-1]
                        close_price = float(current_candle[4])
                        open_price = float(current_candle[1])
                        low_price = float(current_candle[3])
                        current_volume = float(current_candle[5])
                        candle_time = current_candle[0]
                        
                        past_volumes = [float(c[5]) for c in candles[:-1]]
                        avg_volume = sum(past_volumes) / len(past_volumes)
                        vol_strength = current_volume / avg_volume if avg_volume > 0 else 0
                        price_change_pct = ((close_price - open_price) / open_price) * 100

                        is_whale = current_volume > (avg_volume * VOLUME_MULTIPLIER)
                        is_pump = price_change_pct > 1.2
                        
                        last_time = last_alert_times.get(symbol, 0)
                        
                        if is_whale and is_pump and candle_time != last_time:
                            tp1 = close_price * 1.02
                            sl = low_price * 0.98
                            msg = f"💎 **توصية Render VIP**\n#{symbol}\nVol: {vol_strength:.1f}x\n💰 {close_price}\n🎯 {tp1:.4f}\n🛡️ {sl:.4f}"
                            send_telegram_alert(msg)
                            last_alert_times[symbol] = candle_time
                    time.sleep(0.5)
            time.sleep(15)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# تشغيل البوت في خيط منفصل (Thread) لكي لا يوقف السيرفر
t = threading.Thread(target=run_scanner)
t.start()

# تشغيل السيرفر الوهمي
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
