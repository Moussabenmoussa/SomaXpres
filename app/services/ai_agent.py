import os
import json
import base64
import requests
from groq import Groq

# تعريف الشخصيات (الأقنعة)
PERSONAS = {
    "amine": {
        "name": "أمين",
        "voice_id": "Puck", # صوت شبابي
        "style": "شاب جزائري 'رجلة' وعفوي. استخدم الدارجة المباشرة (خويا، المعلم، السلعة شابة).",
        "tone": "energetic"
    },
    "sarah": {
        "name": "سارة",
        "voice_id": "Leda", # صوت نسائي ناعم
        "style": "فتاة جزائرية لطيفة جداً وحنونة. استخدمي كلمات (يا عمري، عزيزي، يهبّل). كوني جذابة للمبيعات.",
        "tone": "warm"
    },
    "nadir": {
        "name": "نذير",
        "voice_id": "Fenrir", # صوت عميق ورسمي
        "style": "مساعد إداري محترم ورسمي. استخدم الفصحى المبسطة أو دارجة مهذبة جداً. ركز على الضمان والثقة.",
        "tone": "professional"
    }
}

class AIAgent:
    def __init__(self, groq_key, gemini_key):
        self.groq_client = Groq(api_key=groq_key)
        self.gemini_key = gemini_key

    def think_and_speak(self, user_input, history, product_context, merchant_rules, persona="amine", input_type="text"):
        """
        الدالة الموحدة: تفكر بـ Groq وترد بـ Gemini (إذا كان صوتياً)
        """
        # 1. إعداد الشخصية
        selected_persona = PERSONAS.get(persona, PERSONAS["amine"])
        
        # 2. هندسة البرومبت (The Prompt Engineering)
        system_prompt = f"""
        أنت '{selected_persona['name']}'، مساعد مبيعات ذكي في الجزائر.
        الأسلوب: {selected_persona['style']}
        
        📦 **المنتج:** {product_context}
        ⛔ **القوانين:** {merchant_rules}
        
        🚨 **قواعد صارمة:**
        1. ردك يجب أن يكون أقل من 20 كلمة (توفير التوكنات).
        2. اطرح سؤالاً واحداً فقط في كل مرة.
        3. هدفك: أخذ الولاية ورقم الهاتف وتأكيد الطلب.
        """

        # 3. إعداد الرسائل لـ Groq
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:]) # ذاكرة قصيرة (آخر 4 ردود)
        messages.append({"role": "user", "content": user_input})

        try:
            # 4. استدعاء العقل (Groq)
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=60, # تقييد الطول
                temperature=0.6
            )
            ai_text = completion.choices[0].message.content

            # 5. إذا كان الطلب صوتياً -> حوّل النص لصوت
            audio_b64 = None
            if input_type == "voice":
                audio_b64 = self.generate_audio(ai_text, selected_persona['voice_id'])

            return {
                "text": ai_text,
                "audio": audio_b64, # سيكون None إذا كان شات كتابي
                "persona": persona
            }

        except Exception as e:
            print(f"❌ AI Error: {e}")
            return {"text": "سمحلي خويا، الشبكة راهي ثقيلة، عاود قولي؟", "audio": None}

    def generate_audio(self, text, voice_name):
        """
        تحويل النص لصوت باستخدام Gemini TTS API
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={self.gemini_key}"
        
        payload = {
            "contents": [{ "parts": [{ "text": text }] }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": { "voiceName": voice_name }
                    }
                }
            }
        }

        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                result = response.json()
                # استخراج الصوت (Base64)
                audio_data = result['candidates'][0]['content']['parts'][0]['inlineData']['data']
                return audio_data
            else:
                print(f"❌ Gemini TTS Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Audio Generation Error: {e}")
            return None
