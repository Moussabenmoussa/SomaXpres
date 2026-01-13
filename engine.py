import asyncio
import aiohttp
import json
import os
from typing import List, Dict
from groq import Groq

# نقرأ المفاتيح من بيئة السيرفر (Render)
API_KEY_GROQ = os.getenv("GROQ_API_KEY")
API_KEY_SERPER = os.getenv("SERPER_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 3

class AsyncEliteAgent:
    def __init__(self):
        # التحقق من وجود المفاتيح
        if not API_KEY_GROQ or not API_KEY_SERPER:
            raise ValueError("API Keys are missing in Environment Variables!")
            
        self.groq_client = Groq(api_key=API_KEY_GROQ)
        self.serper_key = API_KEY_SERPER
        self.model = MODEL_NAME

    async def _async_search(self, query: str) -> str:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": 5, "tbs": "qdr:w"})
        headers = {'X-API-KEY': self.serper_key, 'Content-Type': 'application/json'}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload) as response:
                try:
                    data = await response.json()
                    results = []
                    if "organic" in data:
                        for item in data["organic"]:
                            results.append(f"- {item.get('title')}: {item.get('snippet')} (Link: {item.get('link')})")
                    return "\n".join(results)
                except:
                    return "Search Error"

    def _sync_llm(self, messages: List[Dict], json_mode=False) -> str:
        try:
            response = self.groq_client.chat.completions.create(
                messages=messages,
                model=self.model,
                response_format={"type": "json_object"} if json_mode else {"type": "text"},
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return str(e)

    async def execute_mission(self, target: str):
        # 1. التخطيط
        initial_plan = self._sync_llm([
            {"role": "system", "content": "You are a Chief Intelligence Officer."},
            {"role": "user", "content": f"Analyze '{target}'. Break it down into 3 aggressive search queries. Return JSON: {{'queries': []}}"}
        ], json_mode=True)
        
        queries = json.loads(initial_plan).get("queries", [])
        
        # 2. التنفيذ المتوازي
        tasks = [self._async_search(q) for q in queries]
        search_results = await asyncio.gather(*tasks)
        combined_data = "\n".join(search_results)

        # 3. الحلقة الانعكاسية
        current_report = ""
        for i in range(MAX_ITERATIONS):
            draft_prompt = f"Data: {combined_data}\nTask: Write a brutal, honest report on '{target}'."
            current_report = self._sync_llm([{"role": "user", "content": draft_prompt}])

            critic_prompt = f"Review this report:\n{current_report}\nIf good return JSON: {{ 'satisfied': true }}. If bad return {{ 'satisfied': false, 'new_query': '...' }}"
            critique = json.loads(self._sync_llm([{"role": "user", "content": critic_prompt}], json_mode=True))
            
            if critique.get("satisfied"):
                break
            else:
                new_q = critique.get("new_query")
                new_data = await self._async_search(new_q)
                combined_data += f"\n[New Evidence]: {new_data}"
        
        return current_report
