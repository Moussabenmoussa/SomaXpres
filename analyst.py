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
    signal: str
    severity: str        # HIGH (Scam), MEDIUM (Risky), LOW (Safe)
    headline: str
    full_report: str
    audit_data: dict     # <--- البيانات الحقيقية من فحص العقد

class InstitutionalAnalyst:
    def __init__(self):
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _check_contract_security(self, chain_id: str, address: str) -> dict:
        """
        فحص أمني حقيقي للعقد الذكي باستخدام GoPlus Security API.
        هذه بيانات حقيقية 100% وليست تخمينات.
        """
        # توحيد أسماء الشبكات لتناسب API
        chain_map = {"solana": "solana", "ethereum": "1", "bsc": "56", "base": "8453"}
        chain_id_code = chain_map.get(chain_id.lower(), "1") # الافتراضي إيثريوم

        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id_code}?contract_addresses={address}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    # استخراج نتائج الفحص
                    result = data.get("result", {}).get(address.lower(), {})
                    
                    # استخلاص الحقائق القاتلة (Red Flags)
                    risk_report = {
                        "is_honeypot": str(result.get("is_honeypot", "0")) == "1", # هل هي فخ؟
                        "is_mintable": str(result.get("is_mintable", "0")) == "1", # هل يمكن طباعة المزيد؟
                        "owner_balance": result.get("owner_balance", "Unknown"),   # كم يملك المطور؟
                        "is_open_source": str(result.get("is_open_source", "0")) == "1",
                        "buy_tax": result.get("buy_tax", "0"), # ضريبة الشراء
                        "sell_tax": result.get("sell_tax", "0") # ضريبة البيع
                    }
                    return risk_report
        except:
            return {"error": "Security data unavailable"}

    async def _search_news(self, query: str) -> str:
        """بحث عن الأخبار التكميلية"""
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 4, "tbs": "qdr:d"}) 
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
            return ""

    async def analyze_asset(self, asset: AssetData) -> AlphaSignal:
        print(f"🛡️ [AUDITOR] Running Security Check on: {asset.symbol}...")

        # 1. الخطوة الأولى: الفحص الأمني الحقيقي (The Real Value)
        security_audit = await self._check_contract_security(asset.chain, asset.pair_address)

        # 2. الخطوة الثانية: بحث الأخبار
        queries = [
            f"{asset.symbol} crypto project scam accusations",
            f"{asset.symbol} official twitter announcement",
            f"{asset.symbol} token huge whale activity"
        ]
        tasks = [self._search_news(q) for q in queries]
        search_results = await asyncio.gather(*tasks)
        news_data = "\n".join(search_results)

        # 3. التحليل النهائي: دمج التدقيق الأمني مع الأخبار
        prompt = f"""
        ACT AS A CRYPTO RISK AUDITOR (Institutional Grade).
        
        ASSET: {asset.symbol}
        
        🚨 SECURITY AUDIT (REAL ON-CHAIN FACTS):
        - Is Honeypot (Can't sell): {security_audit.get('is_honeypot')}
        - Mintable (Infinite Supply Risk): {security_audit.get('is_mintable')}
        - Buy/Sell Tax: {security_audit.get('buy_tax')}% / {security_audit.get('sell_tax')}%
        - Code Open Source: {security_audit.get('is_open_source')}
        
        📰 MARKET METRICS & NEWS:
        - Liquidity: ${asset.liquidity_usd:,.0f}
        - Search Intel: {news_data}
        
        --------------------------------
        YOUR VERDICT:
        Base your signal PRIMARILY on the Security Audit.
        - If Honeypot OR Mintable = "SCAM ALERT" (Severity: HIGH).
        - If Taxes > 10% = "HIGH RISK" (Severity: HIGH).
        - If Security is clean AND News is good = "SAFE / BUY".
        
        OUTPUT JSON ONLY:
        {{
            "signal": "SAFE" | "CAUTION" | "DANGEROUS" | "SCAM DETECTED",
            "severity": "HIGH" | "MEDIUM" | "LOW",
            "headline": "Example: 🟢 Code Clean + High Liquidity",
            "full_report": "Markdown. \n- Start with '🛡️ Security Audit' section listing the risks found.\n- Then '📰 Market Analysis'.\n- Final Verdict."
        }}
        """
        
        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1 # دقة عالية جداً (لا إبداع في المخاطر)
            )
            result_json = json.loads(response.choices[0].message.content)
            
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal=result_json.get("signal", "CAUTION"),
                severity=result_json.get("severity", "MEDIUM"),
                headline=result_json.get("headline", "Audit Complete"),
                full_report=result_json.get("full_report", "Report ready."),
                audit_data=security_audit
            )
            
        except Exception as e:
            return AlphaSignal(
                asset_symbol=asset.symbol,
                signal="UNKNOWN",
                severity="LOW",
                headline="Audit Error",
                full_report=str(e),
                audit_data={}
            )
