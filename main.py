import os
import json
import numpy as np
from flask import Flask, session, redirect, request, render_template_string, jsonify
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# ==========================================
# 1. CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "hybrid_v1_secret")

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

# Telegram & Email
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# ==========================================
# 2. PYTHON ANALYZER (THE BRAIN)
# ==========================================
def calculate_indicators(closes, volumes):
    """حساب المؤشرات رياضياً بدون مكتبات خارجية لتقليل الحمل"""
    closes = np.array(closes, dtype=float)
    volumes = np.array(volumes, dtype=float)
    
    # RSI Calculation
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = np.mean(gain[-14:])
    avg_loss = np.mean(loss[-14:])
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
    # Volume Spike Calculation
    current_vol = volumes[-1]
    avg_vol = np.mean(volumes[-20:-1]) # متوسط آخر 20 شمعة
    
    vol_ratio = 0
    if avg_vol > 0:
        vol_ratio = current_vol / avg_vol
        
    return rsi, vol_ratio

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

# ==========================================
# 3. API ENDPOINTS (THE BRIDGE)
# ==========================================

@app.route('/api/analyze', methods=['POST'])
def analyze_data():
    """
    هنا يستقبل البايثون البيانات من هاتفك ويحللها
    """
    try:
        data = request.json
        symbol = data.get('symbol')
        closes = data.get('closes') # قائمة أسعار الإغلاق
        volumes = data.get('volumes') # قائمة الأحجام
        price = float(closes[-1])
        
        # 1. تشغيل المحرك التحليلي
        rsi, vol_ratio = calculate_indicators(closes, volumes)
        
        # 2. شروط صيد الحيتان (Whale Logic)
        # فوليوم عالي (> 2x) + RSI منخفض (< 45) يعني تجميع
        if vol_ratio >= 2.0 and rsi < 45:
            
            # منع التكرار (نتحقق من قاعدة البيانات)
            last_sig = None
            if signals_collection:
                last_sig = signals_collection.find_one(
                    {"symbol": symbol}, 
                    sort=[("time", -1)]
                )
            
            # إذا لم تكن هناك إشارة حديثة (ساعة واحدة)
            if not last_sig or (datetime.utcnow() - last_sig['time']).total_seconds() > 3600:
                
                # إعداد التوصية
                tp1 = price * 1.02
                sl = price * 0.97
                
                signal = {
                    "symbol": symbol,
                    "price": price,
                    "vol_ratio": round(vol_ratio, 1),
                    "rsi": round(rsi, 1),
                    "tp1": tp1,
                    "sl": sl,
                    "time": datetime.utcnow()
                }
                
                # حفظ وإرسال
                if signals_collection:
                    signals_collection.insert_one(signal)
                
                msg = f"""
🐋 <b>HYBRID WHALE ALERT</b>
<b>#{symbol}</b>

📈 <b>Vol Spike:</b> {vol_ratio:.1f}x
📉 <b>RSI:</b> {rsi:.0f} (Dip)

💵 <b>Price:</b> ${price}
🎯 <b>TP:</b> ${tp1:.4f}
🛡 <b>SL:</b> ${sl:.4f}

<i>Source: Mobile Proxy 📱</i>
                """
                send_telegram(msg)
                
                return jsonify({"status": "signal_found", "symbol": symbol})
        
        return jsonify({"status": "scanned", "vol": vol_ratio})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/signals/latest')
def get_latest_signals():
    """جلب آخر الإشارات لعرضها في الموقع"""
    if not signals_collection: return jsonify([])
    sigs = list(signals_collection.find({}, {'_id': 0}).sort("time", -1).limit(10))
    return jsonify(sigs)

# ==========================================
# 4. FRONTEND (THE SPY 🕵️‍♂️)
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    :root { --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --accent: #3b82f6; --success: #10b981; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; text-align: center; }
    .status-box { background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
    .pulse { width: 10px; height: 10px; background: var(--success); border-radius: 50%; display: inline-block; box-shadow: 0 0 0 rgba(16, 185, 129, 0.4); animation: pulse 2s infinite; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }
    .log-area { font-family: monospace; font-size: 12px; color: #94a3b8; text-align: left; height: 150px; overflow-y: auto; background: #020617; padding: 10px; border-radius: 8px; }
    .signal-card { background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #3b82f6; padding: 15px; border-radius: 10px; margin-top: 10px; text-align: left; }
    .btn { background: var(--accent); color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; display: inline-block; margin-top: 10px; }
</style>
"""

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    return render_template_string(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TRADOVIP Hybrid</title>
        {SHARED_STYLE}
    </head>
    <body>
        <div class="status-box">
            <h2>🐋 Hybrid Radar</h2>
            <p><span class="pulse"></span> Connected via your Device</p>
            <small style="color:#94a3b8">Keep this page open to scan market</small>
        </div>

        <div id="signals-container">
            <!-- Signals will appear here -->
        </div>

        <h3>Live Logs</h3>
        <div class="log-area" id="logs">Initializing Spy Module...</div>

        <script>
            // --- JAVASCRIPT SPY MODULE ---
            
            function log(msg) {{
                const logs = document.getElementById('logs');
                const time = new Date().toLocaleTimeString();
                logs.innerHTML = `<div>[${{time}}] ${{msg}}</div>` + logs.innerHTML;
            }}

            async function fetchBinanceData() {{
                try {{
                    // 1. Get Top Volume Coins (The Funnel)
                    const r = await fetch('https://api.binance.com/api/v3/ticker/24hr');
                    const data = await r.json();
                    
                    // Filter: USDT pairs, Vol > 10M
                    const targets = data.filter(t => 
                        t.symbol.endsWith('USDT') && 
                        parseFloat(t.quoteVolume) > 5000000 &&
                        !t.symbol.includes('UP') && !t.symbol.includes('DOWN')
                    ).sort((a,b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume)).slice(0, 30);

                    log(`Found ${{targets.length}} active coins. Scanning deep...`);

                    // 2. Deep Scan each coin
                    for (const coin of targets) {{
                        await analyzeCoin(coin.symbol);
                        await new Promise(r => setTimeout(r, 200)); // Delay to be safe
                    }}
                    
                    log('Cycle complete. Waiting 60s...');

                }} catch (e) {{
                    log('Binance Error: ' + e.message);
                }}
            }}

            async function analyzeCoin(symbol) {{
                try {{
                    // Get Candles (15m)
                    const r = await fetch(`https://api.binance.com/api/v3/klines?symbol=${{symbol}}&interval=15m&limit=30`);
                    const klines = await r.json();
                    
                    const closes = klines.map(k => k[4]); // Close prices
                    const volumes = klines.map(k => k[5]); // Volumes

                    // Send to Server Brain
                    const serverRes = await fetch('/api/analyze', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ symbol, closes, volumes }})
                    }});
                    
                    const resData = await serverRes.json();
                    if(resData.status === 'signal_found') {{
                        log(`🐋 WHALE FOUND: ${{symbol}}!`);
                        loadSignals(); // Refresh UI
                    }}

                }} catch (e) {{
                    // Ignore errors
                }}
            }}

            async function loadSignals() {{
                const r = await fetch('/api/signals/latest');
                const sigs = await r.json();
                const cont = document.getElementById('signals-container');
                cont.innerHTML = sigs.map(s => `
                    <div class="signal-card">
                        <div style="font-weight:bold; font-size:1.2rem; color:#3b82f6">${{s.symbol}}</div>
                        <div>Vol: ${{s.vol_ratio}}x | RSI: ${{s.rsi}}</div>
                        <div style="margin-top:5px; color:#10b981">TP: ${{s.tp1.toFixed(4)}}</div>
                    </div>
                `).join('');
            }}

            // Start the Loop
            setInterval(fetchBinanceData, 60000); // Run every minute
            fetchBinanceData(); // Run immediately
            loadSignals();
        </script>
    </body>
    </html>
    """)

# --- Auth Routes (نفس السابق) ---
@app.route('/')
def index(): return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>TRADOVIP</title>{SHARED_STYLE}</head><body><div style="text-align:center;margin-top:50px;"><h1>TRADOVIP Hybrid</h1><p>Client-Side Scanning Technology</p><br><a href="/login" class="btn">Login</a><br><br><a href="/signup" style="color:#94a3b8;">Create Account</a></div></body></html>""")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = users_collection.find_one({"email": request.form.get('email').strip().lower()}) if users_collection else None
        if u and check_password_hash(u['password'], request.form.get('password')):
            session['user_id'] = str(u['_id'])
            return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title>{SHARED_STYLE}</head><body><div class="status-box"><h2>Login</h2><form method="POST"><input name="email" placeholder="Email"><input type="password" name="password" placeholder="Pass"><button class="btn">Enter</button></form></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        if users_collection:
            users_collection.insert_one({"email": email, "password": generate_password_hash(request.form.get('password')), "status": "active"})
            session['user_id'] = email
            return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign</title>{SHARED_STYLE}</head><body><div class="status-box"><h2>Sign Up</h2><form method="POST"><input name="email" placeholder="Email"><input type="password" name="password" placeholder="Pass"><button class="btn">Create</button></form></div></body></html>""")

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
