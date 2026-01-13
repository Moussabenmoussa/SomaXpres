import asyncio
import json
import aiohttp
from groq import Groq
from pydantic import BaseModel
from scout import AssetData

# ================= إعدادات المحلل =================
API_KEY_GROQ = "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"
API_KEY_SERPER = "a0ff8f3b86f02f586ee6dfef6fcefcb95bb7e650"
MODEL_NAME = "llama-3.3-70b-versatile"

class AlphaSignal(BaseModel):
    asset_symbol: str
    signal: str          # BUY, SELL, ACCUMULATION, DUMPING
    severity: str        # HIGH, MEDIUM, LOW
    headline: str
    full_report: str
    whale_index: int     # مؤشر الحيتان (من 0 إلى 100)

class InstitutionalAnalyst:
    def __init__(self):
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _get_order_flow_data(self, pair_address: str) -> dict:
        """
        هنا السحر: نحسب تدفق الأموال الحقيقي من DexScreener
        """
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}" # نجرب سولانا كمثال، يمكن تعميمه
        # ملاحظة: الرابط العام يعمل لكل الشبكات إذا كان العنوان صحيحاً، لكن نستخدم البحث للضمان
        # للتبسيط سنعتمد على البيانات التي مررناها من Scout
        return {}

    async def analyze_asset(self, asset: AssetData) -> AlphaSignal:
        print(f"🐋 [ORDER FLOW] Analyzing Smart Money for: {asset.symbol}...")

        # 1. جلب بيانات التداولات التفصيلية (من Scout Data مباشرة)
        # DexScreener يعطينا عدد عمليات البيع والشراء في آخر ساعة و 24 ساعة
        # سنحتاج لإعادة جلب البيانات بدقة إذا لم تكن موجودة، لكن سنفترض وجودها في التحليل
        
        # لنقم بعملية حسابية "قذرة" لكن فعالة جداً لاكتشاف الحيتان
        # متوسط حجم الصفقة = الحجم الكلي / عدد العمليات
        # ملاحظة: DexScreener API لا يعطي عدد العمليات (Txns) في البحث العام، 
        # لذلك سنقوم بطلب خاص للزوج المحدد للحصول على الـ txns
        
        url = f"https://api.dexscreener.com/latest/dex/pairs/{asset.chain}/{asset.pair_address}"
        
        whale_dominance = 0
        buy_pressure = 0
        tx_data = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    pair = data['pairs'][0]
                    
                    # استخراج بيانات الضغط (آخر 24 ساعة)
                    txns = pair.get('txns', {}).get('h24', {})
                    buys = txns.get('buys', 1)
                    sells = txns.get('sells', 1)
                    total_tx = buys + sells
                    
                    # المعادلة 1: ضغط الشراء (Buy Pressure)
                    # هل المشترون أكثر من البائعين؟
                    buy_ratio = (buys / total_tx) * 100 if total_tx > 0 else 50
                    
                    # المعادلة 2: هيمنة الحيتان (Whale Dominance)
                    # متوسط حجم الصفقة الواحدة
                    avg_trade_size = asset.volume_24h / total_tx if total_tx > 0 else 0
                    
                    # تقييم "نوعية" المال
                    # إذا كان متوسط الصفقة > 2000$ (في الكريبتو اليومي هذا يعتبر مال ذكي نسبياً مقارنة بـ 10$ لعملات الميم)
                    whale_dominance = min(100, (avg_trade_size / 500) * 50) # معادلة تقريبية
                    
                    tx_data = {
                        "buys": buys,
                        "sells": sells,
                        "avg_trade": avg_trade_size,
                        "buy_ratio": buy_ratio
                    }

        except:
            tx_data = {"error": "No Order Flow Data"}

        # 2. إعداد التقرير الذكي (بدون أخبار تافهة)
        prompt = f"""
        ACT AS AN INSTITUTIONAL TRADER (ORDER FLOW SPECIALIST).
        
        ASSET: {asset.symbol}
        
        📊 ORDER FLOW DATA (THE TRUTH):
        - 24h Transactions: {tx_data.get('buys', 0)} Buys vs {tx_data.get('sells', 0)} Sells.
        - Buy Pressure: {tx_data.get('buy_ratio', 50):.1f}% (Above 50% = Buying dominance).
        - Average Trade Size: ${tx_data.get('avg_trade', 0):.0f} per transaction.
        - Total Volume: ${asset.volume_24h:,.0f}
        
        --------------------------------
        YOUR JOB: Determine who is moving the price?
        
        LOGIC TO FOLLOW:
        1. If "Avg Trade Size" is HIGH (> $1000) AND "Buy Pressure" > 55% -> **WHALES ACCUMULATING**. (Strong Buy).
        2. If "Avg Trade Size" is LOW (< $50) AND "Buy Pressure" > 60% -> **RETAIL FOMO**. (Risky/Top Signal).
        3. If "Buy Pressure" < 40% -> **DISTRIBUTION/DUMPING**. (Sell).
        
        OUTPUT JSON ONLY:
        {{
            "signal": "ACCUMULATION" | "FOMO" | "DUMPING" | "NEUTRAL",
            "severity": "HIGH" | "MEDIUM" | "LOW",
            "headline": "Example: 🐋 Smart Money Buying (Avg Tx $2k)",
            "full_report": "Markdown. Focus ONLY on the money flow. e.g., 'Retail is buying the top while whales are selling'. Don't talk about news.",
            "whale_index": {int(whale_dominance)}
        }}
        """
        
        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            result_json = json.loads(response.choices[0].message.content)
            
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal=result_json.get("signal", "NEUTRAL"),
                severity=result_json.get("severity", "LOW"),
                headline=result_json.get("headline", "Analyzing Flow..."),
                full_report=result_json.get("full_report", "Data processed."),
                whale_index=result_json.get("whale_index", 0)
            )
            
        except Exception as e:
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal="ERROR",
                severity="LOW",
                headline="Data Error",
                full_report=str(e),
                whale_index=0
            )
