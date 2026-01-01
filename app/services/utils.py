from flask import current_app
from .db import get_collection

def get_merchant_api_keys(merchant_id):
    """
    جلب مفاتيح API الخاصة بالتاجر.
    إذا لم يملك مفاتيح خاصة، نستخدم مفاتيح المنصة (للتجربة فقط).
    """
    users_col = get_collection('users')
    merchant = users_col.find_one({"_id": merchant_id}, {"api_keys": 1, "settings": 1})

    # المفاتيح الافتراضية للمنصة (من ملف config.py)
    groq_key = current_app.config['PLATFORM_GROQ_KEY']
    gemini_key = current_app.config['PLATFORM_GEMINI_KEY']

    # إذا كان التاجر لديه مفاتيح خاصة، نستخدمها (الأولوية للتاجر)
    if merchant and "api_keys" in merchant:
        if merchant["api_keys"].get("groq_key"):
            groq_key = merchant["api_keys"]["groq_key"]
        
        if merchant["api_keys"].get("gemini_key"):
            gemini_key = merchant["api_keys"]["gemini_key"]

    return groq_key, gemini_key

def check_credit_balance(merchant_id):
    """
    فحص هل لدى التاجر رصيد كافٍ لإجراء محادثة؟
    """
    users_col = get_collection('users')
    merchant = users_col.find_one({"_id": merchant_id}, {"credits": 1})
    
    if merchant and merchant.get("credits", 0) > 0:
        return True
    return False

def deduct_credit(merchant_id):
    """
    خصم نقطة واحدة من رصيد التاجر
    """
    users_col = get_collection('users')
    users_col.update_one({"_id": merchant_id}, {"$inc": {"credits": -1}})
