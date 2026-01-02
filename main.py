import time
import requests
import threading
import traceback
from flask import Flask, jsonify
from datetime import datetime

# ---------------- إعدادات الطوارئ ----------------
SCAN_LIMIT = 5
TIMEFRAME = "5m"
# -----------------------------------------------

app = Flask(__name__)

# 👇 1. وضعنا إشارة ثابتة ستظهر لك 100% لتتأكد من التطبيق
signals_history = [
    {
        "symbol": "APP-WORKING",
        "price": 1.0, "tp1": 1.1, "tp2": 1.2, "sl": 0.9,
        "vol": 100.0,
        "time": "TEST-OK"
    }
]

@app.route('/')
def home():
    return "✅ SomaScanner API is Running!"

@app.route('/api/signals')
def get_signals():
    return jsonify(signals_history)

def get_market_data(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=5"
        # خدعة لتجاوز حظر المتصفحات
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200: 
            return resp.json()
        else:
            return None
    except: 
        return None

def run_scanner():
    print("🚀 Scanner Thread Started...")
    
    # تأخير بسيط لضمان تشغيل السيرفر أولاً
    time.sleep(5)
    
    while True:
        try:
            # سنجرب عملة واحدة فقط ومضمونة (BTC) لنرى هل الاتصال يعمل
            test_coin = "BTCUSDT"
            candles = get_market_data(test_coin)
            
            if candles:
                current_price = float(candles[-1][4])
                
                # إضافة إشارة حقيقية من السوق (BTC)
                signal_data = {
                    "symbol": "BTC-LIVE",
                    "price": current_price,
                    "tp1": current_price * 1.01,
                    "tp2": current_price * 1.02,
                    "sl": current_price * 0.99,
                    "vol": 99.0,
                    "time": datetime.now().strftime("%H:%M")
                }
                
                # تحديث القائمة (نحذف إشارة الاختبار ونضع الحقيقية)
                # نبحث هل BTC موجودة؟
                exists = any(d['symbol'] == "BTC-LIVE" for d in signals_history)
                if not exists:
                    signals_history.insert(0, signal_data)
            
            else:
                # إذا فشل جلب البيانات، أضف رسالة خطأ للقائمة
                err_signal = {
                    "symbol": "API-ERROR",
                    "price": 0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 0, "time": "FAIL"
                }
                if not any(d['symbol'] == "API-ERROR" for d in signals_history):
                    signals_history.insert(0, err_signal)

            time.sleep(10) # فحص كل 10 ثواني
            
        except Exception as e:
            # إذا انهار الكود، سجل الخطأ في القائمة لنراه في التطبيق
            error_msg = str(e)[:10] # نأخذ أول 10 حروف من الخطأ
            crash_signal = {
                "symbol": f"CRASH: {error_msg}",
                "price": 0, "tp1": 0, "tp2": 0, "sl": 0, "vol": 0, "time": "BUG"
            }
            if not any(d['time'] == "BUG" for d in signals_history):
                signals_history.insert(0, crash_signal)
            time.sleep(10)

# تشغيل الخيط
t = threading.Thread(target=run_scanner)
t.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
