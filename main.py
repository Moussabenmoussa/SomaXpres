import time
import requests
import threading
import pandas as pd
import numpy as np
import os
import random
import json
import concurrent.futures
from flask import Flask, session, redirect, request, render_template_string
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# 1. إعدادات المشروع
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "trado_master_key_v3")

# قاعدة البيانات
mongo_uri = os.getenv("MONGO_URI")
db = None
users_collection = None

if mongo_uri:
    try:
        client = MongoClient(mongo_uri)
        db = client.get_database("tradovip_db")
        users_collection = db.users
        print("✅ MongoDB Connected")
    except: print("❌ Database Error")

# إعدادات البريد والتداول
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT']
TIMEFRAME = '15m'
signals_history = []

# ==========================================
# 2. محرك التداول (نفس الكود الذي اشتغل سابقاً)
# ==========================================
def get_market_data(symbol):
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': 300}
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

def calculate_indicators(df):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    k = df['close'].ewm(span=12, adjust=False, min_periods=12).mean()
    d = df['close'].ewm(span=26, adjust=False, min_periods=26).mean()
    df['macd'] = k - d
    df['macdsignal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(14).mean()
    return df

def analyze_market_pro(symbol):
    df = get_market_data(symbol)
    if df is None or len(df) < 200: return None
    try: df = calculate_indicators(df)
    except: return None

    price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macd_sig = df['macdsignal'].iloc[-1]
    ema200 = df['ema200'].iloc[-1]
    atr = df['atr'].iloc[-1]

    signal = None
    if price > ema200:
        if rsi < 45 and macd_val > macd_sig:
            sl = price - (1.5 * atr)
            tp1 = price + (1.5 * atr)
            tp2 = price + (3.0 * atr)
            signal = {"type": "LONG 🟢", "symbol": symbol, "price": price, "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Trend Pullback"}
    elif price < ema200:
        if rsi > 55 and macd_val < macd_sig:
            sl = price + (1.5 * atr)
            tp1 = price - (1.5 * atr)
            tp2 = price - (3.0 * atr)
            signal = {"type": "SHORT 🔴", "symbol": symbol, "price": price, "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Trend Rejection"}
            
    if signal:
        for k in ['price', 'sl', 'tp1', 'tp2']: signal[k] = round(signal[k], 4)
        signal['time'] = datetime.now().strftime("%H:%M")
        return signal
    return None

def engine_loop():
    print("🚀 Engine Started...")
    while True:
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(analyze_market_pro, TARGET_PAIRS))
            for signal in results:
                if signal:
                    exists = False
                    for s in signals_history:
                        if s['symbol'] == signal['symbol'] and s['type'] == signal['type']: exists = True; break
                    if not exists:
                        signals_history.insert(0, signal)
                        if len(signals_history) > 20: signals_history.pop()
            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

t = threading.Thread(target=engine_loop)
t.daemon = True
t.start()

# ==========================================
# 3. خدمة البريد
# ==========================================
def send_email(to, subject, html_content):
    if not BREVO_API_KEY: return
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": "TRADOVIP", "email": SENDER_EMAIL}, "to": [{"email": to}], "subject": subject, "htmlContent": html_content}
    try: requests.post(url, data=json.dumps(payload), headers=headers)
    except: pass

# ==========================================
# 4. التصميم (تم تعديله ليدعم الهاتف 100%)
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; --text: #1e293b; --success: #10b981; --danger: #ef4444; }
    
    * { box-sizing: border-box; }
    
    body { 
        font-family: 'Cairo', sans-serif; 
        background: var(--bg); 
        color: var(--text); 
        margin: 0; 
        direction: rtl; 
        font-size: 16px;
    }
    
    /* Navbar Mobile Friendly */
    .navbar { 
        background: white; 
        padding: 15px 20px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
        position: sticky; top: 0; z-index: 1000;
    }
    .logo { font-size: 20px; font-weight: 800; color: var(--primary); text-decoration: none; }
    
    /* Container responsive */
    .container { 
        width: 100%; 
        max-width: 500px; 
        margin: 0 auto; 
        padding: 20px; 
    }
    
    .card { 
        background: white; 
        padding: 25px; 
        border-radius: 16px; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
        border: 1px solid #e2e8f0; 
    }
    
    /* Inputs Mobile Friendly */
    input { 
        width: 100%; 
        padding: 15px; 
        margin: 10px 0; 
        border: 1px solid #cbd5e1; 
        border-radius: 10px; 
        font-size: 16px; /* Prevents zoom on iPhone */
        background: #fff;
    }
    
    .btn { 
        display: block; 
        width: 100%; 
        background: var(--primary); 
        color: white; 
        padding: 15px; 
        border: none; 
        border-radius: 10px; 
        font-weight: bold; 
        font-size: 16px; 
        cursor: pointer; 
        text-align: center;
        text-decoration: none;
    }
    
    .btn:active { transform: scale(0.98); }
    
    /* Signal Cards Mobile */
    .signal-item { 
        background: white; 
        border: 1px solid #e2e8f0; 
        border-radius: 12px; 
        padding: 15px; 
        margin-bottom: 15px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        border-left: 5px solid transparent; 
    }
    .signal-item.long { border-left-color: var(--success); } 
    .signal-item.short { border-left-color: var(--danger); }
    
    .price-box { text-align: left; }
    .price-val { font-weight: 800; font-size: 18px; }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; color: white; display: inline-block; margin-top: 5px; }
    .badge-long { background: var(--success); } 
    .badge-short { background: var(--danger); }
    
    /* Mobile Typography */
    h1 { font-size: 28px; line-height: 1.3; }
    p { font-size: 16px; color: #64748b; }
</style>
"""

# ==========================================
# 5. المسارات (نفس المنطق الذي نجح)
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    # إضافة meta viewport لدعم الموبايل
    return render_template_string(f"""
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TRADOVIP</title>{SHARED_STYLE}</head><body>
        <nav class="navbar">
            <a href="/" class="logo">TRADOVIP</a>
            <div><a href="/login" style="margin-left:10px;text-decoration:none;font-weight:bold;color:#333;">دخول</a><a href="/signup" class="btn" style="width:auto;padding:8px 15px;display:inline-block;font-size:14px;">جديد</a></div>
        </nav>
        <div style="text-align:center; padding: 60px 20px;">
            <h1>تداول بذكاء<br><span style="color:var(--primary)">من هاتفك</span></h1>
            <p>منصة توصيات نخبوية تعمل بالذكاء الاصطناعي.</p>
            <br>
            <a href="/signup" class="btn">ابدأ التجربة المجانية</a>
        </div>
    </body></html>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        user = users_collection.find_one({"email": email}) if users_collection is not None else None
        if user and check_password_hash(user['password'], password):
            if user.get('status') == 'pending':
                session['pending_email'] = email
                return redirect('/verify')
            session['user_id'] = str(user['_id'])
            return redirect('/dashboard')
        else: msg = "<div class='alert error' style='background:#fee2e2;color:red;padding:10px;border-radius:8px;margin-bottom:10px;text-align:center;'>البيانات غير صحيحة</div>"
    
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>دخول</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 style="text-align:center">تسجيل الدخول</h2>{msg}<form method="POST"><label>البريد الإلكتروني</label><input type="email" name="email" required><label>كلمة المرور</label><input type="password" name="password" required><button type="submit" class="btn">دخول</button></form><div style="text-align:center;margin-top:20px;"><a href="/forgot-password" style="color:#64748b;text-decoration:none;">نسيت كلمة المرور؟</a><br><br><a href="/signup" style="color:var(--primary);font-weight:bold;">حساب جديد</a></div></div></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        if users_collection is not None:
            if users_collection.find_one({"email": email}): msg = "<div class='alert error' style='background:#fee2e2;color:red;padding:10px;border-radius:8px;margin-bottom:10px;text-align:center;'>البريد مسجل مسبقاً</div>"
            else:
                otp = str(random.randint(100000, 999999))
                users_collection.insert_one({"email": email, "password": generate_password_hash(password), "status": "pending", "otp": otp, "created_at": datetime.utcnow()})
                send_email(email, "Verify Code", f"<h1 style='text-align:center'>{otp}</h1>")
                session['pending_email'] = email
                return redirect('/verify')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تسجيل</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 style="text-align:center">حساب جديد</h2>{msg}<form method="POST"><label>البريد</label><input type="email" name="email" required><label>كلمة المرور</label><input type="password" name="password" required><button type="submit" class="btn">تسجيل</button></form><p style="text-align:center;margin-top:20px;"><a href="/login" style="color:var(--primary);">لديك حساب؟</a></p></div></div></body></html>""")

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_email' not in session: return redirect('/signup')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code')
        user = users_collection.find_one({"email": session['pending_email']})
        if user and user.get('otp') == code:
            users_collection.update_one({"email": session['pending_email']}, {"$set": {"status": "active"}})
            session['user_id'] = str(user['_id'])
            return redirect('/dashboard')
        else: msg = "<div class='alert error' style='background:#fee2e2;color:red;padding:10px;text-align:center;'>الكود خطأ</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تفعيل</title>{SHARED_STYLE}</head><body><div class="container"><div class="card" style="text-align:center"><h2>تفعيل الحساب</h2><p>أدخل الكود المرسل للإيميل</p>{msg}<form method="POST"><input type="text" name="code" style="text-align:center;font-size:24px;letter-spacing:5px;" maxlength="6" required><button type="submit" class="btn">تفعيل</button></form></div></div></body></html>""")

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        user = users_collection.find_one({"email": email}) if users_collection else None
        if user:
            code = str(random.randint(100000, 999999))
            users_collection.update_one({"email": email}, {"$set": {"reset_code": code}})
            send_email(email, "Reset Password", f"<h1>{code}</h1>")
            session['reset_email'] = email
            return redirect('/reset-password')
        else: msg = "<div class='alert error' style='color:red;text-align:center;'>البريد غير موجود</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>استعادة</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>استعادة كلمة المرور</h2>{msg}<form method="POST"><input type="email" name="email" placeholder="بريدك الإلكتروني" required><button type="submit" class="btn">إرسال الكود</button></form><p style="text-align:center;margin-top:20px;"><a href="/login">إلغاء</a></p></div></div></body></html>""")

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session: return redirect('/forgot-password')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code')
        pwd = request.form.get('password')
        user = users_collection.find_one({"email": session['reset_email']})
        if user and user.get('reset_code') == code:
            users_collection.update_one({"email": session['reset_email']}, {"$set": {"password": generate_password_hash(pwd), "reset_code": None}})
            return redirect('/login')
        else: msg = "<div class='alert error' style='color:red;text-align:center;'>الكود خطأ</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>كلمة مرور جديدة</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>تعيين كلمة المرور</h2>{msg}<form method="POST"><input type="text" name="code" placeholder="الكود" required style="text-align:center;letter-spacing:3px;"><input type="password" name="password" placeholder="كلمة المرور الجديدة" required><button type="submit" class="btn">حفظ</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    html = ""
    if not signals_history:
        html = "<div style='text-align:center; padding:40px; color:#94a3b8;'><div style='font-size:30px;'>⏳</div><p>جاري البحث عن فرص...</p></div>"
    else:
        for s in signals_history:
            cls, badge = ("long", "badge-long") if "LONG" in s['type'] else ("short", "badge-short")
            html += f"""
            <div class="signal-item {cls}">
                <div>
                    <div style="font-weight:800; font-size:18px; color:var(--primary);">{s['symbol']}</div>
                    <div style="font-size:12px; color:#64748b;">{s['reason']}</div>
                    <span class="badge {badge}">{s['type']}</span>
                </div>
                <div class="price-box">
                    <div class="price-val">${s['price']}</div>
                    <div style="font-size:11px; color:#64748b; margin-top:5px;">
                        <span style="color:var(--danger)">SL: {s['sl']}</span><br>
                        <span style="color:var(--success)">TP: {s['tp1']}</span>
                    </div>
                    <div style="font-size:10px; color:#cbd5e1; margin-top:5px;">{s['time']}</div>
                </div>
            </div>
            """
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>لوحة التحكم</title>{SHARED_STYLE}<meta http-equiv="refresh" content="30"></head><body><nav class="navbar"><span class="logo">TRADOVIP</span><a href="/logout" style="color:#ef4444;text-decoration:none;font-weight:bold;">خروج</a></nav><div class="container"><h2 style="margin-bottom:20px;">التوصيات الحية 🔴</h2>{html}</div></body></html>""")

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
