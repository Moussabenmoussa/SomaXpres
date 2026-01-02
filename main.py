import time
import requests
import threading
import math
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات المحلل الفني ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"

# سنفحص أهم 10 عملات فقط لأن التحليل عميق ويحتاج وقت
TARGET_COINS = ['bitcoin', 'ethereum', 'solana', 'binancecoin', 'ripple', 'cardano', 'avalanche-2', 'dogecoin', 'polkadot', 'chainlink']
# -----------------------------------------------------

app = Flask(__name__)
signals_history = []

# إشارة النظام
signals_history.append({
    "symbol": "ANALYST-MODE",
    "price": 0.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 0, "time": "ACTIVE"
})

@app.route('/')
def home():
    return "✅ SomaScanner Analyst Mode is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# --- دوال التحليل الفني (الرياضيات) ---

def calculate_rsi(prices, period=14):
    """حساب مؤشر القوة النسبية RSI يدوياً"""
    if len(prices) < period + 1: return 50 # بيانات غير كافية
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
            
    # المتوسط الأول
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0: return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # التمهيد (Smoothed) لباقي البيانات
    for i in range(period, len(prices)-1):
        change = prices[i] - prices[i-1]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_coin_candles(coin_id):
    """جلب الشموع التاريخية من CoinGecko"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "1"} # شموع آخر 24 ساعة (30 دقيقة)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json() # يعيد مصفوفة [time, open, high, low, close]
        return []
    except: return []

def run_scanner():
    print("🚀 Analyst Engine Started...")
    send_telegram_alert("🧠 **تم تفعيل وضع التحليل الفني العميق**\nجاري حساب RSI و SMA للعملات الكبرى...")
    
    while True:
        try:
            for coin_id in TARGET_COINS:
                # 1. جلب البيانات التاريخية (الشموع)
                candles = get_coin_candles(coin_id)
                
                if candles and len(candles) > 20:
                    # استخراج أسعار الإغلاق فقط للحساب
                    close_prices = [x[4] for x in candles]
                    current_price = close_prices[-1]
                    
                    # 2. حساب المؤشرات
                    rsi = calculate_rsi(close_prices, 14)
                    
                    # 3. الاستراتيجية (السر):
                    # - شراء إذا كان RSI منخفض (تحت 35) وبدأ يرتفع (ارتداد من القاع)
                    # - أو شراء إذا كان RSI قوي (فوق 50) ولكن لم يتشبع بعد (تحت 70) = ترند صاعد
                    
                    signal_type = None
                    
                    # استراتيجية القنص من القاع (Oversold Bounce)
                    if rsi < 35:
                        signal_type = "قنص قاع 🟢"
                    
                    # استراتيجية ركوب الترند (Trend Following)
                    elif 55 < rsi < 70:
                        signal_type = "زخم صعودي 🔥"
                    
                    if signal_type:
                        symbol = coin_id.upper()
                        tp1 = current_price * 1.02
                        tp2 = current_price * 1.05
                        sl = current_price * 0.98
                        
                        signal_data = {
                            "symbol": symbol,
                            "price": current_price,
                            "tp1": tp1, "tp2": tp2, "sl": sl,
                            "vol": round(rsi, 1), # سنعرض قيمة RSI مكان الفوليوم للأهمية
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # منع التكرار
                        exists = any(d['symbol'] == symbol and d['time'] == signal_data['time'] for d in signals_history)
                        
                        if not exists:
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 20: signals_history.pop()
                            if len(signals_history) > 1 and signals_history[-1]['symbol'] == "ANALYST-MODE":
                                signals_history.pop()

                            msg = f"""
🧠 **تحليل فني آلي**
💎 العملة: #{symbol}
📊 المؤشر: RSI = {rsi:.1f}
⚡ النوع: {signal_type}
💰 السعر: {current_price}$

🎯 **أهداف:** {tp1:.4f} - {tp2:.4f}
🛡️ **وقف:** {sl:.4f}
                            """
                            send_telegram_alert(msg)
                            print(f"Signal: {symbol} | RSI: {rsi}")
                
                # انتظار 4 ثواني بين كل عملة لتجنب الحظر (مهم جداً في هذا الوضع)
                time.sleep(4)
            
            # انتظار دقيقة بعد فحص كل القائمة
            time.sleep(60)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
