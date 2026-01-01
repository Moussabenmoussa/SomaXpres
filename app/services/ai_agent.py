import os
import requests
from groq import Groq

# ---------------------------------------------------------
# 👇 ضع مفاتيحك هنا مباشرة (بين علامات التنصيص)
MY_GROQ_KEY = "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" 
MY_GEMINI_KEY = "AIzaSyCKKXguNfvGNCEaoC6oQF0mu05UEXtPI9M"
# ---------------------------------------------------------

PERSONAS = {
    "amine": { "name": "أمين", "voice_id": "Puck", "style": "شاب جزائري عفوي." },
    "sarah": { "name": "سارة", "voice_id": "Leda", "style": "فتاة لطيفة وجذابة." },
    "nadir": { "name": "نذير", "voice_id": "Fenrir", "style": "رسمي ومحترم." }
}

class AIAgent:
    def __init__(self, groq_key=None, gemini_key=None):
        # نستخدم المفتاح المكتوب يدوياً في الأعلى لتجنب مشاكل قاعدة البيانات
        final_groq_key = MY_GROQ_KEY
        final_gemini_key = MY_GEMINI_KEY

        if "gsk_" not in final_groq_key:
            print("❌ خطأ: لم يتم وضع مفتاح Groq الصحيح في الكود!")
            self.groq_client = None
        else:
            self.groq_client = Groq(api_key=final_groq_key)
            
        self.gemini_key = final_gemini_key

    def think_and_speak(self, user_input, history, product_context, merchant_rules, persona="amine", input_type="text"):
        if not self.groq_client:
            return {
                "text": "يا شريكي، راك نسيت تحط المفتاح في ملف ai_agent.py 🛑",
                "audio": None
            }

        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        system_prompt = f"""
        أنت '{selected_persona['name']}'، مساعد مبيعات.
        الأسلوب: {selected_persona['style']}
        المنتج: {product_context}
        القوانين: {merchant_rules}
        كن مختصراً جداً (أقل من 20 كلمة).
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": user_input})

        try:
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=60,
                temperature=0.6
            )
            ai_text = completion.choices[0].message.content

            audio_b64 = None
            # توليد الصوت فقط إذا كان المفتاح موجوداً والطلب صوتي
            if input_type == "voice" and self.gemini_key and "AIza" in self.gemini_key:
                audio_b64 = self.generate_audio(ai_text, selected_persona['voice_id'])

            return { "text": ai_text, "audio": audio_b64 }

        except Exception as e:
            print(f"❌ AI Error: {e}")
            return {"text": "سمحلي، كاين مشكل تقني في عقلي.", "audio": None}

    def generate_audio(self, text, voice_name):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{ "parts": [{ "text": text }] }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": { "voiceConfig": { "prebuiltVoiceConfig": { "voiceName": voice_name } } }
            }
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['inlineData']['data']
            return None
        except:
            return None
