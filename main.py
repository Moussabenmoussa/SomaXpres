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
# 1. CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "trado_master_key_v3")

# Database
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

# Email & Trading
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT']
TIMEFRAME = '15m'
signals_history = []

# ==========================================
# 2. ELITE TRADING ENGINE (Manual Calculation)
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
    """حساب المؤشرات يدوياً بدلاً من الاعتماد على مكتبات خارجية"""
    # 1. RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 2. EMA 200
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # 3. MACD
    k = df['close'].ewm(span=12, adjust=False, min_periods=12).mean()
    d = df['close'].ewm(span=26, adjust=False, min_periods=26).mean()
    df['macd'] = k - d
    df['macdsignal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()

    # 4. ATR (لإدارة المخاطر)
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

    try:
        df = calculate_indicators(df)
    except: return None

    # Get Last Values
    price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macd_sig = df['macdsignal'].iloc[-1]
    ema200 = df['ema200'].iloc[-1]
    atr = df['atr'].iloc[-1]

    signal = None
    
    # Buy Strategy
    if price > ema200:
        if rsi < 45 and macd_val > macd_sig:
            sl = price - (1.5 * atr)
            tp1 = price + (1.5 * atr)
            tp2 = price + (3.0 * atr)
            signal = {"type": "LONG 🟢", "symbol": symbol, "price": price, "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Trend Pullback"}

    # Sell Strategy
    elif price < ema200:
        if rsi > 55 and macd_val < macd_sig:
            sl = price + (1.5 * atr)
            tp1 = price - (1.5 * atr)
            tp2 = price - (3.0 * atr)
            signal = {"type": "SHORT 🔴", "symbol": symbol, "price": price, "sl": sl, "tp1": tp1, "tp2": tp2, "reason": "Trend Rejection"}
            
    if signal:
        # Rounding numbers
        for k in ['price', 'sl', 'tp1', 'tp2']:
            signal[k] = round(signal[k], 4)
        signal['time'] = datetime.now().strftime("%H:%M")
        return signal
    return None

def engine_loop():
    print("🚀 Engine Started (No-Lib Mode)...")
    while True:
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(analyze_market_pro, TARGET_PAIRS))

            for signal in results:
                if signal:
                    exists = False
                    for s in signals_history:
                        if s['symbol'] == signal['symbol'] and s['type'] == signal['type']:
                            exists = True
                            break
                    if not exists:
                        print(f"💎 Signal: {signal['symbol']}")
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
# 3. EMAIL SERVICE
# ==========================================
def send_email(to, subject, html_content):
    if not BREVO_API_KEY: return
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": "TRADOVIP", "email": SENDER_EMAIL}, "to": [{"email": to}], "subject": subject, "htmlContent": html_content}
    try: requests.post(url, data=json.dumps(payload), headers=headers)
    except: pass

# ==========================================
# 4. GLOBAL STYLES
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    :root { --primary: #0f172a; --accent: #3b82f6; --bg: #f8fafc; --text: #334155; --success: #10b981; --danger: #ef4444; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.6; }
    .navbar { background: white; padding: 1rem 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; }
    .logo { font-size: 1.5rem; font-weight: 800; color: var(--primary); text-decoration: none; }
    .container { max-width: 480px; margin: 3rem auto; padding: 0 1rem; }
    .card { background: white; padding: 2.5rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    h1, h2 { color: var(--primary); margin-top: 0; }
    input { width: 100%; padding: 0.75rem; margin-bottom: 1rem; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box; }
    .btn { display: block; width: 100%; background: var(--primary); color: white; padding: 0.8rem; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; text-align: center; }
    .btn:hover { opacity: 0.9; }
    .alert { padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; text-align: center; font-size: 0.9rem; }
    .error { background: #fee2e2; color: #991b1b; }
    .signal-item { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid transparent; }
    .signal-item.long { border-left-color: var(--success); } .signal-item.short { border-left-color: var(--danger); }
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
    .badge-long { background: #dcfce7; color: #15803d; } .badge-short { background: #fee2e2; color: #b91c1c; }
</style>
"""

# ==========================================
# 5. ROUTES
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""
    <!DOCTYPE html><html><head><title>TRADOVIP</title>{SHARED_STYLE}</head><body>
        <nav class="navbar">
            <a href="/" class="logo">TRADOVIP</a>
            <div style="display:flex; gap:10px;"><a href="/login" class="btn" style="width:auto; background:transparent; color:var(--text); border:1px solid #cbd5e1;">Login</a><a href="/signup" class="btn" style="width:auto; background:var(--accent);">Get Started</a></div>
        </nav>
        <div style="text-align:center; padding: 6rem 1rem;">
            <h1 style="font-size: 3.5rem; margin-bottom: 1rem;">Trade Smarter.</h1>
            <p style="font-size: 1.2rem; color: #64748b; margin-bottom: 3rem;">AI-powered crypto signals with risk management.</p>
            <a href="/signup" class="btn" style="width:auto; display:inline-block; padding: 1rem 3rem; background:var(--accent);">Start Free Trial</a>
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
        else: msg = "<div class='alert error'>Invalid credentials</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><title>Login</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 style="text-align:center">Welcome Back</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn">Login</button></form><p style="text-align:center; margin-top:1rem;"><a href="/forgot-password" style="color:#64748b;">Forgot Password?</a><br><br><a href="/signup" style="color:var(--accent); font-weight:bold;">Create Account</a></p></div></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        if users_collection is not None:
            if users_collection.find_one({"email": email}): msg = "<div class='alert error'>Email taken</div>"
            else:
                otp = str(random.randint(100000, 999999))
                users_collection.insert_one({"email": email, "password": generate_password_hash(password), "status": "pending", "otp": otp, "created_at": datetime.utcnow()})
                send_email(email, "Verify Account", f"<h1>Code: {otp}</h1>")
                session['pending_email'] = email
                return redirect('/verify')
    return render_template_string(f"""<!DOCTYPE html><html><head><title>Sign Up</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 style="text-align:center">Create Account</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn" style="background:var(--accent);">Sign Up</button></form><p style="text-align:center; margin-top:1rem;">Have an account? <a href="/login" style="color:var(--accent); font-weight:bold;">Login</a></p></div></div></body></html>""")

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_email' not in session: return redirect('/signup')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code')
        email = session['pending_email']
        user = users_collection.find_one({"email": email})
        if user and user.get('otp') == code:
            users_collection.update_one({"email": email}, {"$set": {"status": "active"}})
            session['user_id'] = str(user['_id'])
            return redirect('/dashboard')
        else: msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><title>Verify</title>{SHARED_STYLE}</head><body><div class="container"><div class="card text-center"><h2>Verify Email</h2><p>Code sent to {session.get('pending_email')}</p>{msg}<form method="POST"><input type="text" name="code" style="text-align:center; letter-spacing:5px; font-size:1.5rem;" required><button type="submit" class="btn">Verify</button></form></div></div></body></html>""")

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        user = users_collection.find_one({"email": email}) if users_collection is not None else None
        if user:
            code = str(random.randint(100000, 999999))
            users_collection.update_one({"email": email}, {"$set": {"reset_code": code}})
            send_email(email, "Reset Password", f"<h1>Code: {code}</h1>")
            session['reset_email'] = email
            return redirect('/reset-password')
        else: msg = "<div class='alert error'>Email not found</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><title>Forgot</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>Reset Password</h2>{msg}<form method="POST"><input type="email" name="email" placeholder="Enter your email" required><button type="submit" class="btn">Send Code</button></form></div></div></body></html>""")

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session: return redirect('/forgot-password')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code')
        password = request.form.get('password')
        email = session['reset_email']
        user = users_collection.find_one({"email": email})
        if user and user.get('reset_code') == code:
            users_collection.update_one({"email": email}, {"$set": {"password": generate_password_hash(password), "reset_code": None}})
            session.pop('reset_email', None)
            return redirect('/login')
        else: msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><title>New Password</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>New Password</h2>{msg}<form method="POST"><input type="text" name="code" placeholder="Code" required><input type="password" name="password" placeholder="New Password" required><button type="submit" class="btn">Change</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    html = ""
    if not signals_history:
        html = "<div style='text-align:center; padding:3rem; color:#94a3b8;'><div style='font-size:2rem;'>⏳</div><p>Scanning markets...</p></div>"
    else:
        for s in signals_history:
            cls, badge = ("long", "badge-long") if "LONG" in s['type'] else ("short", "badge-short")
            html += f"""<div class="signal-item {cls}"><div><div style="font-weight:800; font-size:1.2rem; color:var(--primary);">{s['symbol']}</div><div style="font-size:0.8rem; color:#64748b;">{s['reason']}</div><div style="margin-top:5px;"><span class="badge {badge}">{s['type']}</span></div></div><div style="text-align:right;"><div style="font-weight:700; font-size:1.1rem;">${s['price']}</div><div style="font-size:0.75rem; color:#64748b;">SL: <span style="color:#ef4444">{s['sl']}</span> | TP1: <span style="color:#10b981">{s['tp1']}</span></div><div style="font-size:0.7rem; color:#cbd5e1;">{s['time']}</div></div></div>"""
    return render_template_string(f"""<!DOCTYPE html><html><head><title>Dashboard</title>{SHARED_STYLE}<meta http-equiv="refresh" content="30"></head><body><nav class="navbar"><span class="logo">TRADOVIP</span><a href="/logout" style="color:#ef4444; text-decoration:none; font-weight:600;">Logout</a></nav><div class="container" style="max-width:600px;"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;"><h2 style="margin:0;">Live Signals 📡</h2><span style="font-size:0.8rem; background:#e0f2fe; color:#0369a1; padding:4px 10px; border-radius:20px; font-weight:600;">Auto-Refresh</span></div>{html}</div></body></html>""")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
