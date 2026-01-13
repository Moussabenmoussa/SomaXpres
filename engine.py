import asyncio
import aiohttp
import json
from typing import List, Dict
from groq import Groq

# ================= إعدادات الاتصال (مباشرة) =================
# لقد وضعت المفاتيح هنا مباشرة لضمان الاشتغال 100%
API_KEY_GROQ = "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"
API_KEY_SERPER = "a0ff8f3b86f02f586ee6dfef6fcefcb95bb7e650"
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 3 

class AsyncEliteAgent:
    def __init__(self):
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _async_search(self, query: str) -> str:
        """بحث سريع باستخدام Serper"""
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5, "tbs": "qdr:w"}) # نتائج آخر أسبوع
        headers = {'X-API-KEY': self.serper_key, 'Content-Type': 'application/json'}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=payload) as response:
                    if response.status != 200:
                        return f"Search Error: {response.status}"
                    data = await response.json()
                    results = []
                    if "organic" in data:
                        for item in data["organic"]:
                            results.append(f"- {item.get('title')}: {item.get('snippet')} (Link: {item.get('link')})")
                    return "\n".join(results)
        except Exception as e:
            return f"Connection Error: {str(e)}"

    def _sync_llm(self, messages: List[Dict], json_mode=False) -> str:
        """استدعاء Groq"""
        try:
            response = self.groq_client.chat.completions.create(
                messages=messages,
                model=self.model,
                response_format={"type": "json_object"} if json_mode else {"type": "text"},
                temperature=0.6
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM Error: {str(e)}"

    async def execute_mission(self, target: str):
        # 1. التخطيط
        initial_plan = self._sync_llm([
            {"role": "system", "content": "You are a Chief Intelligence Officer."},
            {"role": "user", "content": f"Analyze '{target}'. Break it down into 3 aggressive search queries. Return JSON: {{'queries': []}}"}
        ], json_mode=True)
        
        try:
            queries = json.loads(initial_plan).get("queries", [])
        except:
            queries = [f"{target} analysis", f"{target} news", f"{target} scam or legit"]
        
        # 2. البحث المتوازي
        tasks = [self._async_search(q) for q in queries]
        search_results = await asyncio.gather(*tasks)
        combined_data = "\n".join(search_results)

        # 3. التحليل النهائي (بدون تعقيد زائد لضمان السرعة)
        final_prompt = f"""
        Data: {combined_data}
        Task: Write a detailed 'Crypto Alpha Report' on '{target}'.
        Structure:
        1. 🚀 Executive Summary (The Verdict)
        2. 🚩 Risks & Red Flags
        3. 💎 Catalysts (Why buy?)
        4. 🧠 Final Conclusion
        
        Use Markdown formatting.
        """
        final_report = self._sync_llm([{"role": "user", "content": final_prompt}])
        
        return final_report
