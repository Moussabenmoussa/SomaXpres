from flask import Blueprint, render_template, request, jsonify
from app.services.db import get_collection

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
def index():
    return render_template('dashboard.html')

# حفظ مفاتيح API
@bp.route('/api/save-keys', methods=['POST'])
def save_keys():
    data = request.json
    merchant_id = "demo_merchant_id" # تاجر افتراضي
    
    users_col = get_collection('users')
    
    # تحديث أو إنشاء التاجر
    users_col.update_one(
        {"_id": merchant_id},
        {"$set": {
            "api_keys": {
                "groq_key": data.get('groq_key'),
                "gemini_key": data.get('gemini_key')
            }
        }},
        upsert=True
    )
    
    return jsonify({"success": True, "message": "تم حفظ المفاتيح بنجاح!"})

# شحن الرصيد (تجريبي)
@bp.route('/api/top-up', methods=['POST'])
def top_up():
    merchant_id = "demo_merchant_id"
    users_col = get_collection('users')
    
    users_col.update_one(
        {"_id": merchant_id},
        {"$inc": {"credits": 50}}, # شحن 50 نقطة
        upsert=True
    )
    return jsonify({"success": True, "new_balance": "تم الشحن!"})
