import time
import requests
import threading
import pandas as pd
import pandas_ta as ta
import os
import random
import json
from flask import Flask, session, redirect, request, render_template_string
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "trado_global_key_v2")

# Database Connection
mongo_uri = os.getenv("MONGO_URI")
db = None
users_collection = None

if mongo_uri:
    try:
        client = MongoClient(mongo_uri)
        db = client.get_database("tradovip_db")
        users_collection = db.users
        print("✅ MongoDB Connected Successfully")
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")

# External Services
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")

# Trading Config
TARGET_PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT']
TIMEFRAME = '15m'
signals_history = [] # Live Signals Memory

# ==========================================
# 2. ELITE TRADING ENGINE (ATR + MACD + EMA)
# ==========================================
def get_market_data(symbol):
    """Fetch candlestick data from Binance"""
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': 100}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Create DataFrame
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'x', 'y', 'z', 'a', 'b', 'c'])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            return df
        return None
    except: return None

def analyze_market_pro(symbol):
    """Advanced Technical Analysis with Dynamic ATR Targets"""
    df = get_market_data(symbol)
    if df is None: return None

    try:
        # 1. Calculate Indicators
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # MACD for Momentum
        macd = ta.macd(df['close'])
        df['macd'] = macd['MACD_12_26_9']
        df['macdsignal'] = macd['MACDs_12_26_9']
        
        # EMA for Trend
        df['ema200'] = ta.ema(df['close'], length=200)
        
        # ATR for Volatility (The Secret Sauce for SL/TP)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    except: return None

    # Get Last Values
    price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    macd_val = df['macd'].iloc[-1]
    macd_sig = df['macdsignal'].iloc[-1]
    ema200 = df['ema200'].iloc[-1]
    atr = df['atr'].iloc[-1]

    signal = None
    
    # --- LONG STRATEGY (BUY) ---
    if price > ema200: # Uptrend
        if rsi < 45 and macd_val > macd_sig: # Oversold Bounce
            sl = price - (1.5 * atr) # Stop Loss below volatility
            tp1 = price + (1.5 * atr) # 1:1 Risk/Reward
            tp2 = price + (3.0 * atr) # 1:2 Risk/Reward
            
            signal = {
                "type": "LONG 🟢",
                "symbol": symbol,
                "price": price,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "reason": "Trend Pullback"
            }

    # --- SHORT STRATEGY (SELL) ---
    elif price < ema200: # Downtrend
        if rsi > 55 and macd_val < macd_sig: # Overbought Rejection
            sl = price + (1.5 * atr)
            tp1 = price - (1.5 * atr)
            tp2 = price - (3.0 * atr)
            
            signal = {
                "type": "SHORT 🔴",
                "symbol": symbol,
                "price": price,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "reason": "Trend Rejection"
            }
            
    if signal:
        # Formatting numbers
        signal['price'] = round(signal['price'], 4)
        signal['sl'] = round(signal['sl'], 4)
        signal['tp1'] = round(signal['tp1'], 4)
        signal['tp2'] = round(signal['tp2'], 4)
        signal['time'] = datetime.now().strftime("%H:%M")
        return signal
        
    return None

def engine_loop():
    print("🚀 Global Trading Engine Started...")
    while True:
        try:
            for symbol in TARGET_PAIRS:
                signal = analyze_market_pro(symbol)
                if signal:
                    # Prevent duplicates (30 mins cooldown)
                    exists = False
                    for s in signals_history:
                        if s['symbol'] == signal['symbol'] and s['type'] == signal['type']:
                            exists = True
                            break
                    
                    if not exists:
                        print(f"💎 New Signal: {signal['symbol']}")
                        signals_history.insert(0, signal)
                        if len(signals_history) > 20: signals_history.pop()
                
                time.sleep(2) # Avoid API Ban
            
            time.sleep(60) # Scan every minute
        except Exception as e:
            print(f"Engine Error: {e}")
            time.sleep(10)

t = threading.Thread(target=engine_loop)
t.daemon = True
t.start()

# ==========================================
# 3. EMAIL SERVICE (BREVO)
# ==========================================
def send_email(to, subject, html_content):
    if not BREVO_API_KEY: return
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {
        "sender": {"name": "TRADOVIP Team", "email": SENDER_EMAIL},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content
    }
    try: requests.post(url, data=json.dumps(payload), headers=headers)
    except: pass

# ==========================================
# 4. GLOBAL STYLES (Clean Professional UI)
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    :root {
        --primary: #0f172a;       /* Dark Navy */
        --accent: #3b82f6;        /* Bright Blue */
        --bg: #f8fafc;            /* Light Gray */
        --text: #334155;          /* Slate */
        --success: #10b981;
        --danger: #ef4444;
        --card-bg: #ffffff;
    }

    body {
        font-family: 'Inter', sans-serif;
        background: var(--bg);
        color: var(--text);
        margin: 0;
        line-height: 1.6;
    }

    /* Navbar */
    .navbar {
        background: white;
        padding: 1rem 5%;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
    }
    .logo { font-size: 1.5rem; font-weight: 800; color: var(--primary); text-decoration: none; letter-spacing: -1px; }
    
    /* Layout */
    .container { max-width: 480px; margin: 3rem auto; padding: 0 1rem; }
    .card { background: var(--card-bg); padding: 2.5rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    
    /* Typography */
    h1, h2, h3 { color: var(--primary); margin-top: 0; letter-spacing: -0.5px; }
    .text-center { text-align: center; }
    .text-muted { color: #64748b; font-size: 0.9rem; }

    /* Forms */
    label { display: block; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem; color: var(--primary); }
    input {
        width: 100%;
        padding: 0.75rem;
        margin-bottom: 1rem;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        font-size: 1rem;
        box-sizing: border-box;
        transition: border 0.2s;
    }
    input:focus { outline: none; border-color: var(--accent); ring: 2px solid var(--accent); }

    /* Buttons */
    .btn {
        display: block;
        width: 100%;
        background: var(--primary);
        color: white;
        padding: 0.8rem;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        text-align: center;
        text-decoration: none;
        transition: opacity 0.2s;
    }
    .btn:hover { opacity: 0.9; }
    .btn-outline { background: transparent; border: 1px solid #cbd5e1; color: var(--text); }
    .link { color: var(--accent); text-decoration: none; font-weight: 600; }

    /* Alerts */
    .alert { padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.9rem; text-align: center; }
    .error { background: #fee2e2; color: #991b1b; }
    .success { background: #d1fae5; color: #065f46; }

    /* Signal Card */
    .signal-item {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 4px solid transparent;
    }
    .signal-item.long { border-left-color: var(--success); }
    .signal-item.short { border-left-color: var(--danger); }
    
    .price-box { text-align: right; }
    .price { font-weight: 700; font-size: 1.1rem; color: var(--primary); }
    .targets { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
    .badge { 
        padding: 4px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; 
    }
    .badge-long { background: #dcfce7; color: #15803d; }
    .badge-short { background: #fee2e2; color: #b91c1c; }

</style>
"""

# ==========================================
# 5. ROUTES (WEB PAGES)
# ==========================================

@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en"><head><title>TRADOVIP | Elite Trading</title>{SHARED_STYLE}</head><body>
        <nav class="navbar">
            <a href="/" class="logo">TRADOVIP</a>
            <div style="display:flex; gap:10px;">
                <a href="/login" class="btn btn-outline" style="width:auto; padding:8px 20px;">Login</a>
                <a href="/signup" class="btn" style="width:auto; padding:8px 20px; background:var(--accent);">Get Started</a>
            </div>
        </nav>
        <div style="text-align:center; padding: 6rem 1rem;">
            <h1 style="font-size: 3.5rem; margin-bottom: 1rem; line-height:1.1;">
                Trade like a <span style="color:var(--accent)">Pro</span>.
            </h1>
            <p style="font-size: 1.2rem; color: #64748b; max-width: 600px; margin: 0 auto 3rem;">
                AI-powered signals with institutional-grade accuracy. 
                Real-time alerts, dynamic Stop Loss, and precise Targets.
            </p>
            <a href="/signup" class="btn" style="width:auto; display:inline-block; padding: 1rem 3rem; font-size: 1.1rem; background:var(--accent);">Start Free Trial</a>
            
            <div style="margin-top: 4rem; display: flex; gap: 20px; justify-content: center; flex-wrap: wrap;">
                <div class="card" style="flex:1; min-width:200px; padding:1.5rem;">
                    <h3>⚡ Real-time</h3>
                    <p class="text-muted">Instant execution signals from Binance.</p>
                </div>
                <div class="card" style="flex:1; min-width:200px; padding:1.5rem;">
                    <h3>🛡️ Risk Managed</h3>
                    <p class="text-muted">Dynamic ATR-based Stop Loss & Take Profits.</p>
                </div>
                <div class="card" style="flex:1; min-width:200px; padding:1.5rem;">
                    <h3>🤖 AI Analysis</h3>
                    <p class="text-muted">Powered by RSI, MACD & EMA Confluence.</p>
                </div>
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
        else:
            msg = "<div class='alert error'>Invalid email or password</div>"

    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><title>Login</title>{SHARED_STYLE}</head><body>
    <div class="container"><div class="card">
        <h2 class="text-center">Welcome Back</h2>
        {msg}
        <form method="POST">
            <label>Email Address</label>
            <input type="email" name="email" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit" class="btn">Sign In</button>
        </form>
        <div class="text-center" style="margin-top:1.5rem;">
            <a href="/forgot-password" class="text-muted" style="text-decoration:none;">Forgot Password?</a><br><br>
            Don't have an account? <a href="/signup" class="link">Sign Up</a>
        </div>
    </div></div></body></html>
    """)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        
        if users_collection is not None:
            if users_collection.find_one({"email": email}):
                msg = "<div class='alert error'>Email already registered</div>"
            else:
                otp = str(random.randint(100000, 999999))
                users_collection.insert_one({
                    "email": email,
                    "password": generate_password_hash(password),
                    "status": "pending",
                    "otp": otp,
                    "created_at": datetime.utcnow()
                })
                # Email Content
                html = f"""
                <div style='background:#f8fafc; padding:20px; text-align:center; font-family:sans-serif;'>
                    <div style='background:white; padding:30px; border-radius:8px; max-width:400px; margin:auto;'>
                        <h2 style='color:#0f172a;'>Verify Your Account</h2>
                        <p style='color:#64748b;'>Use this code to activate your TRADOVIP account:</p>
                        <h1 style='letter-spacing:5px; color:#3b82f6;'>{otp}</h1>
                    </div>
                </div>
                """
                send_email(email, "Activate Account - TRADOVIP", html)
                
                session['pending_email'] = email
                return redirect('/verify')
        else:
            msg = "<div class='alert error'>Database Error</div>"

    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><title>Sign Up</title>{SHARED_STYLE}</head><body>
    <div class="container"><div class="card">
        <h2 class="text-center">Create Account</h2>
        {msg}
        <form method="POST">
            <label>Email Address</label>
            <input type="email" name="email" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit" class="btn" style="background:var(--accent);">Create Account</button>
        </form>
        <p class="text-center" style="margin-top:1.5rem;">Already have an account? <a href="/login" class="link">Log in</a></p>
    </div></div></body></html>
    """)

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
        else:
            msg = "<div class='alert error'>Invalid Code</div>"

    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><title>Verify</title>{SHARED_STYLE}</head><body>
    <div class="container"><div class="card text-center">
        <h2>Enter Verification Code</h2>
        <p class="text-muted">We sent a code to <strong>{session.get('pending_email')}</strong></p>
        {msg}
        <form method="POST">
            <input type="text" name="code" placeholder="123456" style="text-align:center; font-size:1.5rem; letter-spacing:5px;" maxlength="6" required>
            <button type="submit" class="btn">Verify Account</button>
        </form>
    </div></div></body></html>
    """)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        user = users_collection.find_one({"email": email}) if users_collection is not None else None
        
        if user:
            reset_code = str(random.randint(100000, 999999))
            users_collection.update_one({"email": email}, {"$set": {"reset_code": reset_code}})
            html = f"<div style='text-align:center;'><h2>Reset Password Code</h2><h1>{reset_code}</h1></div>"
            send_email(email, "Reset Password - TRADOVIP", html)
            session['reset_email'] = email
            return redirect('/reset-password')
        else:
            msg = "<div class='alert error'>Email not found</div>"

    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><title>Forgot Password</title>{SHARED_STYLE}</head><body>
    <div class="container"><div class="card">
        <h2 class="text-center">Reset Password</h2>
        <p class="text-center text-muted">Enter your email to receive a reset code.</p>
        {msg}
        <form method="POST">
            <label>Email Address</label>
            <input type="email" name="email" required>
            <button type="submit" class="btn">Send Code</button>
        </form>
        <p class="text-center" style="margin-top:1.5rem;"><a href="/login" class="link">Cancel</a></p>
    </div></div></body></html>
    """)

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session: return redirect('/forgot-password')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code')
        new_pass = request.form.get('password')
        email = session['reset_email']
        user = users_collection.find_one({"email": email})
        
        if user and user.get('reset_code') == code:
            users_collection.update_one({"email": email}, {
                "$set": {"password": generate_password_hash(new_pass), "reset_code": None}
            })
            session.pop('reset_email', None)
            return redirect('/login')
        else:
            msg = "<div class='alert error'>Invalid Code</div>"

    return render_template_string(f"""
    <!DOCTYPE html><html lang="en"><head><title>New Password</title>{SHARED_STYLE}</head><body>
    <div class="container"><div class="card">
        <h2 class="text-center">Set New Password</h2>
        {msg}
        <form method="POST">
            <label>Verification Code</label>
            <input type="text" name="code" required style="text-align:center; letter-spacing:3px;">
            <label>New Password</label>
            <input type="password" name="password" required>
            <button type="submit" class="btn">Change Password</button>
        </form>
    </div></div></body></html>
    """)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    
    signals_html = ""
    if not signals_history:
        signals_html = """
        <div style='text-align:center; padding:3rem; color:#94a3b8;'>
            <div style='font-size:2rem; margin-bottom:10px;'>⏳</div>
            <p>Scanning the market for high-probability setups...</p>
            <small>This may take a few minutes. Please wait.</small>
        </div>
        """
    else:
        for s in signals_history:
            css_class = "long" if "LONG" in s['type'] else "short"
            badge_class = "badge-long" if "LONG" in s['type'] else "badge-short"
            
            # Elite Signal Display
            signals_html += f"""
            <div class="signal-item {css_class}">
                <div>
                    <div style="font-weight:800; font-size:1.2rem; color:var(--primary);">{s['symbol']}</div>
                    <div style="font-size:0.8rem; color:#64748b; font-weight:600;">{s['reason']}</div>
                    <div style="margin-top:5px;"><span class="badge {badge_class}">{s['type']}</span></div>
                </div>
                <div class="price-box">
                    <div class="price">${s['price']}</div>
                    <div class="targets">
                        <span style="color:#ef4444;">SL: {s['sl']}</span> | 
                        <span style="color:#10b981;">TP1: {s['tp1']}</span> | 
                        <span style="color:#059669;">TP2: {s['tp2']}</span>
                    </div>
                    <div style="font-size:0.7rem; color:#cbd5e1; margin-top:5px;">{s['time']}</div>
                </div>
            </div>
            """

    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en"><head><title>Dashboard</title>{SHARED_STYLE}<meta http-equiv="refresh" content="30"></head>
    <body style="background:#f1f5f9;">
        <nav class="navbar">
            <span class="logo">TRADOVIP</span>
            <a href="/logout" style="color:#ef4444; text-decoration:none; font-weight:600;">Logout</a>
        </nav>
        <div class="container" style="max-width:600px; margin-top:2rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
                <h2 style="margin:0;">Live Signals 📡</h2>
                <span style="font-size:0.8rem; background:#e0f2fe; color:#0369a1; padding:4px 10px; border-radius:20px; font-weight:600;">Auto-Refresh</span>
            </div>
            {signals_html}
        </div>
    </body></html>
    """)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================================
# 6. RUN APP
# ==========================================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
