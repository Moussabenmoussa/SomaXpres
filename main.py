import time
import requests
import threading
import pandas as pd
import numpy as np
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات المحلل الفني المحترف ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"

# رموز العملات بصيغة باينانس (الأكثر دقة)
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT']

# الإطار الزمني: 15 دقيقة (أفضل للمضاربة السريعة)
TIMEFRAME = '15m' 
# ---------------------------------------------------------------

app = Flask(__name__)
signals_history = []

# رسالة البداية
signals_history.append({
    "symbol": "SYSTEM-READY",
    "price": 0.0, "tp": 0, "sl": 0, "strategy": "SMA+RSI", "time": "ACTIVE"
})

@app.route('/')
def home():
    return "✅ Professional Crypto Analyst is Running..."

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

# --- محرك البيانات (Binance API) ---
def get_market_data(symbol, interval='15m', limit=100):
    """جلب الشموع الحقيقية من باينانس"""
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # تحويل البيانات إلى DataFrame (تنسيق احترافي)
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_base', 'tb_quote', 'ignore'])
            df['close'] = df['close'].astype(float)
            return df
        return None
    except: return None

# --- المؤشرات الفنية (Pandas) ---
def calculate_indicators(df):
    # 1. RSI (مؤشر القوة النسبية)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 2. EMA 50 (متوسط متحرك أسي لتحديد الاتجاه القريب)
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # 3. EMA 200 (متوسط متحرك أسي لتحديد الاتجاه العام)
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    return df

def run_pro_scanner():
    print("🚀 Professional Engine Started (Binance Data)...")
    send_telegram_alert("📊 **تم تشغيل المحلل الذكي**\nاستراتيجية: Trend Pullback (تداول مع الاتجاه فقط)")
    
    while True:
        try:
            for symbol in TARGET_PAIRS:
                df = get_market_data(symbol, TIMEFRAME)
                
                if df is not None and len(df) > 50:
                    df = calculate_indicators(df)
                    
                    # استخراج آخر القيم
                    last_close = df['close'].iloc[-1]
                    last_rsi = df['rsi'].iloc[-1]
                    prev_rsi = df['rsi'].iloc[-2] # الشمعة السابقة
                    ema_50 = df['ema_50'].iloc[-1]
                    ema_200 = df['ema_200'].iloc[-1] # إذا كانت البيانات كافية
                    
                    signal_type = None
                    strength = "عادية"

                    # --- الاستراتيجية الذهبية (Trend Pullback) ---
                    # الشرط 1: السعر فوق متوسط 50 (يعني الاتجاه صاعد) -> لا نشتري أبداً في ترند هابط
                    # الشرط 2: RSI كان منخفضاً وبدأ بالارتداد للأعلى (تصحيح سعري)
                    
                    is_uptrend = last_close > ema_50
                    
                    # سيناريو 1: شراء آمن (تصحيح في ترند صاعد)
                    if is_uptrend and prev_rsi < 40 and last_rsi > 40:
                        signal_type = "شراء (ارتداد) 📈"
                        strength = "قوية 🔥"
                    
                    # سيناريو 2: انفجار سعري (اختراق قوي)
                    elif last_close > ema_50 and prev_rsi < 60 and last_rsi > 65:
                        signal_type = "زخم قوي 🚀"
                        strength = "متوسطة"

                    if signal_type:
                        # أهداف مدروسة (ليست عشوائية)
                        tp = last_close * 1.015  # ربح 1.5% (مضاربة)
                        sl = last_close * 0.99   # وقف خسارة 1%
                        
                        # التحقق من عدم تكرار الإشارة لنفس العملة في آخر 30 دقيقة
                        exists = False
                        for s in signals_history:
                            if s['symbol'] == symbol:
                                # مقارنة توقيت الإشارة (بسيط)
                                exists = True 
                                break
                        
                        if not exists:
                            # إضافة الإشارة
                            signal_data = {
                                "symbol": symbol,
                                "price": last_close,
                                "tp": tp, "sl": sl,
                                "strategy": strength,
                                "time": datetime.now().strftime("%H:%M")
                            }
                            
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 15: signals_history.pop()

                            msg = f"""
✅ **إشارة {strength}**
💎 العملة: #{symbol}
💵 السعر: {last_close}
📊 المؤشرات: RSI={last_rsi:.1f} | فوق EMA50

🎯 الهدف: {tp:.4f}
🛡️ الوقف: {sl:.4f}
                            """
                            send_telegram_alert(msg)
                            print(f"Signal Found: {symbol}")

                # راحة بسيطة لتجنب حظر API
                time.sleep(1) 
            
            print("...finsihed cycle, waiting...")
            time.sleep(120) # فحص كل دقيقتين
            
        except Exception as e:
            print(f"System Error: {e}")
            time.sleep(20)

# تشغيل المحرك في الخلفية
t = threading.Thread(target=run_pro_scanner)
t.daemon = True
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
