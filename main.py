import time
import requests
import threading
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات البوت الكاملة ----------------
# 👇 تأكد من أن التوكن والآيدي هنا صحيحان
BOT_TOKEN = "8454394574:AAFKylU8ZnQjp9-3oCksAIxaOEEB1oJ9goU"
CHAT_ID = "1413638026"

SCAN_LIMIT = 50  # فحص أفضل 50 عملة عالمياً
# -----------------------------------------------------

app = Flask(__name__)
signals_history = []

# ✅ إشارة ترحيبية تظهر في التطبيق فوراً عند التشغيل
# (هذا الاسم SYSTEM-ONLINE هو ما سيظهر لك في التطبيق عند التحديث)
signals_history.append({
    "symbol": "SYSTEM-ONLINE",
    "price": 0.0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 100, "time": "NOW"
})

@app.route('/')
def home():
    return "✅ SomaScanner Ultimate is Running (Telegram + App + Gecko)!"

@app.route('/api/signals')
def get_signals():
    # رابط API الذي يقرأ منه التطبيق
    return jsonify(signals_history)

def send_telegram_alert(message):
    # وظيفة إرسال الرسائل لتيليجرام
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: 
        requests.post(url, json=payload, timeout=10)
    except Exception as e: 
        print(f"Telegram Error: {e}")

def get_coingecko_data():
    # جلب البيانات من السوق العالمي (CoinGecko) لتجاوز الحظر
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc", 
        "per_page": SCAN_LIMIT,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h"
    }
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200: return resp.json()
        else: 
            print(f"⚠️ API Status: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return []

def run_scanner():
    print("🚀 SomaScanner Ultimate Started...")
    
    # 🔔 إرسال رسالة تفعيل للتليجرام فور التشغيل
    send_telegram_alert("✅ **تم تشغيل النظام بالكامل!**\n(App + Telegram + CoinGecko)")
    
    while True:
        try:
            coins = get_coingecko_data()
            if coins:
                print(f"🔍 Checking {len(coins)} coins...")
                
                for coin in coins:
                    symbol = coin['symbol'].upper()
                    current_price = coin['current_price']
                    
                    # نسبة التغير في آخر ساعة
                    price_change_1h = coin.get('price_change_percentage_1h_in_currency')
                    
                    # معالجة القيم الفارغة
                    if price_change_1h is None: price_change_1h = 0.0
                    else: price_change_1h = float(price_change_1h)
                    
                    # 🔥 الشرط: ارتفاع أكثر من 0.5% في الساعة الأخيرة
                    is_pump = price_change_1h > 0.5 
                    
                    if is_pump:
                        # حساب الأهداف (سكالبينغ)
                        tp1 = current_price * 1.02
                        tp2 = current_price * 1.05
                        sl = current_price * 0.98
                        
                        signal_data = {
                            "symbol": symbol,
                            "price": current_price,
                            "tp1": tp1, "tp2": tp2, "sl": sl,
                            "vol": round(price_change_1h, 1),
                            "time": datetime.now().strftime("%H:%M")
                        }
                        
                        # التأكد من عدم تكرار الإشارة لنفس العملة
                        exists = any(d['symbol'] == symbol for d in signals_history)
                        
                        if not exists:
                            # 1. تحديث القائمة للتطبيق
                            signals_history.insert(0, signal_data)
                            if len(signals_history) > 30: signals_history.pop()
                            
                            # حذف رسالة النظام الافتراضية إذا وجدت إشارة حقيقية
                            if len(signals_history) > 1 and signals_history[-1]['symbol'] == "SYSTEM-ONLINE":
                                signals_history.pop()

                            # 2. إرسال تنبيه لتيليجرام 🔔
                            msg = f"""
🚀 **فرصة جديدة (Global)**
💎 العملة: #{symbol}
📈 الارتفاع: {price_change_1h:.2f}% (1h)
💰 السعر: {current_price}$

🎯 **أهداف:** {tp1:.4f} - {tp2:.4f}
🛡️ **وقف:** {sl:.4f}
                            """
                            send_telegram_alert(msg)
                            print(f"🔔 Signal Sent: {symbol}")
            
            # استراحة 45 ثانية (كوين جيكو يحتاج هذا الوقت)
            time.sleep(45)
            
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

# تشغيل البوت في الخلفية
t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
