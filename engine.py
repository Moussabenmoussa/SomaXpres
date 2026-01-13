import asyncio
import aiohttp
import json
from groq import Groq

# ================= SNIPER MODE CONFIGURATION =================
API_KEY_GROQ = "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"
API_KEY_SERPER = "a0ff8f3b86f02f586ee6dfef6fcefcb95bb7e650"
MODEL_NAME = "llama-3.3-70b-versatile"

class AsyncEliteAgent:
    def __init__(self):
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _async_search(self, query: str) -> str:
        """بحث متخصص في التسريبات والشائعات"""
        url = "https://google.serper.dev/search"
        # tbs: "qdr:d" تعني ابحث في آخر 24 ساعة فقط! نريد أخباراً طازجة
        payload = json.dumps({"q": query, "num": 8, "tbs": "qdr:d"}) 
        headers = {'X-API-KEY': self.serper_key, 'Content-Type': 'application/json'}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=payload) as response:
                    data = await response.json()
                    results = []
                    if "organic" in data:
                        for item in data["organic"]:
                            # نجمع المقتطفات فقط
                            results.append(f"SOURCE: {item.get('title')} | INFO: {item.get('snippet')}")
                    return "\n".join(results)
        except:
            return ""

    def _sync_llm(self, messages) -> str:
        response = self.groq_client.chat.completions.create(
            messages=messages,
            model=self.model,
            temperature=0.4, # حرارة منخفضة ليكون حاداً ومباشراً
        )
        return response.choices[0].message.content

    async def execute_mission(self, target: str):
        # 1. القنص (Sniping): البحث عن كلمات محددة جداً للكشف عن المستور
        # لن نبحث عن "News"، سنبحث عن "Rumors", "Leaks", "Insider selling"
        queries = [
            f"{target} crypto insider rumor leak site:reddit.com OR site:twitter.com",
            f"{target} developer wallet selling alert",
            f"{target} smart contract vulnerability warning",
            f"{target} upcoming token unlock dump"
        ]
        
        # تنفيذ البحث المتوازي
        tasks = [self._async_search(q) for q in queries]
        search_results = await asyncio.gather(*tasks)
        raw_intel = "\n".join(search_results)

        # 2. الاستخلاص (Extraction): استخراج الجمل التي تساوي ذهباً فقط
        final_prompt = f"""
        ACT AS A BLACK OPS CRYPTO INTELLIGENCE AGENT.
        Target: {target}
        Raw Intel:
        {raw_intel}

        MISSION:
        Ignore general news. Ignore price charts. Ignore marketing fluff.
        Find the "ALPHA" - the hidden info that moves markets before the public knows.
        
        OUTPUT FORMAT (Strictly 3 Short Bullet Points):
        
        💀 **INSIDER MOVES:** (Mention any dev selling, unlocks, or suspicious wallet moves found).
        🤫 **WHISPERS:** (What is the darkest rumor on Reddit/Twitter right now? Good or Bad?).
        🎯 **THE SNIPER VERDICT:** (ONE sentence: Buy, Sell, or Trap? and Why?).

        If no specific leaks found, say: "No insider signals detected yet. Chart is neutral."
        """
        
        report = self._sync_llm([{"role": "user", "content": final_prompt}])
        return report
