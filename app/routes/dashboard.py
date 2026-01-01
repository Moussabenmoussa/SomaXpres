from flask import Blueprint, render_template, request, jsonify
from app.services.db import get_collection
from app.services.utils import TEMP_MEMORY

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
def index():
    return render_template('dashboard.html')

# --- إدارة المنتجات (الجديد) ---
@bp.route('/api/add-product', methods=['POST'])
def add_product():
    data = request.json
    products_col = get_collection('products')
    
    if products_col is not None:
        new_product = {
            "merchant_id": "demo_merchant_id",
            "name": data.get('name'),
            "price": data.get('price'),
            "image": data.get('image') or "https://placehold.co/600x400?text=No+Image",
            # هنا نحفظ الدماغ الخاص بالمنتج
            "ai_instructions": data.get('ai_instructions', ''), 
            "views": 0,
            "orders_count": 0
        }
        result = products_col.insert_one(new_product)
        return jsonify({"success": True, "product_id": str(result.inserted_id)})
    
    # في حالة عدم وجود قاعدة بيانات، نستخدم الذاكرة المؤقتة (للتجربة فقط)
    # (هذا الجزء احتياطي لكي لا يتوقف السيرفر)
    import uuid
    fake_id = str(uuid.uuid4())
    TEMP_MEMORY[f"prod_{fake_id}"] = data
    return jsonify({"success": True, "product_id": f"temp_{fake_id}"})


# --- إدارة المفاتيح (القديم - ضروري) ---
@bp.route('/api/save-keys', methods=['POST'])
def save_keys():
    data = request.json
    # الحفظ في الذاكرة المؤقتة أولاً (للأمان)
    TEMP_MEMORY['groq_key'] = data.get('groq_key')
    TEMP_MEMORY['gemini_key'] = data.get('gemini_key')

    # الحفظ في قاعدة البيانات
    users_col = get_collection('users')
    if users_col is not None:
        try:
            users_col.update_one(
                {"_id": "demo_merchant_id"},
                {"$set": { "api_keys": data }},
                upsert=True
            )
        except: pass
    return jsonify({"success": True})

@bp.route('/api/get-keys', methods=['GET'])
def get_keys():
    # محاولة من الذاكرة
    keys = {
        "groq_key": TEMP_MEMORY.get('groq_key', ''),
        "gemini_key": TEMP_MEMORY.get('gemini_key', '')
    }
    # محاولة من قاعدة البيانات
    if not keys['groq_key']:
        users_col = get_collection('users')
        if users_col is not None:
            merchant = users_col.find_one({"_id": "demo_merchant_id"}, {"api_keys": 1})
            if merchant: keys = merchant.get("api_keys", keys)
            
    return jsonify(keys)
