import time
import requests
import threading
import pandas as pd
import numpy as np
import os
import random
import json
from flask import Flask, session, redirect, request, render_template_string
from datetime import datetime, timedelta
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque

# ==========================================
# 1. SYSTEM CONFIGURATION (لا تغيير)
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "whale_hunter_v3")

# Database Connection
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
    except:
        print("❌ Database Error")

# Services
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

signals_history = []
scan_logs = deque(maxlen=100)  # سجل المسح للتتبع

# ==========================================
# 2. WHALE HUNTER V3 - BALANCED EDITION
# ==========================================

class WhaleHunterV3:
    """
    محرك اكتشاف الحيتان V3
    شروط متوازنة لإنتاج إشارات أكثر مع الحفاظ على الجودة
    """

    def __init__(self):
        self.btc_trend = "neutral"
        self.btc_price = 0
        self.coins_scanned = 0
        self.last_scan_time = None
        self.signal_cooldown = {}

        # ========= إعدادات قابلة للتعديل =========
        self.CONFIG = {
            # الحد الأدنى لحجم التداول (بالدولار)
            "MIN_VOLUME_USDT": 2_000_000,  # 2 مليون (مخفض من 5 مليون)

            # مضاعف الحجم المطلوب
            "VOLUME_SPIKE_MIN": 1.8,       # 180% من المتوسط (مخفض من 250%)
            "VOLUME_SPIKE_STRONG": 2.5,    # 250% = إشارة قوية
            "VOLUME_SPIKE_WHALE": 4.0,     # 400% = حوت حقيقي

            # ضغط الشراء
            "BUY_PRESSURE_MIN": 0.48,      # 48% كحد أدنى (مخفض من 52%)
            "BUY_PRESSURE_STRONG": 0.55,   # 55% = قوي
            "BUY_PRESSURE_WHALE": 0.65,    # 65% = حوت

            # الحد الأدنى للنقاط
            "MIN_SCORE": 35,               # مخفض من 45
            "STRONG_SCORE": 55,
            "WHALE_SCORE": 70,

            # وقت الانتظار بين الإشارات لنفس العملة (بالثواني)
            "COOLDOWN_SECONDS": 3600,      # ساعة واحدة (مخفض من 4 ساعات)

            # وقت الانتظار بين المسحات (بالثواني)
            "SCAN_INTERVAL": 60,           # كل دقيقة (مخفض من 90 ثانية)
        }

    def log(self, message, level="INFO"):
        """تسجيل الأحداث"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        scan_logs.append({"time": timestamp, "level": level, "message": message})

    def send_telegram(self, message):
        """إرسال إشعار تيليجرام"""
        if not BOT_TOKEN or not CHAT_ID:
            self.log("Telegram not configured", "WARN")
            return False
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code == 200:
                self.log("Telegram sent ✓", "INFO")
                return True
            else:
                self.log(f"Telegram error: {r.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Telegram exception: {e}", "ERROR")
            return False

    def get_btc_status(self):
        """تحليل حالة Bitcoin"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 12}
            r = requests.get(url, params=params, timeout=10)

            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'x', 'y', 'z', 'a', 'b', 'c'])
                df['close'] = df['close'].astype(float)
                df['open'] = df['open'].astype(float)

                self.btc_price = df['close'].iloc[-1]
                change_4h = ((df['close'].iloc[-1] - df['close'].iloc[-4]) / df['close'].iloc[-4]) * 100

                if change_4h < -4:
                    self.btc_trend = "strong_down"
                elif change_4h < -2:
                    self.btc_trend = "down"
                elif change_4h > 3:
                    self.btc_trend = "strong_up"
                elif change_4h > 1:
                    self.btc_trend = "up"
                else:
                    self.btc_trend = "neutral"

                self.log(f"BTC: ${self.btc_price:.0f} | Trend: {self.btc_trend} | 4h: {change_4h:+.2f}%")
                return True
        except Exception as e:
            self.log(f"BTC Error: {e}", "ERROR")
            return False

    def get_all_tickers(self):
        """جلب بيانات جميع العملات"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return pd.DataFrame(r.json())
            return None
        except Exception as e:
            self.log(f"Tickers Error: {e}", "ERROR")
            return None

    def get_klines(self, symbol, interval='15m', limit=60):
        """جلب الشموع"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': symbol, 'interval': interval, 'limit': limit}
            r = requests.get(url, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data, columns=[
                    'time', 'open', 'high', 'low', 'close', 'vol',
                    'close_time', 'quote_vol', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                numeric_cols = ['open', 'high', 'low', 'close', 'vol', 'quote_vol', 'taker_buy_base', 'taker_buy_quote']
                df[numeric_cols] = df[numeric_cols].astype(float)
                return df
            return None
        except:
            return None

    def calculate_rsi(self, df, period=14):
        """حساب RSI"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, df):
        """حساب MACD"""
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    def analyze_buy_pressure(self, df):
        """تحليل ضغط الشراء"""
        # آخر 3 شموع
        recent = df.iloc[-3:]
        total_vol = recent['vol'].sum()
        taker_buy = recent['taker_buy_base'].sum()

        if total_vol == 0:
            return 0.5

        return taker_buy / total_vol

    def analyze_candle(self, df):
        """تحليل الشمعة الحالية"""
        c = df.iloc[-1]
        body = c['close'] - c['open']
        full_range = c['high'] - c['low']

        is_green = body > 0
        body_ratio = abs(body) / (full_range + 1e-10)

        # شمعة خضراء قوية
        strong_green = is_green and body_ratio > 0.6

        # مطرقة (wick سفلي طويل)
        lower_wick = min(c['open'], c['close']) - c['low']
        hammer = lower_wick > abs(body) * 2

        return {
            "is_green": is_green,
            "strong_green": strong_green,
            "hammer": hammer,
            "body_ratio": body_ratio
        }

    def calculate_score(self, vol_ratio, buy_pressure, rsi, macd_hist, candle, price_change):
        """
        حساب نقاط الإشارة
        """
        score = 0
        reasons = []

        # 1. تحليل الحجم (0-30 نقطة)
        if vol_ratio >= self.CONFIG["VOLUME_SPIKE_WHALE"]:
            score += 30
            reasons.append(f"🔥 حجم ضخم {vol_ratio:.1f}x")
        elif vol_ratio >= self.CONFIG["VOLUME_SPIKE_STRONG"]:
            score += 22
            reasons.append(f"📈 حجم عالي {vol_ratio:.1f}x")
        elif vol_ratio >= self.CONFIG["VOLUME_SPIKE_MIN"]:
            score += 15
            reasons.append(f"📊 حجم مرتفع {vol_ratio:.1f}x")

        # 2. ضغط الشراء (0-25 نقطة)
        if buy_pressure >= self.CONFIG["BUY_PRESSURE_WHALE"]:
            score += 25
            reasons.append(f"💪 ضغط شراء {buy_pressure*100:.0f}%")
        elif buy_pressure >= self.CONFIG["BUY_PRESSURE_STRONG"]:
            score += 18
            reasons.append(f"📗 شراء قوي {buy_pressure*100:.0f}%")
        elif buy_pressure >= self.CONFIG["BUY_PRESSURE_MIN"]:
            score += 10
            reasons.append(f"📈 شراء إيجابي {buy_pressure*100:.0f}%")

        # 3. RSI (0-15 نقطة)
        if rsi < 25:
            score += 15
            reasons.append(f"🔄 RSI منخفض جداً {rsi:.0f}")
        elif rsi < 35:
            score += 12
            reasons.append(f"📉 RSI منخفض {rsi:.0f}")
        elif rsi < 45:
            score += 8
            reasons.append(f"📊 RSI متوسط {rsi:.0f}")
        elif rsi > 70:
            score -= 10  # خصم للـ overbought
            reasons.append(f"⚠️ RSI مرتفع {rsi:.0f}")

        # 4. MACD (0-15 نقطة)
        if macd_hist > 0:
            score += 15
            reasons.append("✨ MACD إيجابي")
        elif macd_hist > -0.001:
            score += 8
            reasons.append("📈 MACD يتحسن")

        # 5. الشمعة (0-10 نقطة)
        if candle["strong_green"]:
            score += 10
            reasons.append("🟢 شمعة خضراء قوية")
        elif candle["hammer"]:
            score += 10
            reasons.append("🔨 نمط المطرقة")
        elif candle["is_green"]:
            score += 5
            reasons.append("📗 شمعة خضراء")

        # 6. تغير السعر (0-10 نقطة)
        if -5 < price_change < 0:
            score += 10
            reasons.append(f"💰 تراجع طفيف {price_change:.1f}%")
        elif -10 < price_change < -5:
            score += 8
            reasons.append(f"📉 تراجع متوسط {price_change:.1f}%")
        elif 0 < price_change < 5:
            score += 5
            reasons.append(f"📈 ارتفاع خفيف {price_change:.1f}%")

        # 7. تعديل BTC
        if self.btc_trend == "strong_up":
            score += 8
            reasons.append("₿ BTC صاعد")
        elif self.btc_trend == "up":
            score += 4
        elif self.btc_trend == "strong_down":
            score -= 15
            reasons.append("⚠️ BTC هابط!")
        elif self.btc_trend == "down":
            score -= 8

        return max(0, score), reasons

    def calculate_targets(self, price, vol_ratio, score):
        """حساب الأهداف"""
        # نسبة الربح بناءً على قوة الإشارة
        if score >= self.CONFIG["WHALE_SCORE"]:
            tp1_pct, tp2_pct, tp3_pct = 3.0, 6.0, 10.0
            sl_pct = 4.0
        elif score >= self.CONFIG["STRONG_SCORE"]:
            tp1_pct, tp2_pct, tp3_pct = 2.5, 5.0, 8.0
            sl_pct = 3.5
        else:
            tp1_pct, tp2_pct, tp3_pct = 2.0, 4.0, 6.0
            sl_pct = 3.0

        return {
            "tp1": round(price * (1 + tp1_pct/100), 8),
            "tp2": round(price * (1 + tp2_pct/100), 8),
            "tp3": round(price * (1 + tp3_pct/100), 8),
            "sl": round(price * (1 - sl_pct/100), 8),
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "tp3_pct": tp3_pct,
            "sl_pct": sl_pct
        }

    def is_on_cooldown(self, symbol):
        """التحقق من الـ cooldown"""
        if symbol in self.signal_cooldown:
            elapsed = (datetime.now() - self.signal_cooldown[symbol]).total_seconds()
            if elapsed < self.CONFIG["COOLDOWN_SECONDS"]:
                return True
        return False

    def format_signal(self, symbol, price, score, reasons, targets, vol_ratio, buy_pressure):
        """تنسيق رسالة الإشارة"""
        # تحديد نوع الإشارة
        if score >= self.CONFIG["WHALE_SCORE"]:
            signal_type = "🐋🐋🐋 WHALE ALERT"
            strength = "قوية جداً"
        elif score >= self.CONFIG["STRONG_SCORE"]:
            signal_type = "🐋🐋 STRONG SIGNAL"
            strength = "قوية"
        else:
            signal_type = "🐋 SIGNAL"
            strength = "متوسطة"

        reasons_text = "\n".join([f"  • {r}" for r in reasons[:5]])

        msg = f"""
{signal_type}

<b>#{symbol}</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>Score:</b> {score}/100 ({strength})
📈 <b>Volume:</b> {vol_ratio:.1f}x
💰 <b>Buy Pressure:</b> {buy_pressure*100:.0f}%
₿ <b>BTC:</b> {self.btc_trend}

<b>تحليل:</b>
{reasons_text}

━━━━━━━━━━━━━━━━━━━━
💵 <b>Entry:</b> ${price:.8f}
🎯 <b>TP1:</b> +{targets['tp1_pct']}% (${targets['tp1']:.8f})
🎯 <b>TP2:</b> +{targets['tp2_pct']}% (${targets['tp2']:.8f})
🎯 <b>TP3:</b> +{targets['tp3_pct']}% (${targets['tp3']:.8f})
🛡 <b>SL:</b> -{targets['sl_pct']}% (${targets['sl']:.8f})
━━━━━━━━━━━━━━━━━━━━

⚠️ <i>استخدم 2-5% فقط من رأس المال</i>
⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        return msg

    def scan_market(self):
        """المسح الرئيسي"""
        self.log("=" * 50)
        self.log("🐋 Whale Hunter V3 Started - Balanced Edition")
        self.log(f"Config: Vol≥{self.CONFIG['VOLUME_SPIKE_MIN']}x | Buy≥{self.CONFIG['BUY_PRESSURE_MIN']*100}% | Score≥{self.CONFIG['MIN_SCORE']}")
        self.log("=" * 50)

        self.send_telegram(f"""
🐋 <b>Whale Hunter V3 Active</b>

⚙️ <b>Settings:</b>
• Volume Spike: ≥{self.CONFIG['VOLUME_SPIKE_MIN']}x
• Buy Pressure: ≥{self.CONFIG['BUY_PRESSURE_MIN']*100:.0f}%
• Min Score: {self.CONFIG['MIN_SCORE']}/100
• Scan Interval: {self.CONFIG['SCAN_INTERVAL']}s

🔍 Scanning started...
        """)

        scan_count = 0
        candidates_found = 0

        while True:
            try:
                scan_count += 1
                self.last_scan_time = datetime.now()
                self.log(f"\n{'='*40}")
                self.log(f"🔍 SCAN #{scan_count}")

                # تحديث BTC
                self.get_btc_status()

                # جلب العملات
                tickers = self.get_all_tickers()

                if tickers is None or tickers.empty:
                    self.log("Failed to get tickers", "ERROR")
                    time.sleep(30)
                    continue

                # تحويل الأنواع
                tickers['quoteVolume'] = tickers['quoteVolume'].astype(float)
                tickers['priceChangePercent'] = tickers['priceChangePercent'].astype(float)
                tickers['lastPrice'] = tickers['lastPrice'].astype(float)

                # الفلترة
                suspects = tickers[
                    (tickers['symbol'].str.endswith('USDT')) &
                    (~tickers['symbol'].str.contains('UP|DOWN|BULL|BEAR')) &
                    (tickers['quoteVolume'] > self.CONFIG["MIN_VOLUME_USDT"]) &
                    (tickers['priceChangePercent'] > -25) &
                    (tickers['priceChangePercent'] < 20)
                ]

                # ترتيب حسب الحجم
                suspects = suspects.nlargest(150, 'quoteVolume')
                suspect_list = suspects['symbol'].tolist()
                self.coins_scanned = len(suspect_list)

                self.log(f"📊 Analyzing {len(suspect_list)} coins...")

                current_candidates = []

                for symbol in suspect_list:
                    try:
                        # تجاوز العملات في cooldown
                        if self.is_on_cooldown(symbol):
                            continue

                        df = self.get_klines(symbol)

                        if df is None or len(df) < 30:
                            continue

                        # حساب Volume Ratio
                        vol_ma = df['vol'].rolling(window=20).mean()
                        current_vol = df['vol'].iloc[-1]
                        avg_vol = vol_ma.iloc[-2]

                        if pd.isna(avg_vol) or avg_vol <= 0:
                            continue

                        vol_ratio = current_vol / avg_vol

                        # فلتر الحجم الأولي
                        if vol_ratio < self.CONFIG["VOLUME_SPIKE_MIN"]:
                            continue

                        # ✅ وجدنا عملة بحجم مرتفع!
                        candidates_found += 1

                        # تحليلات إضافية
                        buy_pressure = self.analyze_buy_pressure(df)

                        # فلتر ضغط الشراء
                        if buy_pressure < self.CONFIG["BUY_PRESSURE_MIN"]:
                            self.log(f"  ❌ {symbol}: Vol {vol_ratio:.1f}x but BuyPressure {buy_pressure*100:.0f}% < {self.CONFIG['BUY_PRESSURE_MIN']*100}%")
                            continue

                        # RSI
                        rsi = self.calculate_rsi(df)
                        current_rsi = rsi.iloc[-1]

                        # MACD
                        macd, signal, histogram = self.calculate_macd(df)
                        macd_hist = histogram.iloc[-1]

                        # الشمعة
                        candle = self.analyze_candle(df)

                        # تغير السعر
                        price_change = ((df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6]) * 100

                        # حساب النقاط
                        score, reasons = self.calculate_score(
                            vol_ratio, buy_pressure, current_rsi,
                            macd_hist, candle, price_change
                        )

                        self.log(f"  📊 {symbol}: Vol={vol_ratio:.1f}x | Buy={buy_pressure*100:.0f}% | RSI={current_rsi:.0f} | Score={score}")

                        # فلتر النقاط
                        if score < self.CONFIG["MIN_SCORE"]:
                            self.log(f"  ❌ Score {score} < {self.CONFIG['MIN_SCORE']}")
                            continue

                        # ✅ إشارة صالحة!
                        price = df['close'].iloc[-1]
                        targets = self.calculate_targets(price, vol_ratio, score)

                        signal_data = {
                            "symbol": symbol,
                            "price": price,
                            "score": score,
                            "reasons": reasons,
                            "vol_ratio": vol_ratio,
                            "buy_pressure": buy_pressure,
                            "rsi": current_rsi,
                            "targets": targets,
                            "btc_trend": self.btc_trend,
                            "time": datetime.now(),
                            "status": "active"
                        }

                        # إضافة للسجل
                        signals_history.insert(0, signal_data)
                        if len(signals_history) > 50:
                            signals_history.pop()

                        # تحديث cooldown
                        self.signal_cooldown[symbol] = datetime.now()

                        # إرسال التنبيه
                        msg = self.format_signal(
                            symbol, price, score, reasons,
                            targets, vol_ratio, buy_pressure
                        )
                        self.send_telegram(msg)

                        self.log(f"  ✅ SIGNAL SENT: {symbol} | Score: {score}")

                        # حفظ في قاعدة البيانات
                        if signals_collection is not None:
                            try:
                                signals_collection.insert_one({
                                    **signal_data,
                                    "time": datetime.now()
                                })
                            except:
                                pass

                        current_candidates.append(symbol)

                        # تأخير صغير
                        time.sleep(0.1)

                    except Exception as e:
                        continue

                # ملخص المسح
                self.log(f"\n📈 Scan #{scan_count} Complete:")
                self.log(f"   • Coins analyzed: {self.coins_scanned}")
                self.log(f"   • Volume spikes found: {candidates_found}")
                self.log(f"   • Signals sent this scan: {len(current_candidates)}")
                self.log(f"   • Total signals: {len(signals_history)}")

                # إذا لم نجد شيئاً، نخفض المعايير مؤقتاً
                if len(signals_history) == 0 and scan_count > 5:
                    self.log("⚠️ No signals yet - checking if criteria too strict...")

                # الانتظار
                time.sleep(self.CONFIG["SCAN_INTERVAL"])

            except Exception as e:
                self.log(f"Scanner Error: {e}", "ERROR")
                time.sleep(30)

# إنشاء المحرك
whale_hunter = WhaleHunterV3()

# تشغيل المسح في Thread
scanner_thread = threading.Thread(target=whale_hunter.scan_market)
scanner_thread.daemon = True
scanner_thread.start()

# ==========================================
# 3. EMAIL SERVICE (لا تغيير)
# ==========================================
def send_email(to, subject, html_content):
    print(f"📧 جاري محاولة إرسال إيميل إلى: {to}")

    if not BREVO_API_KEY:
        print("❌ خطأ: BREVO_API_KEY غير موجود في الإعدادات!")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    payload = {
        "sender": {"name": "TRADOVIP Team", "email": SENDER_EMAIL},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        print(f"📡 حالة الاستجابة: {response.status_code}")
        if response.status_code == 201:
            print("✅ تم الإرسال بنجاح!")
        else:
            print(f"❌ فشل الإرسال. رسالة Brevo: {response.text}")
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")

# ==========================================
# 4. UI STYLES
# ==========================================
SHARED_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    :root {
        --primary: #0f172a;
        --accent: #8b5cf6;
        --bg: #0f172a;
        --card: #1e293b;
        --text: #f1f5f9;
        --text-secondary: #94a3b8;
        --success: #10b981;
        --danger: #ef4444;
        --warning: #f59e0b;
    }
    * { box-sizing: border-box; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-top: 60px; line-height: 1.5; }
    .navbar { position: fixed; top: 0; left: 0; right: 0; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); height: 60px; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; z-index: 1000; }
    .logo { font-size: 1.25rem; font-weight: 800; color: var(--accent); text-decoration: none; }
    .container { width: 100%; max-width: 600px; margin: 0 auto; padding: 20px; }
    .card { background: var(--card); padding: 20px; border-radius: 16px; border: 1px solid #334155; margin-bottom: 15px; }
    h2 { font-size: 1.4rem; margin-bottom: 15px; }
    p { color: var(--text-secondary); }
    label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; color: var(--text-secondary); }
    input { width: 100%; padding: 14px 16px; margin-bottom: 16px; border: 1px solid #334155; border-radius: 12px; font-size: 16px; background: #0f172a; color: var(--text); }
    input:focus { outline: none; border-color: var(--accent); }
    .btn { display: block; width: 100%; background: var(--accent); color: white; padding: 16px; border: none; border-radius: 12px; font-weight: 600; font-size: 1rem; cursor: pointer; text-align: center; text-decoration: none; }
    .btn:hover { background: #7c3aed; }
    .btn-outline { background: transparent; border: 1px solid #334155; color: var(--text); }

    .signal-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 16px; padding: 20px; margin-bottom: 15px; position: relative; overflow: hidden; }
    .signal-card::before { content: '🐋'; position: absolute; right: -15px; bottom: -15px; font-size: 80px; opacity: 0.05; }
    .signal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .signal-symbol { font-size: 1.2rem; font-weight: 800; color: var(--accent); }
    .signal-score { padding: 5px 10px; border-radius: 15px; font-size: 0.8rem; font-weight: 700; }
    .score-high { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .score-medium { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
    .score-low { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }

    .signal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0; }
    .signal-stat { background: rgba(139, 92, 246, 0.1); padding: 10px; border-radius: 8px; text-align: center; }
    .stat-label { font-size: 0.7rem; color: var(--text-secondary); }
    .stat-value { font-size: 0.95rem; font-weight: 700; margin-top: 3px; }

    .targets { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 12px; }
    .target { text-align: center; padding: 8px 4px; border-radius: 6px; background: rgba(255,255,255,0.03); }
    .target.tp { border-top: 2px solid var(--success); }
    .target.sl { border-top: 2px solid var(--danger); }
    .target-label { font-size: 0.65rem; color: var(--text-secondary); }
    .target-value { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }

    .signal-time { font-size: 0.7rem; color: var(--text-secondary); margin-top: 10px; text-align: right; }

    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
    .stat-card { background: var(--card); padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #334155; }
    .stat-card .value { font-size: 1.5rem; font-weight: 800; color: var(--accent); }
    .stat-card .label { font-size: 0.75rem; color: var(--text-secondary); margin-top: 5px; }

    .log-box { background: #0d1117; border-radius: 12px; padding: 15px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.75rem; border: 1px solid #30363d; }
    .log-entry { padding: 3px 0; border-bottom: 1px solid #21262d; }
    .log-info { color: #58a6ff; }
    .log-warn { color: #d29922; }
    .log-error { color: #f85149; }

    .btc-badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }
    .btc-up { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .btc-down { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .btc-neutral { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }

    .empty-state { text-align: center; padding: 50px 20px; }
    .empty-icon { font-size: 50px; margin-bottom: 15px; }

    .alert { padding: 15px; border-radius: 12px; margin-bottom: 20px; }
    .error { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); text-align: center; }
</style>
"""

# ==========================================
# 5. ROUTES
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TRADOVIP V3</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a><a href="/login" style="color:var(--text);text-decoration:none;font-weight:600;">Login</a></nav>
    <div class="container" style="text-align:center;padding-top:40px;">
        <h1 style="font-size:2rem;margin-bottom:10px;">Whale Hunter <span style="color:var(--accent)">V3</span></h1>
        <p>Balanced Edition - More signals, Same quality</p>
        <div class="stats-grid" style="margin:30px 0;">
            <div class="stat-card"><div class="value">1.8x</div><div class="label">Min Volume</div></div>
            <div class="stat-card"><div class="value">48%</div><div class="label">Min Buy</div></div>
            <div class="stat-card"><div class="value">35+</div><div class="label">Min Score</div></div>
        </div>
        <a href="/signup" class="btn" style="margin-bottom:15px;">Start Free</a>
        <a href="/login" class="btn btn-outline">Login</a>
    </div></body></html>""")

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        user = users_collection.find_one({"email": email}) if users_collection else None
        if user and check_password_hash(user['password'], password):
            if user.get('status') == 'pending':
                session['pending_email'] = email
                return redirect('/verify')
            session['user_id'] = str(user['_id'])
            return redirect('/dashboard')
        else:
            msg = "<div class='alert error'>Invalid credentials</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a></nav>
    <div class="container"><div class="card"><h2 style="text-align:center;">Login</h2>{msg}
    <form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn">Login</button></form>
    <p style="text-align:center;margin-top:20px;"><a href="/signup" style="color:var(--accent);">Create Account</a></p></div></div></body></html>""")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        if users_collection is not None:
            if users_collection.find_one({"email": email}):
                msg = "<div class='alert error'>Email taken</div>"
            else:
                otp = str(random.randint(100000, 999999))
                users_collection.insert_one({
                    "email": email,
                    "password": generate_password_hash(password),
                    "status": "pending",
                    "otp": otp,
                    "created_at": datetime.utcnow()
                })
                send_email(email, "Verify Code", f"<h1>{otp}</h1>")
                session['pending_email'] = email
                return redirect('/verify')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sign Up</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a></nav>
    <div class="container"><div class="card"><h2 style="text-align:center;">Sign Up</h2>{msg}
    <form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn">Sign Up</button></form>
    <p style="text-align:center;margin-top:20px;"><a href="/login" style="color:var(--accent);">Already have account?</a></p></div></div></body></html>""")

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_email' not in session:
        return redirect('/signup')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code', '')
        user = users_collection.find_one({"email": session['pending_email']}) if users_collection else None
        if user and user.get('otp') == code:
            users_collection.update_one({"email": session['pending_email']}, {"$set": {"status": "active"}})
            session['user_id'] = str(user['_id'])
            return redirect('/dashboard')
        else:
            msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verify</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a></nav>
    <div class="container"><div class="card" style="text-align:center;"><h2>Verify Email</h2><p>Check your inbox for the code</p>{msg}
    <form method="POST"><input type="text" name="code" maxlength="6" style="text-align:center;font-size:24px;letter-spacing:8px;" required><button type="submit" class="btn">Verify</button></form></div></div></body></html>""")

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        user = users_collection.find_one({"email": email}) if users_collection else None
        if user:
            code = str(random.randint(100000, 999999))
            users_collection.update_one({"email": email}, {"$set": {"reset_code": code}})
            send_email(email, "Reset Password", f"<h1>{code}</h1>")
            session['reset_email'] = email
            return redirect('/reset-password')
        else:
            msg = "<div class='alert error'>Email not found</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Forgot</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a></nav>
    <div class="container"><div class="card"><h2>Reset Password</h2>{msg}
    <form method="POST"><input type="email" name="email" required placeholder="Your email"><button type="submit" class="btn">Send Code</button></form></div></div></body></html>""")

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        return redirect('/forgot-password')
    msg = ""
    if request.method == 'POST':
        code = request.form.get('code', '')
        pwd = request.form.get('password', '')
        user = users_collection.find_one({"email": session['reset_email']}) if users_collection else None
        if user and user.get('reset_code') == code:
            users_collection.update_one({"email": session['reset_email']}, {"$set": {"password": generate_password_hash(pwd), "reset_code": None}})
            return redirect('/login')
        else:
            msg = "<div class='alert error'>Invalid Code</div>"
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Reset</title>{SHARED_STYLE}</head><body>
    <nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP V3</a></nav>
    <div class="container"><div class="card"><h2>New Password</h2>{msg}
    <form method="POST"><input type="text" name="code" placeholder="Code" required style="text-align:center;letter-spacing:5px;"><input type="password" name="password" placeholder="New Password" required><button type="submit" class="btn">Change</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    # حالة BTC
    btc = whale_hunter.btc_trend
    btc_class = "btc-up" if "up" in btc else ("btc-down" if "down" in btc else "btc-neutral")

    # بناء الإشارات
    signals_html = ""
    if not signals_history:
        signals_html = """
        <div class="empty-state">
            <div class="empty-icon">🐋</div>
            <h3>Scanning Market...</h3>
            <p style="color:var(--text-secondary);">Signals will appear here when whales are detected.<br>Scan runs every 60 seconds.</p>
        </div>
        """
    else:
        for s in signals_history[:15]:
            score = s.get('score', 0)
            if score >= 70:
                score_class = "score-high"
            elif score >= 55:
                score_class = "score-medium"
            else:
                score_class = "score-low"

            targets = s.get('targets', {})
            signal_time = s.get('time', datetime.now())
            time_str = signal_time.strftime("%H:%M") if isinstance(signal_time, datetime) else "N/A"

            signals_html += f"""
            <div class="signal-card">
                <div class="signal-header">
                    <span class="signal-symbol">🐋 {s.get('symbol', 'N/A')}</span>
                    <span class="signal-score {score_class}">{score}/100</span>
                </div>
                <div class="signal-grid">
                    <div class="signal-stat">
                        <div class="stat-label">Entry</div>
                        <div class="stat-value">${s.get('price', 0):.6f}</div>
                    </div>
                    <div class="signal-stat">
                        <div class="stat-label">Volume</div>
                        <div class="stat-value">{s.get('vol_ratio', 0):.1f}x</div>
                    </div>
                    <div class="signal-stat">
                        <div class="stat-label">Buy Pressure</div>
                        <div class="stat-value" style="color:var(--success);">{s.get('buy_pressure', 0)*100:.0f}%</div>
                    </div>
                    <div class="signal-stat">
                        <div class="stat-label">RSI</div>
                        <div class="stat-value">{s.get('rsi', 0):.0f}</div>
                    </div>
                </div>
                <div class="targets">
                    <div class="target tp"><div class="target-label">TP1</div><div class="target-value" style="color:var(--success);">+{targets.get('tp1_pct', 0)}%</div></div>
                    <div class="target tp"><div class="target-label">TP2</div><div class="target-value" style="color:var(--success);">+{targets.get('tp2_pct', 0)}%</div></div>
                    <div class="target tp"><div class="target-label">TP3</div><div class="target-value" style="color:var(--success);">+{targets.get('tp3_pct', 0)}%</div></div>
                    <div class="target sl"><div class="target-label">SL</div><div class="target-value" style="color:var(--danger);">-{targets.get('sl_pct', 0)}%</div></div>
                </div>
                <div class="signal-time">⏰ {time_str}</div>
            </div>
            """

    # سجل المسح
    logs_html = ""
    for log in list(scan_logs)[-10:]:
        level_class = f"log-{log['level'].lower()}"
        logs_html += f'<div class="log-entry {level_class}">[{log["time"]}] {log["message"]}</div>'

    return render_template_string(f"""<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    {SHARED_STYLE}
    <meta http-equiv="refresh" content="30">
    </head><body>
    <nav class="navbar">
        <span class="logo">🐋 TRADOVIP V3</span>
        <a href="/logout" style="color:var(--danger);text-decoration:none;font-weight:600;">Logout</a>
    </nav>
    <div class="container">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">Live Signals</h2>
            <div style="display:flex;gap:8px;">
                <span class="btc-badge {btc_class}">₿ {btc.upper()}</span>
                <span style="background:rgba(239,68,68,0.2);color:#ef4444;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;">🔴 LIVE</span>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="value">{len(signals_history)}</div><div class="label">Signals</div></div>
            <div class="stat-card"><div class="value">{whale_hunter.coins_scanned}</div><div class="label">Coins Scanned</div></div>
            <div class="stat-card"><div class="value">60s</div><div class="label">Interval</div></div>
        </div>

        {signals_html}

        <div class="card">
            <h3 style="margin-bottom:10px;font-size:0.9rem;">📋 Scan Log</h3>
            <div class="log-box">{logs_html if logs_html else '<div style="color:var(--text-secondary);">Waiting for scan...</div>'}</div>
        </div>

        <p style="text-align:center;font-size:0.75rem;color:var(--text-secondary);margin-top:20px;">
            ⚠️ Not financial advice. Use 2-5% per trade.
        </p>
    </div></body></html>""")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================================
# 6. API
# ==========================================
@app.route('/api/signals')
def api_signals():
    return {
        "status": "ok",
        "btc": whale_hunter.btc_trend,
        "btc_price": whale_hunter.btc_price,
        "signals_count": len(signals_history),
        "coins_scanned": whale_hunter.coins_scanned,
        "config": whale_hunter.CONFIG,
        "signals": [
            {
                "symbol": s.get("symbol"),
                "price": s.get("price"),
                "score": s.get("score"),
                "vol_ratio": s.get("vol_ratio"),
                "buy_pressure": s.get("buy_pressure"),
                "targets": s.get("targets"),
                "time": s.get("time").isoformat() if s.get("time") else None
            }
            for s in signals_history[:10]
        ]
    }

@app.route('/api/logs')
def api_logs():
    return {
        "logs": list(scan_logs)[-30:]
    }

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
