import aiohttp
import asyncio
from pydantic import BaseModel
from typing import List, Optional, Dict

# ================= إعدادات المؤسسة =================
# معايير الجودة لقبول العملة في نظامنا
MIN_LIQUIDITY_USD = 100_000   # الحد الأدنى للسيولة: 100 ألف دولار
MIN_VOLUME_24H = 500_000      # الحد الأدنى للتداول اليومي: 500 ألف دولار

# ================= نموذج البيانات (Data Schema) =================
# هذا ما يجعل الكود مؤسساتياً: نحن نحدد شكل البيانات بدقة
class AssetData(BaseModel):
    name: str
    symbol: str
    price_usd: float
    liquidity_usd: float
    volume_24h: float
    chain: str
    pair_address: str
    url: str
    
    # دالة لعرض البيانات بشكل جميل في الـ Console
    def to_log_string(self):
        return (f"💎 {self.symbol:<6} | 💵 ${self.price_usd:<10.4f} | "
                f"💧 Liq: ${self.liquidity_usd:,.0f} | 📊 Vol: ${self.volume_24h:,.0f} | "
                f"🔗 {self.chain}")

# ================= كلاس الرادار (The Radar Engine) =================
class MarketRadar:
    def __init__(self):
        self.api_url = "https://api.dexscreener.com/latest/dex/search"

    async def scan_market(self, search_queries: List[str]) -> List[AssetData]:
        """
        يقوم بالبحث عن العملات، تنظيف البيانات، واختيار الأقوى فقط.
        """
        print(f"📡 [RADAR] Scanning market for: {search_queries}...")
        
        candidates = []
        
        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                try:
                    # نطلب البيانات من DexScreener
                    async with session.get(self.api_url, params={"q": query}) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get("pairs", [])
                            
                            # معالجة وتنظيف النتائج
                            processed_assets = self._process_pairs(pairs)
                            candidates.extend(processed_assets)
                        else:
                            print(f"⚠️ [ERROR] DexScreener API returned status: {response.status}")
                except Exception as e:
                    print(f"⚠️ [ERROR] Connection failed: {str(e)}")

        # إزالة التكرار (قد تظهر نفس العملة في بحثين مختلفين)
        # نستخدم القاموس لإبقاء نسخة واحدة لكل رمز (Symbol)
        unique_assets = {asset.symbol: asset for asset in candidates}.values()
        
        # الترتيب حسب الحجم (Volume) لضمان أننا نركز على الأهم
        sorted_assets = sorted(list(unique_assets), key=lambda x: x.volume_24h, reverse=True)
        
        print(f"✅ [RADAR] Scan complete. Found {len(sorted_assets)} valid institutional-grade assets.")
        return sorted_assets

    def _process_pairs(self, pairs: List[Dict]) -> List[AssetData]:
        """
        الفلترة الذكية: استبعاد العملات الضعيفة واختيار الزوج الأفضل
        """
        valid_assets = []
        
        for pair in pairs:
            try:
                # استخراج البيانات الأساسية
                liq = float(pair.get("liquidity", {}).get("usd", 0))
                vol = float(pair.get("volume", {}).get("h24", 0))
                price = float(pair.get("priceUsd", 0))
                
                # 1. تطبيق فلتر الجودة (Quality Gate)
                if liq < MIN_LIQUIDITY_USD or vol < MIN_VOLUME_24H:
                    continue # تجاهل هذه العملة، لا تليق بالمؤسسة

                # 2. إنشاء كائن بيانات نظيف
                asset = AssetData(
                    name=pair.get("baseToken", {}).get("name", "Unknown"),
                    symbol=pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
                    price_usd=price,
                    liquidity_usd=liq,
                    volume_24h=vol,
                    chain=pair.get("chainId", "unknown"),
                    pair_address=pair.get("pairAddress"),
                    url=pair.get("url")
                )
                valid_assets.append(asset)
                
            except Exception:
                continue # تخطي أي بيانات تالفة

        return valid_assets

# ================= اختبار الرادار (Simulation) =================
if __name__ == "__main__":
    async def main():
        radar = MarketRadar()
        
        # سنبحث عن كلمات عامة لجلب "الترند" الحالي
        # في النسخة النهائية، هذه القائمة يمكن أن تأتي من قاعدة البيانات
        target_sectors = ["Solana", "AI", "Memecoin", "Pepe", "Trump"] 
        
        results = await radar.scan_market(target_sectors)
        
        print("\n" + "="*80)
        print(f"📊 INSTITUTIONAL MARKET FEED ({len(results)} Assets)")
        print("="*80)
        
        for asset in results[:15]: # عرض أهم 15 فقط
            print(asset.to_log_string())
            
    asyncio.run(main())
