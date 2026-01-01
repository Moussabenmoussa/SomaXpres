from flask import Blueprint, render_template, request, jsonify
from app.services.db import get_collection

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
def index():
    return render_template('dashboard.html')

@bp.route('/api/save-keys', methods=['POST'])
def save_keys():
    data = request.json
    users_col = get_collection('users')
    if users_col is not None:
        users_col.update_one(
            {"_id": "demo_merchant_id"},
            {"$set": { "api_keys": data }},
            upsert=True
        )
        return jsonify({"success": True, "message": "تم الحفظ"})
    return jsonify({"success": False, "message": "خطأ في قاعدة البيانات"}), 500

@bp.route('/api/get-keys', methods=['GET'])
def get_keys():
    users_col = get_collection('users')
    if users_col is not None:
        merchant = users_col.find_one({"_id": "demo_merchant_id"}, {"api_keys": 1})
        if merchant and "api_keys" in merchant:
            return jsonify(merchant["api_keys"])
    return jsonify({"groq_key": "", "gemini_key": ""})

@bp.route('/api/top-up', methods=['POST'])
def top_up():
    users_col = get_collection('users')
    if users_col is not None:
        users_col.update_one(
            {"_id": "demo_merchant_id"},
            {"$inc": {"credits": 50}},
            upsert=True
        )
        return jsonify({"success": True})
    return jsonify({"error": "DB Error"}), 500
