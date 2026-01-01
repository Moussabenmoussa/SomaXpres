import os
import requests
import base64
import struct
from groq import Groq

PERSONAS = {
    "amine": { "name": "أمين", "voice_id": "Puck", "style": "شاب جزائري عفوي." },
    "sarah": { "name": "سارة", "voice_id": "Leda", "style": "فتاة لطيفة وجذابة." },
    "nadir": { "name": "نذير", "voice_id": "Fenrir", "style": "رسمي ومحترم." }
}

class AIAgent:
    def __init__(self, groq_key, gemini_key):
        if groq_key:
            self.groq_client = Groq(api_key=groq_key)
        else:
            self.groq_client = None
        self.gemini_key = gemini_key

    def think_and_speak(self, user_input, history, product_context, merchant_rules, persona="amine", input_type="text"):
        if not self.groq_client:
            return { "text": "يرجى وضع مفتاح Groq API في لوحة التحكم.", "audio": None }

        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        system_prompt = f"""
        أنت '{selected_persona['name']}'، مساعد مبيعات.
        الأسلوب: {selected_persona['style']}
        المنتج: {product_context}
        القوانين: {merchant_rules}
        كن مختصراً جداً (أقصى حد 20 كلمة).
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": user_input})

        try:
            # 1. التفكير (Groq)
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=60,
                temperature=0.6
            )
            ai_text = completion.choices[0].message.content

            # 2. التحدث (Gemini)
            audio_b64 = None
            if input_type == "voice" and self.gemini_key:
                raw_audio = self.generate_audio_raw(ai_text, selected_persona['voice_id'])
                if raw_audio:
                    # تحويل البيانات الخام إلى ملف WAV قابل للتشغيل
                    audio_b64 = self.add_wav_header(raw_audio)

            return { "text": ai_text, "audio": audio_b64 }

        except Exception as e:
            print(f"AI Error: {e}")
            return {"text": "سمحلي، حدث خطأ بسيط.", "audio": None}

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
                print(f"Gemini API Error: {response.text}")
                return None
        except Exception as e:
            print(f"Request Error: {e}")
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
