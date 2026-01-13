import asyncio
import json
import os
import aiohttp
from groq import Groq
from pydantic import BaseModel
from typing import Optional
from scout import AssetData # استيراد هيكلية البيانات من ملف الرادار

# ================= إعدادات المحلل =================
# نستخدم المفاتيح التي زودتني بها (للتجربة المباشرة)
API_KEY_GROQ = "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"
API_KEY_SERPER = "a0ff8f3b86f02f586ee6dfef6fcefcb95bb7e650"
MODEL_NAME = "llama-3.3-70b-versatile"

# ================= نموذج المخرجات (Structured Alpha) =================
# هذا هو الشكل الذي سيظهر في جدول الواجهة (Nansen Style)
class AlphaSignal(BaseModel):
    asset_symbol: str
    signal: str          # BULLISH, BEARISH, NEUTRAL, SCAM_ALERT
    severity: str        # HIGH, MEDIUM, LOW
    headline: str        # جملة واحدة قصيرة جداً للجدول
    full_report: str     # التقرير التفصيلي (Markdown)

class InstitutionalAnalyst:
    def __init__(self):
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _search_intel(self, query: str) -> str:
        """البحث عن المعلومات الحصرية (آخر 24 ساعة)"""
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5, "tbs": "qdr:d"}) 
        headers = {'X-API-KEY': self.serper_key, 'Content-Type': 'application/json'}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=payload) as response:
                    data = await response.json()
                    results = []
                    if "organic" in data:
                        for item in data["organic"]:
                            results.append(f"- {item.get('title')}: {item.get('snippet')}")
                    return "\n".join(results)
        except:
            return "No specific intel found."

    async def analyze_asset(self, asset: AssetData) -> AlphaSignal:
        """
        تحليل أصل واحد بعمق واستخراج إشارات مؤسساتية
        """
        print(f"🧠 [ANALYST] Deep diving into: {asset.symbol}...")

        # 1. البحث الاستراتيجي (Sniper Queries)
        # نبحث عن أشياء محددة جداً
        queries = [
            f"{asset.symbol} crypto insider selling rumors today",
            f"{asset.symbol} token unlock schedule upcoming",
            f"{asset.symbol} major partnership announcement leaked"
        ]
        
        # تنفيذ البحث المتوازي للسرعة
        tasks = [self._search_intel(q) for q in queries]
        search_results = await asyncio.gather(*tasks)
        intel_data = "\n".join(search_results)

        # 2. التحليل وإصدار الحكم (Judgment Day)
        # نطلب من Llama إرجاع JSON حصراً
        prompt = f"""
        ACT AS AN ELITE CRYPTO HEDGE FUND ANALYST.
        
        ASSET: {asset.symbol}
        PRICE: ${asset.price_usd}
        VOL: ${asset.volume_24h}
        
        INTEL GATHERED (Last 24h):
        {intel_data}
        
        --------------------------------
        YOUR MISSION:
        Analyze the intel. Decide the signal. 
        Output valid JSON only matching this schema:
        {{
            "signal": "BULLISH" | "BEARISH" | "NEUTRAL" | "HIGH_RISK",
            "severity": "HIGH" | "MEDIUM" | "LOW",
            "headline": "Short summary (max 6 words)",
            "full_report": "Detailed markdown report focusing on risks and catalysts."
        }}
        """
        
        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"}, # نجبره على JSON
                temperature=0.3
            )
            
            result_json = json.loads(response.choices[0].message.content)
            
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal=result_json.get("signal", "NEUTRAL"),
                severity=result_json.get("severity", "LOW"),
                headline=result_json.get("headline", "No major signals"),
                full_report=result_json.get("full_report", "Analysis complete.")
            )
            
        except Exception as e:
            # في حال حدوث خطأ، نعيد نتيجة فارغة بدلاً من تحطيم النظام
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal="ERROR",
                severity="LOW",
                headline="Analysis Failed",
                full_report=str(e)
            )

# ================= اختبار التكامل (Integration Test) =================
if __name__ == "__main__":
    from scout import MarketRadar # نستدعي الرادار الذي بنيناه سابقاً
    
    async def run_pipeline():
        # 1. تشغيل الرادار لجلب العملات
        radar = MarketRadar()
        print("📡 Launching Scout...")
        # سنجرب على عملة واحدة لتوفير الوقت في الاختبار
        assets = await radar.scan_market(["Pepe"]) 
        
        if not assets:
            print("No assets found.")
            return

        target_asset = assets[0] # نأخذ أول عملة وجدها الرادار
        print(f"🎯 Target Acquired: {target_asset.name} (${target_asset.price_usd})")

        # 2. تشغيل المحلل
        analyst = InstitutionalAnalyst()
        result = await analyst.analyze_asset(target_asset)
        
        # 3. عرض النتيجة كما ستظهر في لوحة التحكم (Dashboard)
        print("\n" + "="*50)
        print("🖥️  DASHBOARD ROW PREVIEW")
        print("="*50)
        print(f"| {result.asset_symbol:<6} | {result.signal:<10} | {result.severity:<8} | {result.headline}")
        print("-" * 50)
        print("\n📄 FULL REPORT PREVIEW:\n")
        print(result.full_report)

    asyncio.run(run_pipeline())
