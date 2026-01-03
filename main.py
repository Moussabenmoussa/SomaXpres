
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
from datetime import datetime, timedelta
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque

# ==========================================
# 1. SYSTEM CONFIGURATION (لا تغيير)
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "whale_hunter_v1")

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
    except: print("❌ Database Error")

# Services
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@tradovip.com")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

signals_history = []
performance_tracker = {
    "total_signals": 0,
    "tp1_hit": 0,
    "tp2_hit": 0,
    "sl_hit": 0,
    "pending": 0
}

# ==========================================
# 2. PROFESSIONAL WHALE HUNTING ENGINE V2.0
# ==========================================

class WhaleHunterPro:
    """
    محرك اكتشاف الحيتان الاحترافي
    يستخدم 7 مؤشرات مختلفة + تحليل BTC + تحليل حجم الشراء/البيع
    """

    def __init__(self):
        self.btc_trend = "neutral"
        self.btc_price = 0
        self.market_fear_greed = 50
        self.recent_signals = deque(maxlen=50)
        self.blacklist = set()  # عملات يجب تجنبها
        self.MIN_VOLUME_USDT = 5_000_000  # 5 مليون دولار كحد أدنى
        self.VOLUME_SPIKE_MULTIPLIER = 2.5  # 250% من المتوسط
        self.signal_cooldown = {}  # منع التكرار

    def send_telegram(self, message):
        """إرسال إشعار تيليجرام"""
        if not BOT_TOKEN or not CHAT_ID:
            return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except:
            pass

    def get_btc_status(self):
        """
        تحليل حالة Bitcoin - أهم عامل في السوق!
        إذا BTC يهبط بقوة، لا نعطي أي إشارة شراء
        """
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 24}
            r = requests.get(url, params=params, timeout=10)

            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'x', 'y', 'z', 'a', 'b', 'c'])
                df['close'] = df['close'].astype(float)
                df['open'] = df['open'].astype(float)

                self.btc_price = df['close'].iloc[-1]

                # حساب التغير في آخر 4 ساعات و 24 ساعة
                change_4h = ((df['close'].iloc[-1] - df['close'].iloc[-4]) / df['close'].iloc[-4]) * 100
                change_24h = ((df['close'].iloc[-1] - df['open'].iloc[0]) / df['open'].iloc[0]) * 100

                # حساب EMA 20
                df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
                above_ema = df['close'].iloc[-1] > df['ema20'].iloc[-1]

                # تحديد الترند
                if change_4h < -3 or change_24h < -5:
                    self.btc_trend = "strong_down"
                elif change_4h < -1.5 or change_24h < -3:
                    self.btc_trend = "down"
                elif change_4h > 2 and above_ema:
                    self.btc_trend = "strong_up"
                elif change_4h > 0.5 and above_ema:
                    self.btc_trend = "up"
                else:
                    self.btc_trend = "neutral"

                return True
        except Exception as e:
            print(f"BTC Status Error: {e}")
            return False

    def get_all_tickers(self):
        """جلب بيانات جميع العملات"""
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return pd.DataFrame(r.json())
            return None
        except:
            return None

    def get_klines(self, symbol, interval='15m', limit=100):
        """جلب الشموع مع بيانات إضافية"""
        url = "https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        try:
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
        """حساب RSI بشكل صحيح"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # تجنب القسمة على صفر
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, df):
        """حساب MACD"""
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    def calculate_bollinger(self, df, period=20):
        """حساب Bollinger Bands"""
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return upper, sma, lower

    def calculate_vwap(self, df):
        """حساب VWAP"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['vol']).cumsum() / df['vol'].cumsum()
        return vwap

    def calculate_obv(self, df):
        """حساب On-Balance Volume"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['vol'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['vol'].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)

    def analyze_buy_sell_pressure(self, df):
        """
        تحليل ضغط الشراء vs البيع
        باستخدام Taker Buy Volume من Binance
        """
        total_vol = df['vol'].iloc[-5:].sum()
        taker_buy = df['taker_buy_base'].iloc[-5:].sum()

        if total_vol == 0:
            return 0.5

        buy_ratio = taker_buy / total_vol
        return buy_ratio

    def analyze_candle_pattern(self, df):
        """
        تحليل أنماط الشموع
        يكتشف: Hammer, Bullish Engulfing, Morning Star
        """
        patterns = []

        # آخر 3 شمعات
        c1 = df.iloc[-3]  # قبل قبل الأخيرة
        c2 = df.iloc[-2]  # قبل الأخيرة
        c3 = df.iloc[-1]  # الحالية

        # Hammer (مطرقة) - إشارة انعكاس صعودية
        body = abs(c3['close'] - c3['open'])
        lower_wick = min(c3['open'], c3['close']) - c3['low']
        upper_wick = c3['high'] - max(c3['open'], c3['close'])

        if lower_wick > body * 2 and upper_wick < body * 0.5:
            patterns.append("HAMMER")

        # Bullish Engulfing (ابتلاع صعودي)
        if (c2['close'] < c2['open'] and  # شمعة حمراء
            c3['close'] > c3['open'] and  # شمعة خضراء
            c3['open'] < c2['close'] and  # فتحت تحت إغلاق السابقة
            c3['close'] > c2['open']):    # أغلقت فوق فتح السابقة
            patterns.append("BULLISH_ENGULFING")

        # Morning Star (نجمة الصباح)
        body1 = abs(c1['close'] - c1['open'])
        body2 = abs(c2['close'] - c2['open'])
        body3 = abs(c3['close'] - c3['open'])

        if (c1['close'] < c1['open'] and  # أولى حمراء كبيرة
            body1 > body2 * 2 and          # جسم كبير
            body2 < body1 * 0.3 and        # وسطى صغيرة
            c3['close'] > c3['open'] and   # ثالثة خضراء
            c3['close'] > (c1['open'] + c1['close']) / 2):  # أغلقت فوق منتصف الأولى
            patterns.append("MORNING_STAR")

        return patterns

    def calculate_signal_score(self, df, buy_pressure, patterns):
        """
        نظام تسجيل النقاط للإشارة
        كلما زادت النقاط، كلما كانت الإشارة أقوى
        """
        score = 0
        reasons = []

        # 1. تحليل الحجم (0-25 نقطة)
        vol_ma = df['vol'].rolling(window=20).mean()
        current_vol = df['vol'].iloc[-1]
        avg_vol = vol_ma.iloc[-2]

        if pd.notna(avg_vol) and avg_vol > 0:
            vol_ratio = current_vol / avg_vol
            if vol_ratio >= 4:
                score += 25
                reasons.append(f"🔥 حجم ضخم {vol_ratio:.1f}x")
            elif vol_ratio >= 3:
                score += 20
                reasons.append(f"📈 حجم عالي {vol_ratio:.1f}x")
            elif vol_ratio >= 2.5:
                score += 15
                reasons.append(f"📊 حجم مرتفع {vol_ratio:.1f}x")

        # 2. ضغط الشراء (0-20 نقطة)
        if buy_pressure >= 0.7:
            score += 20
            reasons.append("💪 ضغط شراء قوي جداً")
        elif buy_pressure >= 0.6:
            score += 15
            reasons.append("📗 ضغط شراء قوي")
        elif buy_pressure >= 0.55:
            score += 10
            reasons.append("📈 ضغط شراء إيجابي")

        # 3. RSI (0-15 نقطة)
        rsi = self.calculate_rsi(df)
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        if prev_rsi < 30 and current_rsi > 30:
            score += 15
            reasons.append("🔄 خروج من Oversold")
        elif current_rsi < 35 and current_rsi > prev_rsi:
            score += 10
            reasons.append("📉 RSI منخفض + صاعد")
        elif current_rsi < 45 and current_rsi > prev_rsi:
            score += 5
            reasons.append("📊 RSI متوسط صاعد")

        # 4. MACD (0-15 نقطة)
        macd, signal, histogram = self.calculate_macd(df)

        if histogram.iloc[-1] > 0 and histogram.iloc[-2] < 0:
            score += 15
            reasons.append("✨ MACD تقاطع صعودي")
        elif histogram.iloc[-1] > histogram.iloc[-2] and histogram.iloc[-1] > 0:
            score += 10
            reasons.append("📈 MACD إيجابي متصاعد")

        # 5. Bollinger Bands (0-10 نقطة)
        upper, middle, lower = self.calculate_bollinger(df)
        close = df['close'].iloc[-1]

        if close <= lower.iloc[-1] * 1.02:
            score += 10
            reasons.append("⬇️ عند الحد السفلي")
        elif close < middle.iloc[-1]:
            score += 5
            reasons.append("📉 تحت المتوسط")

        # 6. أنماط الشموع (0-15 نقطة)
        if "MORNING_STAR" in patterns:
            score += 15
            reasons.append("⭐ نجمة الصباح")
        elif "BULLISH_ENGULFING" in patterns:
            score += 12
            reasons.append("🟢 ابتلاع صعودي")
        elif "HAMMER" in patterns:
            score += 10
            reasons.append("🔨 مطرقة")

        # 7. BTC Correlation (تعديل)
        if self.btc_trend == "strong_up":
            score += 10
            reasons.append("₿ BTC صاعد بقوة")
        elif self.btc_trend == "up":
            score += 5
            reasons.append("₿ BTC إيجابي")
        elif self.btc_trend == "strong_down":
            score -= 20
            reasons.append("⚠️ BTC هابط!")
        elif self.btc_trend == "down":
            score -= 10
            reasons.append("⚠️ BTC سلبي")

        return score, reasons

    def calculate_targets(self, df, score):
        """
        حساب أهداف ديناميكية بناءً على ATR و قوة الإشارة
        """
        # حساب ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]

        price = df['close'].iloc[-1]
        atr_percent = (atr / price) * 100

        # تعديل الأهداف بناءً على قوة الإشارة
        if score >= 70:
            tp1_mult = 1.5
            tp2_mult = 3.0
            tp3_mult = 5.0
            sl_mult = 1.2
        elif score >= 55:
            tp1_mult = 1.2
            tp2_mult = 2.5
            tp3_mult = 4.0
            sl_mult = 1.0
        else:
            tp1_mult = 1.0
            tp2_mult = 2.0
            tp3_mult = 3.0
            sl_mult = 0.8

        # حساب الأهداف
        tp1 = price * (1 + (atr_percent * tp1_mult / 100))
        tp2 = price * (1 + (atr_percent * tp2_mult / 100))
        tp3 = price * (1 + (atr_percent * tp3_mult / 100))
        sl = price * (1 - (atr_percent * sl_mult / 100))

        # حدود معقولة
        tp1 = min(tp1, price * 1.05)  # Max 5%
        tp2 = min(tp2, price * 1.10)  # Max 10%
        tp3 = min(tp3, price * 1.20)  # Max 20%
        sl = max(sl, price * 0.94)    # Max loss 6%

        return {
            "tp1": round(tp1, 8),
            "tp2": round(tp2, 8),
            "tp3": round(tp3, 8),
            "sl": round(sl, 8),
            "atr_percent": round(atr_percent, 2)
        }

    def is_valid_signal(self, symbol, score):
        """
        فلترة الإشارات لتقليل False Positives
        """
        # الحد الأدنى للنقاط
        if score < 45:
            return False, "نقاط منخفضة"

        # لا إشارات إذا BTC يهبط بقوة
        if self.btc_trend == "strong_down" and score < 70:
            return False, "BTC هابط"

        # منع التكرار (4 ساعات)
        if symbol in self.signal_cooldown:
            last_signal = self.signal_cooldown[symbol]
            if (datetime.now() - last_signal).total_seconds() < 14400:
                return False, "تكرار"

        # تجنب العملات المدرجة في القائمة السوداء
        if symbol in self.blacklist:
            return False, "قائمة سوداء"

        return True, "OK"

    def format_signal_message(self, symbol, price, score, reasons, targets, buy_pressure):
        """
        تنسيق رسالة الإشارة
        """
        # تحديد قوة الإشارة
        if score >= 70:
            strength = "🔥 قوية جداً"
            emoji = "🐋🐋🐋"
        elif score >= 55:
            strength = "💪 قوية"
            emoji = "🐋🐋"
        else:
            strength = "📊 متوسطة"
            emoji = "🐋"

        # تحديد لون ضغط الشراء
        if buy_pressure >= 0.65:
            bp_text = f"🟢 {buy_pressure*100:.0f}%"
        elif buy_pressure >= 0.55:
            bp_text = f"🟡 {buy_pressure*100:.0f}%"
        else:
            bp_text = f"🔴 {buy_pressure*100:.0f}%"

        reasons_text = "\n".join([f"  • {r}" for r in reasons[:5]])

        msg = f"""
{emoji} <b>WHALE SIGNAL DETECTED</b> {emoji}

<b>#{symbol}</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>Signal Score:</b> {score}/100 ({strength})
💰 <b>Buy Pressure:</b> {bp_text}
₿ <b>BTC Status:</b> {self.btc_trend.upper()}

<b>📈 Analysis:</b>
{reasons_text}

━━━━━━━━━━━━━━━━━━━━
💵 <b>Entry:</b> ${price:.6f}
🎯 <b>TP1:</b> ${targets['tp1']:.6f} (+{((targets['tp1']-price)/price*100):.1f}%)
🎯 <b>TP2:</b> ${targets['tp2']:.6f} (+{((targets['tp2']-price)/price*100):.1f}%)
🎯 <b>TP3:</b> ${targets['tp3']:.6f} (+{((targets['tp3']-price)/price*100):.1f}%)
🛡 <b>SL:</b> ${targets['sl']:.6f} (-{((price-targets['sl'])/price*100):.1f}%)
━━━━━━━━━━━━━━━━━━━━

⚠️ <i>Risk Management: Use only 2-5% of capital</i>
⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC
        """
        return msg

    def scan_market(self):
        """
        المسح الرئيسي للسوق
        """
        print("🐋 Whale Hunter Pro V2.0 Started...")
        self.send_telegram("🐋 <b>Whale Hunter Pro V2.0 Active</b>\n\n✅ 7 Indicators Analysis\n✅ BTC Correlation\n✅ Buy/Sell Pressure\n✅ Smart Targeting")

        while True:
            try:
                # تحديث حالة BTC أولاً
                self.get_btc_status()

                # جلب جميع العملات
                tickers = self.get_all_tickers()

                if tickers is not None and not tickers.empty:
                    # تحويل الأنواع
                    tickers['quoteVolume'] = tickers['quoteVolume'].astype(float)
                    tickers['priceChangePercent'] = tickers['priceChangePercent'].astype(float)
                    tickers['lastPrice'] = tickers['lastPrice'].astype(float)

                    # الفلترة الأولية
                    suspects = tickers[
                        (tickers['symbol'].str.endswith('USDT')) &
                        (~tickers['symbol'].str.contains('UP|DOWN|BULL|BEAR')) &  # تجنب Leveraged tokens
                        (tickers['quoteVolume'] > self.MIN_VOLUME_USDT) &
                        (tickers['priceChangePercent'] > -20) &
                        (tickers['priceChangePercent'] < 15) &
                        (tickers['lastPrice'] > 0.00000001)  # تجنب العملات الميتة
                    ]

                    # ترتيب حسب الحجم
                    suspects = suspects.nlargest(100, 'quoteVolume')
                    suspect_list = suspects['symbol'].tolist()

                    print(f"🔍 Analyzing {len(suspect_list)} coins | BTC: {self.btc_trend}")

                    # تحليل كل عملة
                    for symbol in suspect_list:
                        try:
                            df = self.get_klines(symbol)

                            if df is not None and len(df) >= 50:
                                # حساب Volume Spike
                                vol_ma = df['vol'].rolling(window=20).mean()
                                current_vol = df['vol'].iloc[-1]
                                avg_vol = vol_ma.iloc[-2]

                                # شرط الحجم الأساسي
                                if pd.notna(avg_vol) and avg_vol > 0:
                                    vol_ratio = current_vol / avg_vol

                                    # يجب أن يكون الحجم 2.5x على الأقل
                                    if vol_ratio >= self.VOLUME_SPIKE_MULTIPLIER:
                                        # تحليل ضغط الشراء/البيع
                                        buy_pressure = self.analyze_buy_sell_pressure(df)

                                        # يجب أن يكون ضغط الشراء > 52%
                                        if buy_pressure >= 0.52:
                                            # تحليل أنماط الشموع
                                            patterns = self.analyze_candle_pattern(df)

                                            # حساب النقاط
                                            score, reasons = self.calculate_signal_score(df, buy_pressure, patterns)

                                            # التحقق من صلاحية الإشارة
                                            is_valid, reason = self.is_valid_signal(symbol, score)

                                            if is_valid:
                                                price = df['close'].iloc[-1]
                                                targets = self.calculate_targets(df, score)

                                                # إنشاء الإشارة
                                                signal = {
                                                    "symbol": symbol,
                                                    "price": price,
                                                    "score": score,
                                                    "reasons": reasons,
                                                    "buy_pressure": buy_pressure,
                                                    "targets": targets,
                                                    "btc_trend": self.btc_trend,
                                                    "vol_ratio": vol_ratio,
                                                    "time": datetime.now(),
                                                    "status": "active"
                                                }

                                                # إضافة للسجل
                                                signals_history.insert(0, signal)
                                                if len(signals_history) > 50:
                                                    signals_history.pop()

                                                # تحديث cooldown
                                                self.signal_cooldown[symbol] = datetime.now()

                                                # إرسال الإشعار
                                                msg = self.format_signal_message(
                                                    symbol, price, score, reasons,
                                                    targets, buy_pressure
                                                )
                                                self.send_telegram(msg)
                                                print(f"✅ Signal: {symbol} | Score: {score}")

                                                # حفظ في قاعدة البيانات
                                                if signals_collection is not None:
                                                    signals_collection.insert_one({
                                                        **signal,
                                                        "time": datetime.now()
                                                    })

                            # Anti-ban delay
                            time.sleep(0.15)

                        except Exception as e:
                            continue

                # انتظار قبل المسح التالي
                time.sleep(90)  # مسح كل 90 ثانية

            except Exception as e:
                print(f"Scanner Error: {e}")
                time.sleep(30)

# إنشاء المحرك وتشغيله
whale_hunter = WhaleHunterPro()
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
# 4. UI STYLES (محسّن)
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
        --whale: #8b5cf6;
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-top: 60px; line-height: 1.5; }
    .navbar { position: fixed; top: 0; left: 0; right: 0; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); height: 60px; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; z-index: 1000; }
    .logo { font-size: 1.25rem; font-weight: 800; color: var(--whale); text-decoration: none; letter-spacing: -0.5px; }
    .container { width: 100%; max-width: 600px; margin: 0 auto; padding: 20px; }
    .card { background: var(--card); padding: 20px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); border: 1px solid #334155; margin-bottom: 15px; }
    h1 { font-size: 1.8rem; line-height: 1.1; color: var(--text); margin-bottom: 10px; }
    h2 { font-size: 1.4rem; margin-bottom: 15px; }
    p { font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 20px; }
    .text-center { text-align: center; }
    label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; color: var(--text-secondary); }
    input { width: 100%; padding: 14px 16px; margin-bottom: 16px; border: 1px solid #334155; border-radius: 12px; font-size: 16px; background: #0f172a; color: var(--text); transition: all 0.2s; }
    input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(139,92,246,0.2); }
    .btn { display: block; width: 100%; background: var(--accent); color: white; padding: 16px; border: none; border-radius: 12px; font-weight: 600; font-size: 1rem; cursor: pointer; text-align: center; text-decoration: none; transition: all 0.2s; }
    .btn:hover { background: #7c3aed; transform: translateY(-1px); }
    .btn:active { transform: scale(0.98); }
    .btn-outline { background: transparent; border: 1px solid #334155; color: var(--text); }

    /* Signal Card Styles */
    .signal-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 16px; padding: 20px; margin-bottom: 15px; position: relative; overflow: hidden; }
    .signal-card::before { content: '🐋'; position: absolute; right: -20px; bottom: -20px; font-size: 100px; opacity: 0.05; }
    .signal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
    .signal-symbol { font-size: 1.3rem; font-weight: 800; color: var(--whale); }
    .signal-score { padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; }
    .score-high { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .score-medium { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
    .score-low { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

    .signal-details { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }
    .detail-box { background: rgba(139, 92, 246, 0.1); padding: 12px; border-radius: 10px; }
    .detail-label { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 4px; }
    .detail-value { font-size: 1rem; font-weight: 700; color: var(--text); }
    .detail-value.green { color: var(--success); }
    .detail-value.red { color: var(--danger); }

    .targets-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 15px; }
    .target-box { text-align: center; padding: 10px 5px; border-radius: 8px; background: rgba(255,255,255,0.05); }
    .target-box.tp { border-top: 2px solid var(--success); }
    .target-box.sl { border-top: 2px solid var(--danger); }
    .target-label { font-size: 0.7rem; color: var(--text-secondary); }
    .target-value { font-size: 0.8rem; font-weight: 600; margin-top: 4px; }

    .signal-time { text-align: right; font-size: 0.75rem; color: var(--text-secondary); margin-top: 15px; }

    .btc-status { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }
    .btc-up { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .btc-down { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .btc-neutral { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }

    .reasons-list { margin: 10px 0; padding: 0; list-style: none; }
    .reasons-list li { font-size: 0.85rem; color: var(--text-secondary); padding: 4px 0; }

    .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 20px; }
    .stat-card { background: var(--card); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #334155; }
    .stat-value { font-size: 2rem; font-weight: 800; color: var(--whale); }
    .stat-label { font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px; }

    .alert { padding: 15px; border-radius: 12px; margin-bottom: 20px; font-size: 0.9rem; text-align: center; }
    .error { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }

    .empty-state { text-align: center; padding: 60px 20px; color: var(--text-secondary); }
    .empty-state .icon { font-size: 60px; margin-bottom: 20px; opacity: 0.5; }

    @media (max-width: 480px) {
        .targets-grid { grid-template-columns: repeat(2, 1fr); }
        .signal-details { grid-template-columns: 1fr; }
    }
</style>
"""

# ==========================================
# 5. ROUTES (لا تغيير في المنطق الأساسي)
# ==========================================
@app.route('/')
def home():
    if 'user_id' in session: return redirect('/dashboard')
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>TRADOVIP Pro</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a><a href="/login" style="font-weight:600;color:var(--text);text-decoration:none;">Login</a></nav><div class="container" style="text-align:center; padding-top:40px;"><h1>Whale Hunting<br><span style="color:var(--accent)">V2.0 Pro</span></h1><p>Advanced whale detection with 7 indicators analysis, BTC correlation, and smart targeting.</p><div class="stats-grid"><div class="stat-card"><div class="stat-value">7</div><div class="stat-label">Indicators</div></div><div class="stat-card"><div class="stat-value">95%</div><div class="stat-label">Accuracy Target</div></div></div><div style="margin:30px 0;"><a href="/signup" class="btn" style="margin-bottom:15px;">Start Free Trial</a><a href="/login" class="btn btn-outline">Member Login</a></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a></nav><div class="container"><div class="card"><h2 class="text-center">Member Login</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn">Login</button></form><div class="text-center" style="margin-top:20px;"><a href="/forgot-password" style="color:var(--text-secondary);text-decoration:none;font-size:0.9rem;">Forgot Password?</a><br><br><a href="/signup" style="color:var(--accent);font-weight:600;">Create Account</a></div></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sign Up</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a></nav><div class="container"><div class="card"><h2 class="text-center">Join TRADOVIP Pro</h2>{msg}<form method="POST"><label>Email</label><input type="email" name="email" required><label>Password</label><input type="password" name="password" required><button type="submit" class="btn">Sign Up</button></form><p class="text-center" style="margin-top:20px;">Already a member? <a href="/login" style="color:var(--accent);font-weight:600;">Login</a></p></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verify</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a></nav><div class="container"><div class="card text-center"><h2>Verify Email</h2><p>Check your email for the code.</p>{msg}<form method="POST"><input type="text" name="code" style="text-align:center;font-size:24px;letter-spacing:5px;" maxlength="6" required><button type="submit" class="btn">Verify</button></form></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Forgot</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a></nav><div class="container"><div class="card"><h2>Reset Password</h2>{msg}<form method="POST"><input type="email" name="email" required placeholder="Enter your email"><button type="submit" class="btn">Send Code</button></form><p class="text-center" style="margin-top:20px;"><a href="/login" style="color:var(--text-secondary);">Cancel</a></p></div></div></body></html>""")

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
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>New Password</title>{SHARED_STYLE}</head><body><nav class="navbar"><a href="/" class="logo">🐋 TRADOVIP Pro</a></nav><div class="container"><div class="card"><h2>New Password</h2>{msg}<form method="POST"><input type="text" name="code" placeholder="Code" required style="text-align:center;letter-spacing:3px;"><input type="password" name="password" placeholder="New Password" required><button type="submit" class="btn">Change Password</button></form></div></div></body></html>""")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')

    # حالة BTC
    btc_status = whale_hunter.btc_trend
    btc_class = "btc-up" if "up" in btc_status else ("btc-down" if "down" in btc_status else "btc-neutral")
    btc_icon = "📈" if "up" in btc_status else ("📉" if "down" in btc_status else "➡️")

    # بناء HTML للإشارات
    signals_html = ""
    if not signals_history:
        signals_html = """
        <div class="empty-state">
            <div class="icon">🐋</div>
            <h3>Scanning Market...</h3>
            <p>Analyzing 100+ coins with 7 indicators.<br>Signals will appear here when whales are detected.</p>
        </div>
        """
    else:
        for s in signals_history[:20]:
            # تحديد فئة النقاط
            score = s.get('score', 0)
            if score >= 70:
                score_class = "score-high"
            elif score >= 55:
                score_class = "score-medium"
            else:
                score_class = "score-low"

            # تنسيق الأسباب
            reasons = s.get('reasons', [])[:4]
            reasons_html = "".join([f"<li>{r}</li>" for r in reasons])

            # تنسيق الأهداف
            targets = s.get('targets', {})
            price = s.get('price', 0)

            tp1_pct = ((targets.get('tp1', price) - price) / price * 100) if price > 0 else 0
            tp2_pct = ((targets.get('tp2', price) - price) / price * 100) if price > 0 else 0
            tp3_pct = ((targets.get('tp3', price) - price) / price * 100) if price > 0 else 0
            sl_pct = ((price - targets.get('sl', price)) / price * 100) if price > 0 else 0

            # الوقت
            signal_time = s.get('time', datetime.now())
            if isinstance(signal_time, datetime):
                time_str = signal_time.strftime("%H:%M")
            else:
                time_str = "N/A"

            signals_html += f"""
            <div class="signal-card">
                <div class="signal-header">
                    <span class="signal-symbol">🐋 {s.get('symbol', 'N/A')}</span>
                    <span class="signal-score {score_class}">{score}/100</span>
                </div>

                <div class="signal-details">
                    <div class="detail-box">
                        <div class="detail-label">Entry Price</div>
                        <div class="detail-value">${price:.6f}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Buy Pressure</div>
                        <div class="detail-value green">{s.get('buy_pressure', 0)*100:.0f}%</div>
                    </div>
                </div>

                <ul class="reasons-list">{reasons_html}</ul>

                <div class="targets-grid">
                    <div class="target-box tp">
                        <div class="target-label">TP1</div>
                        <div class="target-value" style="color:#10b981;">+{tp1_pct:.1f}%</div>
                    </div>
                    <div class="target-box tp">
                        <div class="target-label">TP2</div>
                        <div class="target-value" style="color:#10b981;">+{tp2_pct:.1f}%</div>
                    </div>
                    <div class="target-box tp">
                        <div class="target-label">TP3</div>
                        <div class="target-value" style="color:#10b981;">+{tp3_pct:.1f}%</div>
                    </div>
                    <div class="target-box sl">
                        <div class="target-label">SL</div>
                        <div class="target-value" style="color:#ef4444;">-{sl_pct:.1f}%</div>
                    </div>
                </div>

                <div class="signal-time">⏰ {time_str} UTC</div>
            </div>
            """

    return render_template_string(f"""<!DOCTYPE html><html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - TRADOVIP Pro</title>
        {SHARED_STYLE}
        <meta http-equiv="refresh" content="45">
    </head><body>
        <nav class="navbar">
            <span class="logo">🐋 TRADOVIP Pro</span>
            <a href="/logout" style="color:#ef4444;text-decoration:none;font-weight:600;font-size:0.9rem;">Logout</a>
        </nav>
        <div class="container">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
                <h2 style="margin:0;">Live Signals</h2>
                <div style="display:flex;gap:10px;align-items:center;">
                    <span class="btc-status {btc_class}">{btc_icon} BTC: {btc_status.upper()}</span>
                    <span style="font-size:0.75rem;background:rgba(139,92,246,0.2);color:#8b5cf6;padding:4px 10px;border-radius:12px;font-weight:600;">🔴 LIVE</span>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{len(signals_history)}</div>
                    <div class="stat-label">Total Signals</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">7</div>
                    <div class="stat-label">Active Indicators</div>
                </div>
            </div>

            {signals_html}

            <p style="text-align:center;font-size:0.8rem;color:var(--text-secondary);margin-top:30px;">
                ⚠️ Not financial advice. Always use proper risk management (2-5% per trade).
            </p>
        </div>
    </body></html>""")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================================
# 6. API ENDPOINTS (جديد)
# ==========================================
@app.route('/api/signals')
def api_signals():
    """API للحصول على الإشارات"""
    return {
        "status": "ok",
        "btc_trend": whale_hunter.btc_trend,
        "signals_count": len(signals_history),
        "signals": [
            {
                "symbol": s.get("symbol"),
                "price": s.get("price"),
                "score": s.get("score"),
                "buy_pressure": s.get("buy_pressure"),
                "targets": s.get("targets"),
                "time": s.get("time").isoformat() if s.get("time") else None
            }
            for s in signals_history[:10]
        ]
    }

@app.route('/api/status')
def api_status():
    """API لحالة النظام"""
    return {
        "status": "running",
        "btc_trend": whale_hunter.btc_trend,
        "btc_price": whale_hunter.btc_price,
        "signals_today": len(signals_history),
        "last_scan": datetime.now().isoformat()
    }

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
