"""
📱 Telegram Service
Sends trading signals to Telegram channel/group
"""

import requests
from typing import Dict, Optional
from datetime import datetime

class TelegramService:
    """Service for sending messages to Telegram"""

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram service

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat/channel ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

        if not self.enabled:
            print("⚠️ Telegram service disabled: Missing bot_token or chat_id")

    def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a text message to Telegram

        Args:
            text: Message text
            parse_mode: 'HTML' or 'Markdown'

        Returns:
            True if successful
        """
        if not self.enabled:
            print("📵 Telegram disabled, message not sent")
            return False

        try:
            url = f"{self.BASE_URL}{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('ok'):
                print("✅ Telegram message sent successfully")
                return True
            else:
                print(f"❌ Telegram error: {result.get('description')}")
                return False

        except Exception as e:
            print(f"❌ Telegram send error: {e}")
            return False

    def format_signal(self, signal: Dict) -> str:
        """
        Format a trading signal as a beautiful Telegram message

        Args:
            signal: Signal dictionary

        Returns:
            Formatted HTML message
        """
        # Signal type emoji and color
        if signal['type'] == 'LONG':
            type_emoji = "🟢"
            type_text = "إشارة شراء"
            direction = "LONG"
        else:
            type_emoji = "🔴"
            type_text = "إشارة بيع"
            direction = "SHORT"

        # Strength indicator
        strength = signal['strength']
        if strength >= 85:
            strength_text = "قوية جداً 💪💪💪"
        elif strength >= 75:
            strength_text = "قوية 💪💪"
        elif strength >= 65:
            strength_text = "متوسطة 💪"
        else:
            strength_text = "ضعيفة"

        # Calculate percentages
        entry = signal['entry']
        sl = signal['stop_loss']
        tp1 = signal['take_profit_1']
        tp2 = signal['take_profit_2']
        tp3 = signal['take_profit_3']

        if signal['type'] == 'LONG':
            sl_pct = round((entry - sl) / entry * 100, 2)
            tp1_pct = round((tp1 - entry) / entry * 100, 2)
            tp2_pct = round((tp2 - entry) / entry * 100, 2)
            tp3_pct = round((tp3 - entry) / entry * 100, 2)
        else:
            sl_pct = round((sl - entry) / entry * 100, 2)
            tp1_pct = round((entry - tp1) / entry * 100, 2)
            tp2_pct = round((entry - tp2) / entry * 100, 2)
            tp3_pct = round((entry - tp3) / entry * 100, 2)

        # Format indicators
        indicators = signal.get('indicators', {})
        rsi = indicators.get('rsi', 0)
        macd_cross = indicators.get('macd_cross', 'none')
        ema_trend = indicators.get('ema_trend', 'neutral')
        volume_ratio = indicators.get('volume_ratio', 1)

        # RSI emoji
        if rsi < 30:
            rsi_emoji = "⬇️ تشبع بيعي"
        elif rsi > 70:
            rsi_emoji = "⬆️ تشبع شرائي"
        else:
            rsi_emoji = "➡️ متعادل"

        # MACD emoji
        if macd_cross == 'bullish':
            macd_emoji = "✅ تقاطع صاعد"
        elif macd_cross == 'bearish':
            macd_emoji = "❌ تقاطع هابط"
        else:
            macd_emoji = "➖ لا تقاطع"

        # EMA emoji
        ema_emojis = {
            'strong_bullish': "📈 صاعد قوي",
            'bullish': "↗️ صاعد",
            'neutral': "➡️ متعادل",
            'bearish': "↘️ هابط",
            'strong_bearish': "📉 هابط قوي"
        }
        ema_emoji = ema_emojis.get(ema_trend, "➡️ متعادل")

        # Volume emoji
        if volume_ratio > 2:
            vol_emoji = "🔥 مرتفع جداً"
        elif volume_ratio > 1.5:
            vol_emoji = "📊 مرتفع"
        else:
            vol_emoji = "📉 عادي"

        # Build message
        message = f"""
{type_emoji} <b>{type_text} {strength_text}</b>

━━━━━━━━━━━━━━━━━━━━

💎 <b>العملة:</b> {signal['symbol']}
📊 <b>الإطار:</b> {signal['timeframe']}
🏦 <b>السوق:</b> {signal['market']}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC

━━━━━━━━━━━━━━━━━━━━

💰 <b>الدخول:</b> <code>${entry:,.4f}</code>
🛑 <b>وقف الخسارة:</b> <code>${sl:,.4f}</code> <i>(-{sl_pct}%)</i>

✅ <b>الهدف 1:</b> <code>${tp1:,.4f}</code> <i>(+{tp1_pct}%)</i>
✅ <b>الهدف 2:</b> <code>${tp2:,.4f}</code> <i>(+{tp2_pct}%)</i>
✅ <b>الهدف 3:</b> <code>${tp3:,.4f}</code> <i>(+{tp3_pct}%)</i>

━━━━━━━━━━━━━━━━━━━━

📈 <b>Risk/Reward:</b> 1:{signal['risk_reward']}
💪 <b>قوة الإشارة:</b> {strength}%

━━━━━━━━━━━━━━━━━━━━

<b>📊 المؤشرات الفنية:</b>

• RSI: {rsi:.1f} {rsi_emoji}
• MACD: {macd_emoji}
• EMA: {ema_emoji}
• Volume: {vol_emoji} ({volume_ratio:.1f}x)

━━━━━━━━━━━━━━━━━━━━

⚠️ <i>تنبيه: هذه توصية للتحليل فقط وليست نصيحة مالية.
تداول بمسؤولية ولا تخاطر بأكثر مما تستطيع خسارته.</i>

🤖 <b>Crypto Signals Bot</b>
"""

        return message.strip()

    def send_signal(self, signal: Dict) -> bool:
        """
        Send a formatted trading signal

        Args:
            signal: Signal dictionary

        Returns:
            True if successful
        """
        message = self.format_signal(signal)
        return self.send_message(message)

    def send_startup_message(self) -> bool:
        """Send bot startup notification"""
        message = """
🚀 <b>Crypto Signals Bot Started!</b>

━━━━━━━━━━━━━━━━━━━━

✅ البوت يعمل الآن
📊 مراقبة Top 50 عملة
⏰ تحديث كل 5 دقائق
📱 الإشارات ستُرسل هنا

━━━━━━━━━━━━━━━━━━━━

🤖 <b>Crypto Signals Bot</b>
"""
        return self.send_message(message.strip())

    def send_error(self, error_message: str) -> bool:
        """Send error notification"""
        message = f"""
⚠️ <b>خطأ في البوت</b>

{error_message}

🤖 <b>Crypto Signals Bot</b>
"""
        return self.send_message(message.strip())

    def test_connection(self) -> Dict:
        """
        Test Telegram connection

        Returns:
            Bot info if successful
        """
        if not self.enabled:
            return {'ok': False, 'error': 'Service disabled'}

        try:
            url = f"{self.BASE_URL}{self.bot_token}/getMe"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            return {'ok': False, 'error': str(e)}
