
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
app.secret_key = os.getenv("SECRET_KEY", "trado_mobile_v1")

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
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    # EMA
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    # MACD
    k = df['close'].ewm(span=12, adjust=False, min_periods=12).mean()
    d = df['close'].ewm(span=26, adjust=False, min_periods=26).mean()
    df['macd'] = k - d
    df['macdsignal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()
    # ATR
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
            signal = {"type": "LONG 🟢", "symbol": symbol, "price": price, "sl": price-(1.5*atr), "tp1": price+(1.5*atr), "tp2": price+(3.0*atr), "reason": "Trend Pullback"}
    elif price < ema200:
        if rsi > 55 and macd_val < macd_sig:
            signal = {"type": "SHORT 🔴", "symbol": symbol, "price": price, "sl": price+(1.5*atr), "tp1": price-(1.5*atr), "tp2": price-(3.0*atr), "reason": "Trend Rejection"}
            
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
        except: time.sleep(10)

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
# 4. MOBILE-FIRST STYLES (App Look)
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    :root {
        --primary: #0f172a;
        --accent: #2563eb;
        --bg: #f1f5f9;
        --card: #ffffff;
        --text: #1e293b;
        --success: #10b981;
        --danger: #ef4444;
    }

    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

    body {
        font-family: 'Inter', sans-serif;
        background: var(--bg);
        color: var(--text);
        margin: 0;
        padding-top: 60px; /* Space for fixed navbar */
        line-height: 1.5;
    }

    /* Mobile Navbar */
    .navbar {
        position: fixed;
        top: 0; left: 0; right: 0;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        height: 60px;
        padding: 0 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
        z-index: 1000;
    }
    .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); text-decoration: none; letter-spacing: -0.5px; }
    
    /* Layout & Cards */
    .container { 
        max-width: 100%; 
        padding: 20px; 
        margin: 0 auto; 
    }
    
    .card { 
        background: var(--card); 
        padding: 25px 20px; 
        border-radius: 16px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.03); 
        border: 1px solid #e2e8f0;
        margin-bottom: 20px;
    }
    
    /* Typography */
    h1 { font-size: 2rem; line-height: 1.1; color: var(--primary); margin-bottom: 10px; }
    h2 { font-size: 1.5rem; margin-bottom: 15px; }
    p { font-size: 0.95rem; color: #64748b; margin-bottom: 20px; }
    .text-center { text-align: center; }

    /* Mobile Friendly Forms */
    label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; }
    input {
        width: 100%;
        padding: 14px 16px; /* Finger friendly padding */
        margin-bottom: 16px;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        font-size: 16px; /* Prevents iOS zoom */
        background: #f8fafc;
        transition: all 0.2s;
    }
    input:focus { outline: none; border-color: var(--accent); background: white; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }

    /* Touch Buttons */
    .btn {
        display: block;
        width: 100%;
        background: var(--primary);
        color: white;
        padding: 16px; /* Larger touch area */
        border: none;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1rem;
        cursor: pointer;
        text-align: center;
        text-decoration: none;
        transition: transform 0.1s;
    }
    .btn:active { transform: scale(0.98); }
    .btn-outline { background: transparent; border: 1px solid #cbd5e1; color: var(--text); }
    .btn-accent { background: var(--accent); }

    /* Signal Card (App Style) */
    .signal-item {
        background: white;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        border: 1px solid #e2e8f0;
        position: relative;
        overflow: hidden;
    }
    .signal-item::before {
        content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
    }
    .signal-item.long::before { background: var(--success); }
    .signal-item.short::before { background: var(--danger); }
    
    .sig-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .sig-symbol { font-weight: 800; font-size: 1.1rem; color: var(--primary); }
    .sig-type { font-size: 0.75rem; font-weight: 700; padding: 4px 8px; border-radius: 6px; }
    .type-long { background: #dcfce7; color: #15803d; }
    .type-short { background: #fee2e2; color: #b91c1c; }
    
    .sig-body { display: flex; justify-content: space-between; align-items: flex-end; }
    .sig-price { font-size: 1.5rem; font-weight: 700; color: var(--text); letter-spacing: -0.5px; }
    .sig-meta { text-align: right; font-size: 0.8rem; color: #64748b; }
    .sig-targets { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e2e8f0; font-size: 0.85rem; display: flex; justify-content: space-between; }
    
    /* Alerts */
    .alert { padding: 15px; border-radius: 12px; margin-bottom: 20px; font-size: 0.9rem; text-align: center; }
    .error { background: #fee2e2; color: #991b1b; }
    
    /* Responsive adjustment for larger screens */
    @media (min-width: 768px) {
        .container { max-width: 480px; } /* Keep app-like width on desktop */
        body { background: #e2e8f0; } /* Darker bg on desktop to highlight the 'app' container */
        .container { background: var(--bg); min-height: 100vh; box-shadow: 0 0 20px rgba(0,0,0,0.05); }
    }
</style>
"""

# ==========================================
# 5. ROUTES
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TRADOVIP</title>{SHARED_STYLE}</head><body>
        <nav class="navbar">
            <a href="/" class="logo">TRADOVIP</a>
            <a href="/login" style="font-weight:600; color:var(--text); text-decoration:none;">Login</a>
        </nav>
        <div class="container" style="text-align:center; padding-top:40px;">
            <div style="margin-bottom:30px;">
                <span style="background:#dbeafe; color:#1e40af; padding:5px 12px; border-radius:20px; font-size:0.8rem; font-weight:600;">v2.0 Mobile Engine</span>
            </div>
            <h1>Trade Crypto<br><span style="color:var(--accent)">Like a Pro.</span></h1>
            <p>AI signals sent directly to your phone. Institutional grade accuracy with dynamic risk management.</p>
            
            <div style="margin: 40px 0;">
                <a href="/signup" class="btn btn-accent" style="margin-bottom:15px;">Start Free Trial</a>
                <a href="/login" class="btn btn-outline">Member Login</a>
            </div>

            <div style="text-align:left; margin-top:50px;">
                <div class="signal-item long">
                    <div class="sig-header"><span class="sig-symbol">BTC/USDT</span><span class="sig-type type-long">LONG 🟢</span></div>
                    <div class="sig-body">
                        <div><div class="sig-price">42,500.00</div></div>
                    </div>
                    <div class="sig-targets"><span>TP: 43,100</span><span>SL: 41,900</span></div>
                </div>
                <p style="text-align:center; font-size:0.8rem; margin-top:10px;">Sample signal preview</p>
            </div>
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
        else: msg = "<div class='alert error'>Invalid email or password</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 class="text-center">Welcome Back</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn btn-accent">Sign In</button></form><div class="text-center" style="margin-top:20px;"><a href="/forgot-password" style="color:#64748b; text-decoration:none; font-size:0.9rem;">Forgot Password?</a><br><br><a href="/signup" style="color:var(--accent); font-weight:600;">Create Account</a></div></div></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        if users_collection is not None:
            if users_collection.find_one({"email": email}): msg = "<div class='alert error'>Email already taken</div>"
            else:
                otp = str(random.randint(100000, 999999))
                users_collection.insert_one({"email": email, "password": generate_password_hash(password), "status": "pending", "otp": otp, "created_at": datetime.utcnow()})
                send_email(email, "Verify Code", f"<h1>{otp}</h1>")
                session['pending_email'] = email
                return redirect('/verify')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sign Up</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 class="text-center">Join TRADOVIP</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn btn-accent">Create Account</button></form><p class="text-center" style="margin-top:20px;">Already member? <a href="/login" style="color:var(--accent); font-weight:600;">Login</a></p></div></div></body></html>""")

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
        else: msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verify</title>{SHARED_STYLE}</head><body><div class="container"><div class="card text-center"><h2>Verify Email</h2><p>Enter the 6-digit code sent to your email.</p>{msg}<form method="POST"><input type="text" name="code" style="text-align:center; letter-spacing:5px; font-size:1.5rem;" maxlength="6" required><button type="submit" class="btn btn-accent">Verify</button></form></div></div></body></html>""")

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
        else: msg = "<div class='alert error'>Email not found</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Forgot</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>Reset Password</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><button type="submit" class="btn btn-accent">Send Code</button></form><p class="text-center" style="margin-top:20px;"><a href="/login" style="color:#64748b;">Cancel</a></p></div></div></body></html>""")

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
        else: msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>New Password</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>New Password</h2>{msg}<form method="POST"><input type="text" name="code" placeholder="Code" required style="text-align:center; letter-spacing:2px;"><input type="password" name="password" placeholder="New Password" required><button type="submit" class="btn btn-accent">Change Password</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    html = ""
    if not signals_history:
        html = "<div style='text-align:center; padding:3rem; color:#94a3b8;'><div style='font-size:2rem; margin-bottom:10px;'>📡</div><p>Scanning markets...</p></div>"
    else:
        for s in signals_history:
            cls = "long" if "LONG" in s['type'] else "short"
            type_cls = "type-long" if "LONG" in s['type'] else "type-short"
            html += f"""
            <div class="signal-item {cls}">
                <div class="sig-header">
                    <span class="sig-symbol">{s['symbol']}</span>
                    <span class="sig-type {type_cls}">{s['type']}</span>
                </div>
                <div class="sig-body">
                    <div><div class="sig-price">${s['price']}</div></div>
                    <div class="sig-meta">
                        <div>{s['time']}</div>
                        <div>{s['reason']}</div>
                    </div>
                </div>
                <div class="sig-targets">
                    <span style="color:var(--success)">TP1: {s['tp1']}</span>
                    <span style="color:var(--success)">TP2: {s['tp2']}</span>
                    <span style="color:var(--danger)">SL: {s['sl']}</span>
                </div>
            </div>
            """
    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Dashboard</title>{SHARED_STYLE}<meta http-equiv="refresh" content="30"></head><body>
        <nav class="navbar">
            <span class="logo">TRADOVIP</span>
            <a href="/logout" style="color:#ef4444; text-decoration:none; font-weight:600; font-size:0.9rem;">Logout</a>
        </nav>
        <div class="container">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                <h2 style="margin:0;">Live Signals</h2>
                <span style="font-size:0.75rem; background:#dbeafe; color:#1e40af; padding:4px 10px; border-radius:12px; font-weight:600;">Auto-Live</span>
            </div>
            {html}
        </div>
    </body></html>
    """)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
