import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات تجاوز الحظر ----------------
SCAN_LIMIT = 20
TIMEFRAME = "5m"
VOLUME_MULTIPLIER = 1.5 # خففنا الشرط قليلاً ليصطاد بسرعة
# ----------------------------------------------------

app = Flask(__name__)
signals_history = []

@app.route('/')
def home():
    return "✅ SomaScanner US-Mode is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def get_top_gainers():
    # 🇺🇸 استخدام الرابط الأمريكي لتجاوز حظر ريندر
    url = "https://api.binance.us/api/v3/ticker/24hr"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ Error: {resp.status_code}")
            return []
            
        data = resp.json()
        usdt_pairs = []
        for item in data:
            symbol = item['symbol']
            # باينانس الأمريكي يستخدم USD أحياناً بدلاً من USDT
            if (symbol.endswith("USDT") or symbol.endswith("USD")) and "UP" not in symbol and "DOWN" not in symbol:
                usdt_pairs.append(item)
        
        # ترتيب حسب الأكثر ربحاً
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
        return [x['symbol'] for x in sorted_pairs[:SCAN_LIMIT]]
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return []

def get_market_data(symbol):
    # 🇺🇸 أيضاً هنا نستخدم الرابط الأمريكي
    url = f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=21"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200: return resp.json()
    except: pass
    return []

def run_scanner():
    print(f"🇺🇸 SomaScanner US Edition Started...")
    
    # رسالة ترحيبية للتأكد من العمل
    test_signal = {
        "symbol": "SYSTEM-READY",
        "price": 1.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 0, "time": "NOW"
    }
    signals_history.append(test_signal)

    while True:
        try:
            dynamic_symbols = get_top_gainers()
            
            if dynamic_symbols:
                print(f"Found {len(dynamic_symbols)} coins...") # للمراقبة في السجلات
                
                for symbol in dynamic_symbols:
                    candles = get_market_data(symbol)
                    
                    if candles and len(candles) > 20:
                        current_candle = candles[-1]
                        close_price = float(current_candle[4])
                        open_price = float(current_candle[1])
                        current_volume = float(current_candle[5])
                        
                        # حساب الفوليوم
                        past_volumes = [float(c[5]) for c in candles[:-1]]
                        if len(past_volumes) > 0:
                            avg_volume = sum(past_volumes) / len(past_volumes)
                        else:
                            avg_volume = 1.0
                            
                        vol_strength = current_volume / avg_volume if avg_volume > 0 else 0
                        
                        # الشروط (مخففة قليلاً)
                        is_whale = current_volume > (avg_volume * VOLUME_MULTIPLIER)
                        
                        # الشرط الأهم: أن تكون العملة رابحة اليوم
                        price_change_pct = ((close_price - open_price) / open_price) * 100
                        is_pump = price_change_pct > 0.5 

                        if is_whale and is_pump:
                            signal_data = {
                                "symbol": symbol.replace("USD", ""), # تنظيف الاسم
                                "price": close_price,
                                "tp1": close_price * 1.02,
                                "tp2": close_price * 1.05,
                                "sl": close_price * 0.98,
                                "vol": round(vol_strength, 1),
                                "time": datetime.now().strftime("%H:%M")
                            }
                            
                            # منع التكرار
                            exists = any(d['symbol'] == signal_data['symbol'] for d in signals_history)
                            if not exists:
                                signals_history.insert(0, signal_data)
                                if len(signals_history) > 20: signals_history.pop()
                                print(f"🚀 Signal Found: {symbol}")

                    time.sleep(0.1) # سرعة الفحص
            
            else:
                print("⚠️ List empty (Check US API)")

            time.sleep(15)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
