from flask import current_app
from .db import get_collection

# ✅ هذا المتغير ضروري جداً لمنع الانهيار
TEMP_MEMORY = {}

def get_merchant_api_keys(merchant_id):
    """جلب المفاتيح بأمان من القاعدة أو الذاكرة"""
    groq_key = None
    gemini_key = None

    # 1. محاولة من الذاكرة المؤقتة أولاً (الأسرع والأضمن)
    groq_key = TEMP_MEMORY.get('groq_key')
    gemini_key = TEMP_MEMORY.get('gemini_key')

    # 2. محاولة من قاعدة البيانات (إذا لم نجد في الذاكرة)
    if not groq_key:
        try:
            users_col = get_collection('users')
            if users_col:
                merchant = users_col.find_one({"_id": merchant_id}, {"api_keys": 1})
                if merchant and "api_keys" in merchant:
                    groq_key = merchant["api_keys"].get("groq_key")
                    gemini_key = merchant["api_keys"].get("gemini_key")
        except:
            pass

    # 3. محاولة من إعدادات النظام (config)
    if not groq_key:
        groq_key = current_app.config.get('PLATFORM_GROQ_KEY')
    if not gemini_key:
        gemini_key = current_app.config.get('PLATFORM_GEMINI_KEY')

    return groq_key, gemini_key

def check_credit_balance(merchant_id):
    return True # تجاوز الرصيد حالياً

def deduct_credit(merchant_id):
    try:
        users_col = get_collection('users')
        if users_col:
            users_col.update_one({"_id": merchant_id}, {"$inc": {"credits": -1}})
    except:
        pass
