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
# 1. SYSTEM CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "whale_hunter_v1")

# Database Connection
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

# Services
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

signals_history = [] 

# ==========================================
# 2. WHALE HUNTING ENGINE (Anti-Ban Strategy)
# ==========================================

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def get_all_tickers():
    """
    Step 1: The Funnel (Light Scan)
    Fetches 24hr stats for ALL coins in ONE request to save API calls.
    """
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return None
    except: return None

def get_klines(symbol):
    """
    Step 2: Deep Scan
    Fetches candles for specific suspect coins.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': '15m', 'limit': 50}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'x', 'y', 'z', 'a', 'b', 'c'])
            cols = ['open', 'high', 'low', 'close', 'vol']
            df[cols] = df[cols].astype(float)
            return df
        return None
    except: return None

def whale_radar():
    print("🚀 Whale Hunter Engine Started...")
    send_telegram("🐋 <b>TRADOVIP Whale Radar Active</b>\nScanning for volume anomalies on dips...")
    
    while True:
        try:
            # --- PHASE 1: FILTERING (The Funnel) ---
            tickers = get_all_tickers()
            if tickers is not None and not tickers.empty:
                
                # Filter Logic:
                # 1. Must be USDT pair
                # 2. Volume > 10M USDT (To avoid scams)
                # 3. Change% between -15% and +3% (Looking for dips/consolidation, not pumps)
                
                tickers['quoteVolume'] = tickers['quoteVolume'].astype(float)
                tickers['priceChangePercent'] = tickers['priceChangePercent'].astype(float)
                
                suspects = tickers[
                    (tickers['symbol'].str.endswith('USDT')) &
                    (tickers['quoteVolume'] > 10000000) & 
                    (tickers['priceChangePercent'] > -15) &
                    (tickers['priceChangePercent'] < 3)
                ]
                
                suspect_list = suspects['symbol'].tolist()
                # print(f"🔍 Scanning {len(suspect_list)} suspects...")

                # --- PHASE 2: DEEP ANALYSIS ---
                for symbol in suspect_list:
                    df = get_klines(symbol)
                    if df is not None:
                        # Logic:
                        # 1. Current Volume > 3x Average Volume (Whale Activity)
                        # 2. Price Reversal (Green Candle or Long Wick)
                        
                        # Calculate Indicators manually (No pandas_ta to avoid errors)
                        df['vol_ma'] = df['vol'].rolling(window=20).mean()
                        current_vol = df['vol'].iloc[-1]
                        avg_vol = df['vol_ma'].iloc[-2]
                        
                        close_price = df['close'].iloc[-1]
                        open_price = df['open'].iloc[-1]
                        
                        # RSI Calculation
                        delta = df['close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi = 100 - (100 / (1 + rs))
                        current_rsi = rsi.iloc[-1]

                        # The WHALE Formula 🐋
                        # Volume Spike (300%) AND (Green Candle OR Low RSI Recovery)
                        if current_vol > (avg_vol * 3.0):
                            if (close_price > open_price) or (current_rsi > 30 and current_rsi < 60):
                                
                                # Check duplicate
                                is_new = True
                                for s in signals_history:
                                    if s['symbol'] == symbol:
                                        if (datetime.now() - s['time']).total_seconds() < 7200: # 2 hours cooldown
                                            is_new = False
                                            break
                                
                                if is_new:
                                    process_whale_signal(symbol, close_price, current_vol, avg_vol, current_rsi)
                    
                    # Anti-Ban Protection: Sleep small amount between calls
                    time.sleep(0.2) 

            # Wait 2 minutes before next full scan
            time.sleep(120)
            
        except Exception as e:
            print(f"Scanner Error: {e}")
            time.sleep(20)

def process_whale_signal(symbol, price, vol, avg_vol, rsi):
    # Calculate Targets based on volatility (approx 3% and 6%)
    tp1 = price * 1.03
    tp2 = price * 1.06
    sl = price * 0.96
    
    vol_increase = int((vol / avg_vol) * 100)
    
    signal = {
        "symbol": symbol,
        "type": "WHALE ALERT 🐋",
        "price": price,
        "vol_spike": f"+{vol_increase}%",
        "tp1": tp1, "tp2": tp2, "sl": sl,
        "time": datetime.now()
    }
    
    signals_history.insert(0, signal)
    if len(signals_history) > 30: signals_history.pop()
    
    msg = f"""
🐋 <b>WHALE DETECTED</b>
<b>#{symbol}</b>

📊 <b>Volume Spike:</b> {vol_increase}% (Huge Buying)
📉 <b>Condition:</b> Reversal from Dip

💵 <b>Entry:</b> {price}
🎯 <b>TP1:</b> {tp1:.4f}
🎯 <b>TP2:</b> {tp2:.4f}
🛡 <b>SL:</b> {sl:.4f}

<i>Strategy: Volume Anomaly + Bottom Catching</i>
    """
    print(f"Whale Found: {symbol}")
    send_telegram(msg)

t = threading.Thread(target=whale_radar)
t.daemon = True
t.start()

# ==========================================
# 3. EMAIL SERVICE
# ==========================================
# ==========================================
# 2. خدمة البريد (تم إصلاحها لتظهر الأخطاء)
# ==========================================
def send_email(to, subject, html_content):
    print(f"📧 جاري محاولة إرسال إيميل إلى: {to}") # تسجيل بداية المحاولة
    
    if not BREVO_API_KEY: 
        print("❌ خطأ: BREVO_API_KEY غير موجود في الإعدادات!")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    # التأكد من أن البريد المرسل هو نفسه الموجود في الإعدادات لتجنب الحظر
    payload = {
        "sender": {"name": "TRADOVIP Team", "email": SENDER_EMAIL},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        # إزالة Threading مؤقتاً لنرى الخطأ مباشرة في السجلات
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        
        # طباعة رد Brevo في السجلات
        print(f"📡 حالة الاستجابة: {response.status_code}")
        if response.status_code == 201:
            print("✅ تم الإرسال بنجاح!")
        else:
            print(f"❌ فشل الإرسال. رسالة Brevo: {response.text}")
            
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")

# ==========================================
# 4. UI STYLES (Mobile First)
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    :root { --primary: #0f172a; --accent: #2563eb; --bg: #f1f5f9; --card: #ffffff; --text: #1e293b; --success: #10b981; --danger: #ef4444; }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-top: 60px; line-height: 1.5; }
    .navbar { position: fixed; top: 0; left: 0; right: 0; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); height: 60px; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; z-index: 1000; }
    .logo { font-size: 1.25rem; font-weight: 800; color: var(--primary); text-decoration: none; letter-spacing: -0.5px; }
    .container { width: 100%; max-width: 500px; margin: 0 auto; padding: 20px; }
    .card { background: var(--card); padding: 25px 20px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #e2e8f0; margin-bottom: 20px; }
    h1 { font-size: 2rem; line-height: 1.1; color: var(--primary); margin-bottom: 10px; }
    h2 { font-size: 1.5rem; margin-bottom: 15px; }
    p { font-size: 0.95rem; color: #64748b; margin-bottom: 20px; }
    .text-center { text-align: center; }
    label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; }
    input { width: 100%; padding: 14px 16px; margin-bottom: 16px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 16px; background: #f8fafc; transition: all 0.2s; }
    input:focus { outline: none; border-color: var(--accent); background: white; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
    .btn { display: block; width: 100%; background: var(--primary); color: white; padding: 16px; border: none; border-radius: 12px; font-weight: 600; font-size: 1rem; cursor: pointer; text-align: center; text-decoration: none; transition: transform 0.1s; }
    .btn:active { transform: scale(0.98); }
    .btn-outline { background: transparent; border: 1px solid #cbd5e1; color: var(--text); }
    .btn-accent { background: var(--accent); }
    
    /* Whale Card Style */
    .signal-item { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid #8b5cf6; position: relative; overflow: hidden; }
    .signal-item::after { content: '🐋'; position: absolute; right: -10px; bottom: -10px; font-size: 4rem; opacity: 0.05; pointer-events: none; }
    .price-box { text-align: left; }
    .price-val { font-weight: 800; font-size: 18px; color: var(--primary); }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; color: white; display: inline-block; margin-top: 5px; background: #8b5cf6; }
    .sig-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .sig-symbol { font-weight: 800; font-size: 1.1rem; color: var(--primary); }
    .sig-meta { text-align: right; font-size: 0.8rem; color: #64748b; }
    .alert { padding: 15px; border-radius: 12px; margin-bottom: 20px; font-size: 0.9rem; text-align: center; }
    .error { background: #fee2e2; color: #991b1b; }
    @media (min-width: 768px) { .container { max-width: 480px; } body { background: #e2e8f0; } .container { background: var(--bg); min-height: 100vh; box-shadow: 0 0 20px rgba(0,0,0,0.05); } }
</style>
"""

# ==========================================
# 5. ROUTES
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TRADOVIP</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">TRADOVIP</a><a href="/login" style="font-weight:600;color:var(--text);text-decoration:none;">Login</a></nav><div class="container" style="text-align:center; padding-top:40px;"><h1>Whale Hunting<br><span style="color:var(--accent)">Simplified.</span></h1><p>We detect massive volume spikes on dips before the pump happens.</p><div style="margin:40px 0;"><a href="/signup" class="btn btn-accent" style="margin-bottom:15px;">Start Free Trial</a><a href="/login" class="btn btn-outline">Member Login</a></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 class="text-center">Member Login</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn btn-accent">Login</button></form><div class="text-center" style="margin-top:20px;"><a href="/forgot-password" style="color:#64748b;text-decoration:none;font-size:0.9rem;">Forgot Password?</a><br><br><a href="/signup" style="color:var(--accent);font-weight:600;">Create Account</a></div></div></div></body></html>""")

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
                send_email(email, "Verify Code", f"<h1>{otp}</h1>")
                session['pending_email'] = email
                return redirect('/verify')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sign Up</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2 class="text-center">Join TRADOVIP</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn btn-accent">Sign Up</button></form><p class="text-center" style="margin-top:20px;">Already a member? <a href="/login" style="color:var(--accent);font-weight:600;">Login</a></p></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verify</title>{SHARED_STYLE}</head><body><div class="container"><div class="card text-center"><h2>Verify Email</h2><p>Check your email for the code.</p>{msg}<form method="POST"><input type="text" name="code" style="text-align:center;font-size:24px;letter-spacing:5px;" maxlength="6" required><button type="submit" class="btn btn-accent">Verify</button></form></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Forgot</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>Reset Password</h2>{msg}<form method="POST"><input type="email" name="email" required><button type="submit" class="btn btn-accent">Send Code</button></form><p class="text-center" style="margin-top:20px;"><a href="/login" style="color:#64748b;">Cancel</a></p></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>New Password</title>{SHARED_STYLE}</head><body><div class="container"><div class="card"><h2>New Password</h2>{msg}<form method="POST"><input type="text" name="code" placeholder="Code" required style="text-align:center;letter-spacing:3px;"><input type="password" name="password" placeholder="New Password" required><button type="submit" class="btn btn-accent">Change Password</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    html = ""
    if not signals_history:
        html = "<div style='text-align:center; padding:40px; color:#94a3b8;'><div style='font-size:30px;'>🐋</div><p>Scanning 300+ coins for whales...</p></div>"
    else:
        for s in signals_history:
            formatted_time = s['time'].strftime("%H:%M")
            html += f"""
            <div class="signal-item">
                <div>
                    <div class="sig-header">
                        <span class="sig-symbol">{s['symbol']}</span>
                        <span class="badge">WHALE 🐋</span>
                    </div>
                    <div style="font-size:12px; color:#64748b;">Vol Spike: {s['vol_spike']}</div>
                </div>
                <div class="price-box">
                    <div class="price-val">${s['price']}</div>
                    <div style="font-size:11px; color:#64748b; margin-top:5px;">
                        <span style="color:var(--success)">TP: {s['tp1']:.4f}</span><br>
                        <span style="color:var(--danger)">SL: {s['sl']:.4f}</span>
                    </div>
                    <div style="font-size:10px; color:#cbd5e1; margin-top:5px;">{formatted_time}</div>
                </div>
            </div>
            """
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Dashboard</title>{SHARED_STYLE}<meta http-equiv="refresh" content="60"></head><body><nav class="navbar"><span class="logo">TRADOVIP</span><a href="/logout" style="color:#ef4444;text-decoration:none;font-weight:600;font-size:0.9rem;">Logout</a></nav><div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;"><h2 style="margin:0;">Live Radar</h2><span style="font-size:0.75rem;background:#ede9fe;color:#5b21b6;padding:4px 10px;border-radius:12px;font-weight:600;">Scanning Active</span></div>{html}</div></body></html>""")

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
