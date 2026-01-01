import os
import requests
import base64
import struct
from groq import Groq

# ---------------------------------------------------------
# 👇 ضع مفاتيحك هنا مباشرة
MY_GROQ_KEY = "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" 
MY_GEMINI_KEY = "AIzaSyCKKXguNfvGNCEaoC6oQF0mu05UEXtPI9M"
# ---------------------------------------------------------

PERSONAS = {
    "amine": { "name": "أمين", "voice_id": "Puck", "style": "شاب جزائري عفوي، عملي وسريع." },
    "sarah": { "name": "سارة", "voice_id": "Leda", "style": "فتاة لطيفة وجذابة." },
    "nadir": { "name": "نذير", "voice_id": "Fenrir", "style": "رسمي ومحترم." }
}

class AIAgent:
    def __init__(self, groq_key=None, gemini_key=None):
        self.groq_key = MY_GROQ_KEY
        self.gemini_key = MY_GEMINI_KEY
        
        if self.groq_key and "gsk_" in self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)
        else:
            self.groq_client = None

    def think_and_speak(self, user_input, history, product_context, merchant_rules, persona="amine", input_type="text"):
        if not self.groq_client:
            return { "text": "يا شريكي، تأكد من مفتاح Groq في الكود!", "audio": None }

        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        # 🔥 هذا هو "الدماغ الجديد" (Checklist System)
        system_prompt = f"""
        أنت '{selected_persona['name']}'، بائع محترف هدفه الوحيد: **تأكيد الطلبية**.
        المنتج: {product_context}
        
        🚨 **خوارزمية العمل (طبقها بصرامة):**
        1. **تحليل الحالة:** اقرأ تاريخ المحادثة. ماذا ينقصنا؟ (العنوان؟ أم الهاتف؟).
        2. **المرحلة 1 (البداية):** إذا لم يكن لديك العنوان -> اطلب الولاية والبلدية مباشرة.
        3. **المرحلة 2 (الوسط):** إذا أعطاك العنوان -> اطلب رقم الهاتف فوراً (مثال: "صحيت، واش هو رقم هاتفك؟").
        4. **المرحلة 3 (النهاية):** إذا أعطاك الهاتف -> أكد الطلب بكلمة "سي بون" وأغلق المحادثة.
        
        ⛔ **ممنوعات قاتلة:**
        - **لا ترحب مرتين:** إذا كانت المحادثة قد بدأت، لا تقل "مرحباً أنا أمين" مرة أخرى. ادخل في الموضوع.
        - **لا تذكر السعر:** إلا إذا سألك الزبون عنه صراحة.
        - **لا تفلسف:** رد بجملة واحدة قصيرة (أقل من 15 كلمة).
        - **العنوان:** إذا قال "بسكرة"، لا تقل "بسكرة جميلة"، بل قل "وين بالضبط في بسكرة؟" أو "هات رقمك".

        أسلوب الكلام: {selected_persona['style']}
        """

        messages = [{"role": "system", "content": system_prompt}]
        # نرسل كل التاريخ ليعرف الروبوت أين وصلنا (وليس آخر 4 فقط لتجنب الزهايمر)
        messages.extend(history) 
        messages.append({"role": "user", "content": user_input})

        try:
            # 1. التفكير (Groq)
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=60, # تقييد الرد ليكون قصيراً جداً
                temperature=0.3 # تقليل الإبداع لزيادة الالتزام بالتعليمات
            )
            ai_text = completion.choices[0].message.content

            # 2. التحدث (Gemini)
            audio_b64 = None
            if input_type == "voice" and self.gemini_key:
                raw_audio = self.generate_audio_raw(ai_text, selected_persona['voice_id'])
                if raw_audio:
                    audio_b64 = self.add_wav_header(raw_audio)

            return { "text": ai_text, "audio": audio_b64 }

        except Exception as e:
            print(f"❌ Error: {e}")
            return {"text": "سمحلي، عاود قولي؟", "audio": None}

    def generate_audio_raw(self, text, voice_name):
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
                b64_data = response.json()['candidates'][0]['content']['parts'][0]['inlineData']['data']
                return base64.b64decode(b64_data)
            return None
        except:
            return None

    def add_wav_header(self, pcm_data, sample_rate=24000):
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_data)
        header = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16, 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample, b'data', data_size)
        return base64.b64encode(header + pcm_data).decode('utf-8')
