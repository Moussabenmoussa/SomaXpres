from flask import Blueprint, render_template, request, jsonify, session, redirect
from app import db
from app.services.ai_agent import generate_sales_response
from bson.objectid import ObjectId
import traceback # مكتبة لتتبع الأخطاء

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def home():
    return redirect('/dashboard')

@public_bp.route('/p/<product_id>')
def product_page(product_id):
    try:
        # 1. التحقق من شكل المعرف
        if not ObjectId.is_valid(product_id):
            return "❌ Error: Invalid Product ID Format (المعرف غير صحيح)", 400

        # 2. البحث عن المنتج
        product = db.products.find_one({"_id": ObjectId(product_id)})
        
        if not product:
            return "❌ Error: Product not found in Database (المنتج غير موجود في قاعدة البيانات)", 404
            
        # 3. محاولة عرض القالب
        # زيادة عدد الزيارات
        db.products.update_one({"_id": ObjectId(product_id)}, {"$inc": {"views": 1}})
        
        return render_template('product.html', product=product)

    except Exception as e:
        # 4. طباعة الخطأ الحقيقي على الشاشة
        error_trace = traceback.format_exc()
        return f"""
        <div style="padding: 20px; font-family: monospace; direction: ltr;">
            <h2 style="color: red;">⚠️ System Error Details</h2>
            <p><b>Error Message:</b> {str(e)}</p>
            <hr>
            <pre style="background: #f4f4f4; padding: 10px;">{error_trace}</pre>
        </div>
        """, 500

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

        ai_response = generate_sales_response(history, product)
        
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"response": f"Server Error: {str(e)}"}), 500
