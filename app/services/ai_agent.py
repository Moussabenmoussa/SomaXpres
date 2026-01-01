import os
import requests
import base64
import struct
from groq import Groq

# ---------------------------------------------------------
# 👇 ضع مفاتيحك هنا
MY_GROQ_KEY = "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" 
MY_GEMINI_KEY = "AIzaSyCKKXguNfvGNCEaoC6oQF0mu05UEXtPI9M"
# ---------------------------------------------------------



PERSONAS = {
    "amine": { "name": "أمين", "voice_id": "Puck", "style": "شاب جزائري حريص وفاهم." },
    "sarah": { "name": "سارة", "voice_id": "Leda", "style": "فتاة منظمة ودقيقة." },
    "nadir": { "name": "نذير", "voice_id": "Fenrir", "style": "رسمي ومدقق." }
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
            return { "text": "المفتاح ناقص.", "audio": None }

        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        # تحويل التاريخ لنص للبحث فيه عن الأرقام
        history_text = str(history) + " " + user_input
        
        # 🔥 البرومبت المصفح (The Armored Prompt)
        system_prompt = f"""
        أنت '{selected_persona['name']}'، بائع جزائري لا يقبل الأخطاء.
        المنتج: {product_context}
        
        🚨 **قانون الأرقام الصارم (Number Law):**
        - انظر في المحادثة: هل يوجد رقم هاتف حقيقي (أرقام مثل 05, 06, 07)؟
        - **إذا لم تجد أرقاماً:** ممنوع منعاً باتاً تأكيد الطلب. حتى لو قال الزبون "نعم" أو "أكيد" أو "ابعث".
        - إذا قال "نعم" ولم يكتب الرقم، قل له: "**إيه، بصح ما عطيتنيش الرقم! أكتبهولي باش نسجله.**"
        
        🚨 **خوارزمية المحادثة:**
        1. **الفحص:** هل العنوان والهاتف (الأرقام) موجودان؟
        2. **النقص:** اطلب ما ينقص. (إذا أعطاك الولاية فقط، اطلب الهاتف والبلدية).
        3. **الفخ (التأكيد):**
           - فقط عندما تملك (العنوان + أرقام الهاتف)، قل:
           "صحيت. مالا [المنتج] لـ [العنوان]. الموزع يجي على جالك، **راك توجد الدراهم وترد عليه سير؟**"
        4. **الإغلاق:**
           - إذا وافق بعد الفخ -> "تم التأكيد."

        تكلم بالدارجة الجزائرية فقط. كن حازماً في طلب الرقم.
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history) 
        messages.append({"role": "user", "content": user_input})

        try:
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=90,
                temperature=0.2 # ذكاء بارد جداً (لا يتخيل معلومات غير موجودة)
            )
            ai_text = completion.choices[0].message.content

            audio_b64 = None
            if input_type == "voice" and self.gemini_key:
                raw_audio = self.generate_audio_raw(ai_text, selected_persona['voice_id'])
                if raw_audio:
                    audio_b64 = self.add_wav_header(raw_audio)

            return { "text": ai_text, "audio": audio_b64 }

        except Exception as e:
            print(f"❌ Error: {e}")
            return {"text": "كاين خلل، عاود؟", "audio": None}

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
