import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime
from groq import Groq # 🧠 استدعاء الذكاء الاصطناعي

# ---------------- إعدادات المفاتيح ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"
# مفتاح Groq الذي أرسلتَه لي 👇
GROQ_API_KEY = "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"

SCAN_LIMIT = 20  # نركز على أهم 20 عملة للتحليل الدقيق
# --------------------------------------------------

app = Flask(__name__)
signals_history = []

# إشارة ترحيبية
signals_history.append({
    "symbol": "AI-ACTIVATED",
    "price": 0.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 100, "time": "NOW"
})

# تهيئة عميل الذكاء الاصطناعي
client = Groq(api_key=GROQ_API_KEY)

@app.route('/')
def home():
    return "✅ SomaScanner AI Edition is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_ai_analysis(symbol, price, rsi):
    """دالة تسأل الذكاء الاصطناعي عن رأيه في الصفقة"""
    try:
        prompt = f"""
        You are a crypto sniper expert. 
        Coin: {symbol}
        Price: {price}$
        RSI: {rsi} (Technical Indicator).
        
        Analyze this setup in 1 short sentence. Is it a good entry? Why?
        Start with '🤖 AI Verdict:'
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192", # موديل سريع جداً ومجاني على Groq
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"🤖 AI Error: {e}"

# دوال التحليل الفني (كما هي)
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0: gains.append(change); losses.append(0)
        else: gains.append(0); losses.append(abs(change))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
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
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "1"}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200: return resp.json()
        return []
    except: return []

def run_scanner():
    print("🚀 AI Scanner Started...")
    send_telegram_alert("🤖 **تم تفعيل وضع الذكاء الاصطناعي (Groq Llama 3)!**\nسأقوم بتحليل كل صفقة قبل إرسالها.")
    
    # أهم العملات للفحص
    target_coins = ['bitcoin', 'ethereum', 'solana', 'binancecoin', 'ripple', 'dogecoin', 'pepe', 'shiba-inu']
    
    while True:
        try:
            for coin_id in target_coins:
                candles = get_coin_candles(coin_id)
                if candles and len(candles) > 20:
                    close_prices = [x[4] for x in candles]
                    current_price = close_prices[-1]
                    rsi = calculate_rsi(close_prices, 14)
                    
                    # شرط الدخول: RSI منخفض (قاع) أو بداية صعود
                    if rsi < 35 or (50 < rsi < 60):
                        symbol = coin_id.upper()
                        
                        # 🛑 هنا السحر: نسأل الذكاء الاصطناعي قبل الإرسال
                        ai_opinion = get_ai_analysis(symbol, current_price, round(rsi, 1))
                        
                        # إرسال التنبيه
                        msg = f"""
🧠 **تحليل AI مباشر**
💎 العملة: #{symbol}
📊 المؤشر: RSI {rsi:.1f}
💰 السعر: {current_price}$

{ai_opinion}
                        """
                        
                        # التأكد من عدم التكرار
                        exists = any(d['symbol'] == symbol for d in signals_history)
                        if not exists:
                            send_telegram_alert(msg)
                            
                            # تحديث التطبيق
                            signal_data = {
                                "symbol": symbol,
                                "price": current_price,
                                "tp1": current_price * 1.02,
                                "tp2": current_price * 1.05,
                                "sl": current_price * 0.98,
                                "vol": round(rsi, 1),
                                "time": datetime.now().strftime("%H:%M")
                            }
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 20: signals_history.pop()
                            if len(signals_history) > 1 and signals_history[-1]['symbol'] == "AI-ACTIVATED":
                                signals_history.pop()

                time.sleep(5) # استراحة قصيرة
            
            time.sleep(60) # استراحة الدورة
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
