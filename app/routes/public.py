from flask import Blueprint, render_template, request, jsonify, session
from app import db
from app.services.ai_agent import generate_sales_response
from bson.objectid import ObjectId
import datetime

public_bp = Blueprint('public', __name__)

@public_bp.route('/p/<product_id>')
def product_page(product_id):
    # جلب المنتج من قاعدة البيانات
    try:
        product = db.products.find_one({"_id": ObjectId(product_id)})
        if not product:
            return "Product not found", 404
            
        # زيادة عدد الزيارات
        db.products.update_one({"_id": ObjectId(product_id)}, {"$inc": {"views": 1}})
        
        return render_template('product.html', product=product)
    except:
        return "Invalid Product ID", 404

@public_bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_message = data.get('message')
    product_id = data.get('product_id')
    history = data.get('history', []) # المحادثة تأتي من الفرونت اند

    product = db.products.find_one({"_id": ObjectId(product_id)})
    
    if not product:
        return jsonify({"response": "Error: Product not found"}), 404

    # إضافة رسالة الزبون للسجل المؤقت للمعالجة
    history.append({"role": "user", "content": user_message})

    # استدعاء الذكاء الاصطناعي
    ai_response = generate_sales_response(history, product)
    
    # (اختياري) هنا يمكن تحليل الرد لمعرفة هل تم "تأكيد الطلب" وحفظه في DB
    
    return jsonify({"response": ai_response})
