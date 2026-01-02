import time
import requests
import threading
import pandas as pd
import pandas_ta as ta  # مكتبة المحترفين للتحليل الفني
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# ---------------- إعدادات الإدارة (Admin) ----------------
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
ADMIN_ID = "1413638026" # المعرف الخاص بك لاستقبال التقارير

# القنوات (يجب أن تنشئ قناتين في تيليجرام)
VIP_CHANNEL_ID = "-100xxxxxxx"   # قناة المشتركين (توصيات كاملة)
FREE_CHANNEL_ID = "-100yyyyyyy"  # قناة العامة (توصيات مشفرة للإغراء)

# العملات
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT']
TIMEFRAME = '15m'
# ---------------------------------------------------------

app = Flask(__name__)

# قاعدة بيانات المشتركين (في الواقع تكون MongoDB)
# الهيكل: { user_id: { "plan": "vip", "expiry": "2024-12-30" } }
subscribers_db = {} 

# سجل الإشارات لمنع التكرار
signals_history = []

# --- 1. محرك البيانات والتحليل (The Brain) ---
def get_market_data(symbol):
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': 100}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_base', 'tb_quote', 'ignore'])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            return df
        return None
    except: return None

def analyze_market_pro(symbol):
    """تحليل النخبة باستخدام استراتيجية التلاقي (Confluence)"""
    df = get_market_data(symbol)
    if df is None: return None

    # حساب المؤشرات بمكتبة pandas-ta (أكثر دقة واحترافية)
    # 1. RSI
    df['rsi'] = ta.rsi(df['close'], length=14)
    # 2. MACD (لتحديد الزخم)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['macdsignal'] = macd['MACDs_12_26_9']
    # 3. EMA 200 (لتحديد الاتجاه العام)
    df['ema200'] = ta.ema(df['close'], length=200)

    # القيم الحالية
    current_price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macd_sig = df['macdsignal'].iloc[-1]
    ema200 = df['ema200'].iloc[-1]

    signal = None
    
    # --- استراتيجية "القناص التجاري" (High Probability Setup) ---
    # شروط صارمة جداً لتقليل الخسارة (للحفاظ على سمعة القناة المدفوعة)
    
    # شراء (Long): السعر فوق EMA200 + RSI منخفض وبدأ يصعد + تقاطع MACD إيجابي
    if current_price > ema200:
        if rsi < 40 and macd_val > macd_sig: # تقاطع إيجابي في قاع
            signal = {
                "type": "BUY 🟢",
                "symbol": symbol,
                "price": current_price,
                "tp1": current_price * 1.015, # ربح 1.5%
                "tp2": current_price * 1.03,  # ربح 3%
                "sl": current_price * 0.985,  # وقف 1.5%
                "reason": "ارتداد من ترند صاعد مع تقاطع MACD"
            }

    # بيع (Short): السعر تحت EMA200 + RSI مرتفع وبدأ يهبط + تقاطع MACD سلبي
    elif current_price < ema200:
        if rsi > 60 and macd_val < macd_sig:
            signal = {
                "type": "SELL 🔴",
                "symbol": symbol,
                "price": current_price,
                "tp1": current_price * 0.985,
                "tp2": current_price * 0.97,
                "sl": current_price * 1.015,
                "reason": "ارتداد من ترند هابط مع ضعف الزخم"
            }
            
    return signal

# --- 2. محرك التوزيع (The Dispatcher) ---
def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def distribute_signal(signal):
    # 1. رسالة الـ VIP (التفاصيل الكاملة)
    vip_msg = f"""
👑 **VIP SIGNAL | إشارة خاصة**
💎 العملة: #{signal['symbol']}
⚡ العملية: {signal['type']}
💵 الدخول: {signal['price']}

🎯 هدف 1: {signal['tp1']:.4f}
🎯 هدف 2: {signal['tp2']:.4f}
🛡️ وقف الخسارة: {signal['sl']:.4f}

📝 السبب: {signal['reason']}
    """
    # إرسال للقناة الخاصة (أو للمشتركين في الخاص)
    # send_telegram_msg(VIP_CHANNEL_ID, vip_msg) 
    send_telegram_msg(ADMIN_ID, vip_msg) # تجربة لك حالياً

    # 2. رسالة القناة العامة (Teaser / إغراء)
    # نخفي اسم العملة والأهداف لنجبرهم على الاشتراك
    free_msg = f"""
🔔 **إشارة جديدة قوية جداً!**
نظام الذكاء الاصطناعي رصد فرصة ذهبية 🔥

النوع: {signal['type']}
السبب: {signal['reason']}
نسبة النجاح المتوقعة: 85% 🚀

🔒 **تفاصيل العملة والأهداف متاحة لمشتركي VIP فقط.**
👈 للاشتراك والحصول على التوصية فوراً تواصل مع: @YourSupport
    """
    # send_telegram_msg(FREE_CHANNEL_ID, free_msg)
    # هنا نرسلها لك أيضاً للتجربة
    print(">> Free Channel Message Generated (Hidden Content)")

# --- 3. إدارة النظام (The Manager) ---
def engine_loop():
    print("💎 Commercial Engine Started...")
    while True:
        try:
            for symbol in TARGET_PAIRS:
                signal = analyze_market_pro(symbol)
                
                if signal:
                    # منع تكرار الإشارة لنفس العملة لمدة ساعة
                    is_duplicate = False
                    for old_sig in signals_history:
                        if old_sig['symbol'] == symbol:
                            time_diff = datetime.now() - old_sig['time']
                            if time_diff.seconds < 3600: # ساعة
                                is_duplicate = True
                                break
                    
                    if not is_duplicate:
                        print(f"💰 New Signal: {symbol}")
                        distribute_signal(signal)
                        signals_history.append({"symbol": symbol, "time": datetime.now()})
                        
                        # تنظيف التاريخ القديم
                        if len(signals_history) > 50: signals_history.pop(0)
                
                time.sleep(2) # راحة بين العملات
            
            time.sleep(300) # فحص كل 5 دقائق (الفريم 15 دقيقة لا يحتاج فحص كل ثانية)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# --- نظام API لإدارة المشتركين (لربطه بموقعك مستقبلاً) ---
@app.route('/add_subscriber', methods=['POST'])
def add_sub():
    """API لإضافة مشترك بعد الدفع"""
    data = request.json
    user_id = data.get('user_id')
    days = data.get('days', 30)
    
    expiry = datetime.now() + timedelta(days=days)
    subscribers_db[user_id] = {"plan": "vip", "expiry": expiry}
    
    send_telegram_msg(user_id, f"✅ تم تفعيل اشتراكك بنجاح لمدة {days} يوم!")
    return jsonify({"status": "success", "expiry": str(expiry)})

# تشغيل النظام
t = threading.Thread(target=engine_loop)
t.daemon = True
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
