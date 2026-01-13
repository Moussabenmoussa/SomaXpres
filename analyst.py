# monster_analyst.py
import asyncio
import json
import aiohttp
from groq import Groq
from pydantic import BaseModel
from scout import AssetData
import concurrent.futures
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monster_analyst")

# ================= إعدادات المحلل (كما أرسلتها) =================
API_KEY_GROQ = "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"
API_KEY_SERPER = "a0ff8f3b86f02f586ee6dfef6fcefcb95bb7e650"
MODEL_NAME = "llama-3.3-70b-versatile"

class AlphaSignal(BaseModel):
    asset_symbol: str
    signal: str
    severity: str
    headline: str
    full_report: str
    whale_index: int

class InstitutionalAnalyst:
    def __init__(self):
        # تهيئة عميل Groq بالمفتاح كما أرسلت
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME
        # Executor لتشغيل استدعاءات متزامنة في خيط منفصل حتى لا نجمّد حلقة asyncio
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    async def _get_order_flow_data(self, pair_address: str) -> dict:
        # احتفظت بالهيكل الأصلي — يمكنك توسيعها لاحقًا
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning("DexScreener non-200: %s", resp.status)
                        return {}
                    return await resp.json()
        except Exception as e:
            logger.exception("Order flow fetch failed: %s", e)
            return {}

    async def analyze_asset(self, asset: AssetData) -> AlphaSignal:
        """
        نسخة محافظة على منطقك الأصلي مع:
        - تشغيل استدعاء Groq في ThreadPoolExecutor إن كان العميل متزامنًا
        - معالجة أخطاء أوضح
        """
        logger.info("🐋 [ORDER FLOW] Analyzing Smart Money for: %s", asset.symbol)

        # جلب بيانات الزوج من DexScreener (محاولة بسيطة)
        tx_data = {}
        try:
            url = f"https://api.dexscreener.com/latest/dex/pairs/{asset.chain}/{asset.pair_address}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get("pairs") or []
                        if pairs:
                            pair = pairs[0]
                            txns = pair.get('txns', {}).get('h24', {})
                            buys = txns.get('buys', 1)
                            sells = txns.get('sells', 1)
                            total_tx = buys + sells if (buys + sells) > 0 else 1
                            buy_ratio = (buys / total_tx) * 100
                            avg_trade_size = asset.volume_24h / total_tx if total_tx > 0 else 0
                            whale_dominance = min(100, (avg_trade_size / 500) * 50)
                            tx_data = {
                                "buys": buys,
                                "sells": sells,
                                "avg_trade": avg_trade_size,
                                "buy_ratio": buy_ratio
                            }
                        else:
                            tx_data = {"buys":0,"sells":0,"avg_trade":0,"buy_ratio":50}
                    else:
                        tx_data = {"error": f"dex status {response.status}"}
        except Exception as e:
            logger.exception("Failed to fetch order flow: %s", e)
            tx_data = {"error": "No Order Flow Data"}

        # بناء الـ prompt كما في كودك
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
            "whale_index": {int(tx_data.get('avg_trade',0) and min(100, (tx_data.get('avg_trade',0) / 500) * 50) or 0)}
        }}
        """

        # استدعاء Groq: بعض مكتبات العملاء متزامنة؛ لتجنّب حجب حلقة asyncio نشغّلها في executor
        def groq_call_sync():
            # هذا الجزء يعمل في خيط منفصل
            return self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1
            )

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(self._executor, groq_call_sync)
            # محاولة استخراج المحتوى كما في كودك
            content = None
            try:
                content = response.choices[0].message.content
            except Exception:
                # fallback: قد تكون البنية مختلفة
                content = getattr(response, "content", None) or json.dumps(response)
            # إذا كان النص JSON، نحاول تحميله
            try:
                result_json = json.loads(content) if isinstance(content, str) else content
            except Exception:
                logger.exception("Failed to parse Groq content; returning error signal")
                return AlphaSignal(
                    asset_symbol=asset.symbol,
                    signal="ERROR",
                    severity="LOW",
                    headline="LLM parse error",
                    full_report=f"Raw response: {str(content)[:1000]}",
                    whale_index=0
                )

            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal=result_json.get("signal", "NEUTRAL"),
                severity=result_json.get("severity", "LOW"),
                headline=result_json.get("headline", "Analyzing Flow..."),
                full_report=result_json.get("full_report", "Data processed."),
                whale_index=result_json.get("whale_index", 0)
            )

        except Exception as e:
            logger.exception("Groq call failed: %s", e)
            # fallback: يمكنك هنا استدعاء منطق قواعدي محلي بدلاً من ERROR إذا تفضّل
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal="ERROR",
                severity="LOW",
                headline="Data Error",
                full_report=str(e),
                whale_index=0
            )

# مثال تشغيل سريع لاختبار الملف مباشرة
if __name__ == "__main__":
    class DummyAsset:
        def __init__(self, symbol, chain, pair_address, volume_24h):
            self.symbol = symbol
            self.chain = chain
            self.pair_address = pair_address
            self.volume_24h = volume_24h

    async def demo():
        analyst = InstitutionalAnalyst()
        asset = DummyAsset("TEST", "solana", "0xdeadbeef", 250000)
        sig = await analyst.analyze_asset(asset)
        print(sig.json(indent=2))
    asyncio.run(demo())
