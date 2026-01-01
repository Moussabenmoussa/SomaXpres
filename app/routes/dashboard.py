from flask import Blueprint, render_template, request, jsonify
from app.services.db import get_collection
from app.services.utils import TEMP_MEMORY # استيراد الذاكرة المؤقتة

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
def index():
    return render_template('dashboard.html')

@bp.route('/api/save-keys', methods=['POST'])
def save_keys():
    data = request.json
    
    # 1. الحفظ في الذاكرة المؤقتة فوراً (لضمان العمل)
    TEMP_MEMORY['groq_key'] = data.get('groq_key')
    TEMP_MEMORY['gemini_key'] = data.get('gemini_key')

    # 2. محاولة الحفظ في قاعدة البيانات (إن وجدت)
    users_col = get_collection('users')
    db_status = "Saved to Memory Only (DB Down)"
    
    if users_col is not None:
        try:
            users_col.update_one(
                {"_id": "demo_merchant_id"},
                {"$set": { "api_keys": data }},
                upsert=True
            )
            db_status = "Saved to DB"
        except Exception as e:
            print(f"DB Error: {e}")

    return jsonify({"success": True, "message": db_status})

@bp.route('/api/get-keys', methods=['GET'])
def get_keys():
    # محاولة الاسترجاع من الذاكرة أولاً
    keys = {
        "groq_key": TEMP_MEMORY.get('groq_key', ''),
        "gemini_key": TEMP_MEMORY.get('gemini_key', '')
    }
    
    # محاولة الاسترجاع من قاعدة البيانات إذا كانت الذاكرة فارغة
    if not keys['groq_key']:
        users_col = get_collection('users')
        if users_col is not None:
            try:
                merchant = users_col.find_one({"_id": "demo_merchant_id"}, {"api_keys": 1})
                if merchant and "api_keys" in merchant:
                    keys = merchant["api_keys"]
            except:
                pass
                
    return jsonify(keys)

@bp.route('/api/top-up', methods=['POST'])
def top_up():
    return jsonify({"success": True})
