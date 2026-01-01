from flask import current_app
from .db import get_collection

def get_merchant_api_keys(merchant_id):
    users_col = get_collection('users')
    # تأكد من أن users_col ليس None قبل البحث
    if users_col is None:
        return current_app.config['PLATFORM_GROQ_KEY'], current_app.config['PLATFORM_GEMINI_KEY']

    merchant = users_col.find_one({"_id": merchant_id}, {"api_keys": 1})

    groq_key = current_app.config['PLATFORM_GROQ_KEY']
    gemini_key = current_app.config['PLATFORM_GEMINI_KEY']

    if merchant and "api_keys" in merchant:
        if merchant["api_keys"].get("groq_key"):
            groq_key = merchant["api_keys"]["groq_key"]
        if merchant["api_keys"].get("gemini_key"):
            gemini_key = merchant["api_keys"]["gemini_key"]

    return groq_key, gemini_key

def check_credit_balance(merchant_id):
    users_col = get_collection('users')
    if users_col is None: return True # للسماح بالعمل دون قاعدة بيانات مؤقتاً
    merchant = users_col.find_one({"_id": merchant_id}, {"credits": 1})
    if merchant and merchant.get("credits", 0) > 0:
        return True
    return False # غير إلى True للتجربة المجانية إذا أردت

def deduct_credit(merchant_id):
    users_col = get_collection('users')
    if users_col:
        users_col.update_one({"_id": merchant_id}, {"$inc": {"credits": -1}})
