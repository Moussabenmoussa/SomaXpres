import time
import requests
import threading
import pandas as pd
import numpy as np
import os
from datetime import datetime
from flask import Flask

# ==========================================
# 1. CONFIGURATION
# ==========================================
app = Flask(__name__)

# Telegram Config
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHANNEL_ID_HERE")

# Market Config
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT']
SCALP_TIMEFRAME = '5m'
SWING_TIMEFRAME = '15m'

# Memory to prevent duplicate signals
signals_history = []

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Missing Bot Token or Chat ID")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def get_binance_data(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': 100}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'x', 'y', 'z', 'a', 'b', 'c'])
            cols = ['open', 'high', 'low', 'close']
            df[cols] = df[cols].astype(float)
            return df
        return None
    except: return None

# ==========================================
# 3. TECHNICAL INDICATORS (Manual & Fast)
# ==========================================
def apply_indicators(df):
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # EMA 200 (Trend)
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # MACD (12, 26, 9)
    k = df['close'].ewm(span=12, adjust=False, min_periods=12).mean()
    d = df['close'].ewm(span=26, adjust=False, min_periods=26).mean()
    df['macd'] = k - d
    df['signal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()

    # Bollinger Bands (20, 2)
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper_bb'] = df['sma20'] + (2 * df['std'])
    df['lower_bb'] = df['sma20'] - (2 * df['std'])

    # ATR (14) - For Dynamic Stop Loss
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(14).mean()

    return df

# ==========================================
# 4. STRATEGY ENGINES
# ==========================================

def analyze_scalper(symbol):
    """
    Engine 1: SCALPER (5m)
    Logic: Price touches Lower Bollinger Band + RSI Oversold (<30) -> Buy Bounce
    """
    df = get_binance_data(symbol, SCALP_TIMEFRAME)
    if df is None: return None
    df = apply_indicators(df)

    current = df.iloc[-1]
    
    # Logic: LONG only for now (Safer)
    if current['close'] <= current['lower_bb'] and current['rsi'] < 35:
        # Quick Targets
        tp = current['close'] * 1.015 # 1.5% Profit
        sl = current['close'] * 0.99  # 1% Loss
        
        return {
            "symbol": symbol,
            "type": "SCALP BUY ⚡",
            "price": current['close'],
            "tp": tp,
            "sl": sl,
            "reason": "Bollinger Bounce + RSI Oversold"
        }
    return None

def analyze_swing(symbol):
    """
    Engine 2: SWING/SNIPER (15m)
    Logic: Price > EMA200 (Uptrend) + MACD Crossover + RSI Healthy
    """
    df = get_binance_data(symbol, SWING_TIMEFRAME)
    if df is None: return None
    df = apply_indicators(df)

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # Logic: Trend Following
    if curr['close'] > curr['ema200']: # Uptrend
        # MACD Bullish Cross (Line crosses Signal upwards)
        if prev['macd'] < prev['signal'] and curr['macd'] > curr['signal']:
            if curr['rsi'] < 60: # Room to grow
                
                # Dynamic Risk Management using ATR
                atr = curr['atr']
                sl = curr['close'] - (1.5 * atr)
                tp1 = curr['close'] + (1.5 * atr)
                tp2 = curr['close'] + (3.0 * atr)

                return {
                    "symbol": symbol,
                    "type": "VIP SWING 💎",
                    "price": curr['close'],
                    "tp1": tp1,
                    "tp2": tp2,
                    "sl": sl,
                    "reason": "Trend Pullback + MACD Cross"
                }
    return None

# ==========================================
# 5. MAIN LOOP
# ==========================================
def bot_engine():
    print("🚀 TRADOVIP Hybrid Engine Started...")



    
    while True:
        try:
            for symbol in TARGET_PAIRS:
                
                # 1. Run Scalper
                scalp_signal = analyze_scalper(symbol)
                if scalp_signal:
                    process_signal(scalp_signal)

                # 2. Run Swing
                swing_signal = analyze_swing(symbol)
                if swing_signal:
                    process_signal(swing_signal)
                
                time.sleep(1) # Respect Binance Rate Limits

            time.sleep(60) # Scan every minute
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

def process_signal(signal):
    """Check duplicates and send Telegram message"""
    global signals_history
    
    # Duplicate Check (Prevent spamming the same signal within 1 hour)
    for s in signals_history:
        if s['symbol'] == signal['symbol'] and s['type'] == signal['type']:
            time_diff = (datetime.now() - s['time']).total_seconds()
            if time_diff < 3600: # 1 Hour Cooldown
                return 

    # Add to history
    signal['time'] = datetime.now()
    signals_history.insert(0, signal)
    if len(signals_history) > 50: signals_history.pop()

    # Format Message
    if "SCALP" in signal['type']:
        msg = f"""
⚡ <b>SCALP SIGNAL</b> ⚡
<b>#{signal['symbol']}</b>

🔵 <b>Entry:</b> {signal['price']}
🟢 <b>TP:</b> {signal['tp']:.4f}
🔴 <b>SL:</b> {signal['sl']:.4f}

<i>Strategy: {signal['reason']}</i>
"""
    else:
        msg = f"""
💎 <b>VIP SWING SIGNAL</b> 💎
<b>#{signal['symbol']}</b>

🔵 <b>Entry:</b> {signal['price']}

🎯 <b>Target 1:</b> {signal['tp1']:.4f}
🎯 <b>Target 2:</b> {signal['tp2']:.4f}
🛡 <b>Stop Loss:</b> {signal['sl']:.4f}

<i>Logic: {signal['reason']}</i>
"""
    
    # Send
    print(f"Sending Signal: {signal['symbol']}")
    send_telegram(msg)

# Start Bot in Background
t = threading.Thread(target=bot_engine)
t.daemon = True
t.start()

# ==========================================
# 6. WEB SERVER (To Keep Render Alive)
# ==========================================
@app.route('/')
def index():
    return "<h1>TRADOVIP Bot is Running 24/7 🚀</h1>"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
