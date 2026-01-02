from flask import Blueprint, render_template, request, jsonify, session, redirect
from app import db
from app.services.ai_agent import generate_sales_response
from bson.objectid import ObjectId
import datetime
import traceback

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def home():
    return redirect('/dashboard')

@public_bp.route('/p/<product_id>')
def product_page(product_id):
    try:
        if not ObjectId.is_valid(product_id):
            return "❌ Error: Invalid Product ID", 400

        product = db.products.find_one({"_id": ObjectId(product_id)})
        
        if not product:
            return "❌ Error: Product not found", 404
            
        db.products.update_one({"_id": ObjectId(product_id)}, {"$inc": {"views": 1}})
        return render_template('product.html', product=product)

    except Exception as e:
        error_trace = traceback.format_exc()
        return f"System Error: {str(e)}", 500

@public_bp.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        data = request.json
        user_message = data.get('message')
        product_id = data.get('product_id')
        history = data.get('history', []) 

        if not product_id or not ObjectId.is_valid(product_id):
             return jsonify({"response": "Error: Invalid Product ID"}), 400

        product = db.products.find_one({"_id": ObjectId(product_id)})
        if not product:
            return jsonify({"response": "Error: Product not found"}), 404

        history.append({"role": "user", "content": user_message})

        # 1. استدعاء الذكاء الاصطناعي
        ai_response = generate_sales_response(history, product)
        
        # 2. تسجيل النشاط الحقيقي في قاعدة البيانات (Real Logging)
        # سيتم عرض هذا في لوحة التحكم
        log_entry = {
            "type": "chat",
            "bot_name": product.get('bot_name', 'Agent'),
            "product_name": product.get('name', 'Unknown'),
            "action": "تفاعل مع زبون", # يمكن تطويره لاحقاً ليكون "إغلاق صفقة" حسب تحليل النص
            "timestamp": datetime.datetime.utcnow()
        }
        db.activity_logs.insert_one(log_entry)
        
        return jsonify({"response": ai_response})

    except Exception as e:
        return jsonify({"response": f"Server Error: {str(e)}"}), 500

