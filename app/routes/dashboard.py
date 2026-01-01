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
    if users_col:
        users_col.update_one(
            {"_id": "demo_merchant_id"},
            {"$set": { "api_keys": data }},
            upsert=True
        )
    return jsonify({"success": True})
