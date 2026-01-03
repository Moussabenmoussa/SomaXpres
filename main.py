import time
import requests
import threading
import pandas as pd
import numpy as np
import os
import random
import json
from flask import Flask, session, redirect, request, render_template_string
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque

# ==========================================
# 1. SYSTEM CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "whale_hunter_lite")

# Database
mongo_uri = os.getenv("MONGO_URI")
db = None
users_collection = None
signals_collection = None

if mongo_uri:
    try:
        client = MongoClient(mongo_uri)
        db = client.get_database("tradovip_db")
        users_collection = db.users
        signals_collection = db.signals
        print("✅ MongoDB Connected")
    except: print("❌ Database Error")

# Services
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

signals_history = []
scan_logs = deque(maxlen=50)

# ==========================================
# 2. LIGHTWEIGHT WHALE HUNTER (RAM FRIENDLY)
# ==========================================

class WhaleHunterLite:
    def __init__(self):
        self.btc_trend = "neutral"
        self.coins_scanned = 0
        self.signal_cooldown = {}
        
        # إعدادات متوازنة
        self.CONFIG = {
            "MIN_VOLUME": 3_000_000,    # 3 مليون حجم تداول
            "VOL_SPIKE": 1.8,           # 1.8 ضعف المتوسط
            "MIN_SCORE": 40,
            "SCAN_DELAY": 60
        }

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        print(f"[{t}] {msg}")
        scan_logs.append({"time": t, "message": msg})

    def send_telegram(self, msg):
        if not BOT_TOKEN or not CHAT_ID: return
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=5)
        except: pass

    def get_market_tickers(self):
        """
        نسخة خفيفة جداً لا تستخدم Pandas لتقليل استهلاك الذاكرة
        """
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
            if r.status_code == 200:
                data = r.json()
                filtered = []
                # الفلترة اليدوية السريعة
                for item in data:
                    symbol = item['symbol']
                    if not symbol.endswith('USDT'): continue
                    
                    try:
                        vol = float(item['quoteVolume'])
                        change = float(item['priceChangePercent'])
                        
                        # شروط الفلترة الأولية
                        if vol > self.CONFIG["MIN_VOLUME"] and -15 < change < 15:
                            filtered.append({
                                'symbol': symbol,
                                'vol': vol,
                                'change': change,
                                'price': float(item['lastPrice'])
                            })
                    except: continue
                
                # ترتيب حسب الحجم واختيار أعلى 50 فقط لتوفير الذاكرة
                filtered.sort(key=lambda x: x['vol'], reverse=True)
                return filtered[:50]
            return []
        except Exception as e:
            self.log(f"API Error: {e}")
            return []

    def get_candles(self, symbol):
        try:
            url = "https://api.binance.com/api/v3/klines"
            # نطلب 50 شمعة فقط لتوفير الذاكرة
            params = {'symbol': symbol, 'interval': '15m', 'limit': 50}
            r = requests.get(url, params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data, columns=['t', 'o', 'h', 'l', 'c', 'v', 'x', 'y', 'z', 'a', 'b', 'd'])
                df['c'] = df['c'].astype(float) # Close
                df['v'] = df['v'].astype(float) # Volume
                df['h'] = df['h'].astype(float) # High
                df['l'] = df['l'].astype(float) # Low
                return df
            return None
        except: return None

    def analyze_coin(self, symbol, df):
        try:
            # 1. تحليل الفوليوم
            current_vol = df['v'].iloc[-1]
            avg_vol = df['v'].iloc[-20:-1].mean()
            
            if avg_vol == 0: return None
            vol_ratio = current_vol / avg_vol

            if vol_ratio < self.CONFIG["VOL_SPIKE"]: return None

            # 2. مؤشر RSI (يدوي سريع)
            delta = df['c'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            cur_rsi = rsi.iloc[-1]

            # 3. حساب النقاط
            score = 0
            reasons = []
            
            if vol_ratio > 3: score += 30; reasons.append(f"🔥 Vol Spike {vol_ratio:.1f}x")
            elif vol_ratio > 2: score += 20; reasons.append(f"📈 High Vol {vol_ratio:.1f}x")
            
            if cur_rsi < 30: score += 20; reasons.append(f"💎 Oversold RSI {cur_rsi:.0f}")
            elif cur_rsi < 45: score += 10; reasons.append(f"📉 Low RSI {cur_rsi:.0f}")
            
            # سعر الإغلاق أعلى من الفتح (شمعة خضراء)
            open_p = float(df['o'].iloc[-1])
            close_p = float(df['c'].iloc[-1])
            if close_p > open_p: score += 10; reasons.append("🟢 Green Candle")

            if score >= self.CONFIG["MIN_SCORE"]:
                # حساب الأهداف
                price = close_p
                tp1 = price * 1.02
                tp2 = price * 1.05
                sl = price * 0.97
                
                return {
                    "symbol": symbol,
                    "price": price,
                    "score": score,
                    "vol_ratio": vol_ratio,
                    "rsi": cur_rsi,
                    "tp1": tp1, "tp2": tp2, "sl": sl,
                    "reasons": reasons,
                    "time": datetime.now()
                }
            return None
        except: return None

    def run(self):
        self.log("🚀 Lite Engine Started...")
        self.send_telegram("✅ <b>Engine Restarted</b>\nOptimized for stability.")
        
        while True:
            try:
                # 1. جلب العملات (Light Request)
                candidates = self.get_market_tickers()
                self.coins_scanned = len(candidates)
                
                if not candidates:
                    self.log("No candidates found, retrying...")
                    time.sleep(30)
                    continue

                self.log(f"🔍 Scanning {len(candidates)} coins...")
                
                for coin in candidates:
                    symbol = coin['symbol']
                    
                    # تجاوز إذا تم إرسالها قريباً
                    if symbol in self.signal_cooldown:
                        if (datetime.now() - self.signal_cooldown[symbol]).seconds < 3600:
                            continue

                    # فحص الشموع
                    df = self.get_candles(symbol)
                    if df is not None:
                        signal = self.analyze_coin(symbol, df)
                        
                        if signal:
                            # تسجيل وإرسال
                            signals_history.insert(0, signal)
                            if len(signals_history) > 20: signals_history.pop()
                            
                            self.signal_cooldown[symbol] = datetime.now()
                            
                            msg = f"""
🐋 <b>WHALE ALERT</b>
<b>#{symbol}</b>

📊 Score: {signal['score']}
📈 Vol: {signal['vol_ratio']:.1f}x
📉 RSI: {signal['rsi']:.0f}

💵 Entry: {signal['price']}
🎯 TP1: {signal['tp1']:.4f}
🛡 SL: {signal['sl']:.4f}
                            """
                            self.send_telegram(msg)
                            self.log(f"✅ SIGNAL: {symbol}")
                            
                            # حفظ في قاعدة البيانات
                            if signals_collection:
                                try: signals_collection.insert_one(signal)
                                except: pass

                    time.sleep(0.5) # راحة لتجنب الحظر

                self.log("💤 Scan finished, sleeping...")
                time.sleep(self.CONFIG["SCAN_DELAY"])

            except Exception as e:
                self.log(f"Crash prevention: {e}")
                time.sleep(10)

# تشغيل المحرك
bot = WhaleHunterLite()
t = threading.Thread(target=bot.run)
t.daemon = True
t.start()

# ==========================================
# 3. EMAIL SERVICE
# ==========================================
def send_email(to, subject, html):
    if not BREVO_API_KEY: return
    try:
        requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "content-type": "application/json"},
            data=json.dumps({"sender": {"name": "TRADOVIP", "email": SENDER_EMAIL}, "to": [{"email": to}], "subject": subject, "htmlContent": html}),
            timeout=5
        )
    except: pass

# ==========================================
# 4. UI STYLES & ROUTES
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    :root { --bg: #0f172a; --text: #f1f5f9; --card: #1e293b; --accent: #3b82f6; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
    .card { background: var(--card); padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #334155; }
    .btn { background: var(--accent); color: white; padding: 10px; border-radius: 8px; text-decoration: none; display: block; text-align: center; font-weight: bold; border: none; width: 100%; cursor: pointer;}
    input { width: 100%; padding: 10px; margin-bottom: 10px; background: #020617; border: 1px solid #334155; color: white; border-radius: 8px; box-sizing: border-box; }
    .signal-header { display: flex; justify-content: space-between; font-weight: bold; margin-bottom: 5px; }
    .price { font-size: 1.2rem; font-weight: 800; color: #10b981; }
    .log-box { background: #020617; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 12px; height: 150px; overflow-y: auto; color: #94a3b8; }
</style>
"""

@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>TRADOVIP</title>{SHARED_STYLE}</head><body><div style="text-align:center;margin-top:50px;"><h1>TRADOVIP V3</h1><p>Smart Whale Tracker</p><br><a href="/login" class="btn">Login</a><br><a href="/signup" style="color:#94a3b8;">Create Account</a></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    
    sigs = ""
    if not signals_history:
        sigs = "<div style='text-align:center;color:#64748b;padding:20px;'>Scanning...</div>"
    else:
        for s in signals_history[:10]:
            t = s['time'].strftime("%H:%M") if isinstance(s['time'], datetime) else "N/A"
            sigs += f"""<div class="card"><div class="signal-header"><span>{s['symbol']}</span><span style="color:#f59e0b">Score: {s['score']}</span></div><div class="price">${s['price']}</div><div style="font-size:12px;color:#94a3b8;margin-top:5px;">Vol: {s['vol_ratio']:.1f}x | RSI: {s['rsi']:.0f} | {t}</div></div>"""

    logs = "<br>".join([f"[{l['time']}] {l['message']}" for l in list(scan_logs)[-8:]])

    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dash</title>{SHARED_STYLE}<meta http-equiv="refresh" content="30"></head><body>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;"><h3>Live Signals</h3><a href="/logout" style="color:#ef4444;">Exit</a></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;">
        <div class="card" style="text-align:center;margin:0;"><div style="font-size:20px;font-weight:bold;">{len(signals_history)}</div><div style="font-size:12px;color:#94a3b8;">Signals</div></div>
        <div class="card" style="text-align:center;margin:0;"><div style="font-size:20px;font-weight:bold;">{bot.coins_scanned}</div><div style="font-size:12px;color:#94a3b8;">Coins</div></div>
    </div>
    {sigs}
    <h3>Logs</h3>
    <div class="log-box">{logs}</div>
    </body></html>""")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        pwd = request.form.get('password')
        u = users_collection.find_one({"email": email}) if users_collection else None
        if u and check_password_hash(u['password'], pwd):
            session['user_id'] = str(u['_id'])
            return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title>{SHARED_STYLE}</head><body><div class="card"><h2>Login</h2><form method="POST"><input name="email" placeholder="Email"><input type="password" name="password" placeholder="Pass"><button class="btn">Login</button></form></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        pwd = request.form.get('password')
        if users_collection:
            users_collection.insert_one({"email": email, "password": generate_password_hash(pwd), "status": "active"})
            session['user_id'] = email # Auto login for simplicity
            return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign</title>{SHARED_STYLE}</head><body><div class="card"><h2>Sign Up</h2><form method="POST"><input name="email" placeholder="Email"><input type="password" name="password" placeholder="Pass"><button class="btn">Create</button></form></div></body></html>""")

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
