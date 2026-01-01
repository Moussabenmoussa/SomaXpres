import os
import requests
import base64
import struct
from groq import Groq

# ---------------------------------------------------------
# 👇 ضع مفاتيحك هنا مباشرة لتجنب أي مشاكل
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
        # نستخدم المفاتيح المكتوبة يدوياً للأمان
        self.groq_key = MY_GROQ_KEY
        self.gemini_key = MY_GEMINI_KEY
        
        if self.groq_key and "gsk_" in self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)
        else:
            self.groq_client = None
            print("❌ خطأ: مفتاح Groq مفقود أو غير صحيح.")

    def think_and_speak(self, user_input, history, product_context, merchant_rules, persona="amine", input_type="text"):
        if not self.groq_client:
            return { "text": "يا شريكي، تأكد من مفتاح Groq في الكود!", "audio": None }

        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        system_prompt = f"""
        أنت '{selected_persona['name']}'، مساعد مبيعات.
        الأسلوب: {selected_persona['style']}
        المنتج: {product_context}
        القوانين: {merchant_rules}
        رد بلهجة جزائرية مفهومة. كن مختصراً جداً (أقل من 20 كلمة).
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": user_input})

        try:
            # 1. التفكير (Groq)
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=70,
                temperature=0.6
            )
            ai_text = completion.choices[0].message.content

            # 2. التحدث (Gemini) - فقط إذا كان الطلب صوتياً
            audio_b64 = None
            if input_type == "voice" and self.gemini_key:
                # جلب البيانات الخام
                raw_audio = self.generate_audio_raw(ai_text, selected_persona['voice_id'])
                if raw_audio:
                    # ✅ الخطوة الحاسمة: تحويل الخام إلى WAV
                    audio_b64 = self.add_wav_header(raw_audio)
                else:
                    print("⚠️ تحذير: فشل توليد الصوت من Gemini")

            return { "text": ai_text, "audio": audio_b64 }

        except Exception as e:
            print(f"❌ خطأ عام في الذكاء الاصطناعي: {e}")
            return {"text": "سمحلي، كاين خلل تقني بسيط.", "audio": None}

    def generate_audio_raw(self, text, voice_name):
        """جلب البيانات الصوتية الخام من Gemini"""
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
                # Gemini يعيد الصوت بصيغة Base64 خام (PCM)
                b64_data = response.json()['candidates'][0]['content']['parts'][0]['inlineData']['data']
                return base64.b64decode(b64_data)
            else:
                print(f"❌ خطأ Gemini API: {response.text}")
                return None
        except Exception as e:
            print(f"❌ خطأ اتصال بـ Gemini: {e}")
            return None

    def add_wav_header(self, pcm_data, sample_rate=24000):
        """إضافة ترويسة WAV لكي يفهم المتصفح الملف"""
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_data)
        
        # هيكل ملف WAV القياسي (44 بايت)
        header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + data_size,
            b'WAVE',
            b'fmt ',
            16,
            1, # PCM format
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b'data',
            data_size
        )
        
        # دمج الرأس مع البيانات وتشفيرها مجدداً
        wav_bytes = header + pcm_data
        return base64.b64encode(wav_bytes).decode('utf-8')
