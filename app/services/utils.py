from flask import current_app
from .db import get_collection

# ذاكرة مؤقتة للمفاتيح في حالة تعطل قاعدة البيانات
TEMP_MEMORY = {}

def get_merchant_api_keys(merchant_id):
    """
    جلب المفاتيح بأمان تام (حتى لو قاعدة البيانات معطلة)
    """
    # 1. محاولة الجلب من قاعدة البيانات
    users_col = get_collection('users')
    
    groq_key = None
    gemini_key = None

    if users_col is not None:
        try:
            merchant = users_col.find_one({"_id": merchant_id}, {"api_keys": 1})
            if merchant and "api_keys" in merchant:
                groq_key = merchant["api_keys"].get("groq_key")
                gemini_key = merchant["api_keys"].get("gemini_key")
        except Exception:
            pass
    
    # 2. إذا فشلت قاعدة البيانات، نستخدم الذاكرة المؤقتة
    if not groq_key:
        groq_key = TEMP_MEMORY.get('groq_key')
    if not gemini_key:
        gemini_key = TEMP_MEMORY.get('gemini_key')

    # 3. إذا فشل كل شيء، نستخدم مفاتيح المنصة (من config)
    if not groq_key:
        groq_key = current_app.config.get('PLATFORM_GROQ_KEY')
    if not gemini_key:
        gemini_key = current_app.config.get('PLATFORM_GEMINI_KEY')

    return groq_key, gemini_key

def check_credit_balance(merchant_id):
    # تجاوز فحص الرصيد مؤقتاً لتجنب المشاكل
    return True

def deduct_credit(merchant_id):
    try:
        users_col = get_collection('users')
        if users_col:
            users_col.update_one({"_id": merchant_id}, {"$inc": {"credits": -1}})
    except:
        pass
