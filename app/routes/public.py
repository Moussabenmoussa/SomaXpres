from flask import Blueprint, render_template, request, jsonify, session, redirect
from app import db
from app.services.ai_agent import generate_sales_response
from bson.objectid import ObjectId

public_bp = Blueprint('public', __name__)

# --- هذا هو الإصلاح (الجديد) ---
@public_bp.route('/')
def home():
    # يوجه الزائر مباشرة للوحة التحكم بدلاً من الخطأ 404
    return redirect('/dashboard')
# -----------------------------

@public_bp.route('/p/<product_id>')
def product_page(product_id):
    # جلب المنتج من قاعدة البيانات
    try:
        if not ObjectId.is_valid(product_id):
            return "Invalid Product ID", 404

        product = db.products.find_one({"_id": ObjectId(product_id)})
        
        if not product:
            return "Product not found", 404
            
        # زيادة عدد الزيارات
        db.products.update_one({"_id": ObjectId(product_id)}, {"$inc": {"views": 1}})
        
        return render_template('product.html', product=product)
    except Exception as e:
        print(f"Error: {e}")
        return "System Error", 500

@public_bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_message = data.get('message')
    product_id = data.get('product_id')
    history = data.get('history', []) 

    # التحقق من صحة المعرف
    if not product_id or not ObjectId.is_valid(product_id):
         return jsonify({"response": "Error: Invalid Product ID"}), 400

    product = db.products.find_one({"_id": ObjectId(product_id)})
    
    if not product:
        return jsonify({"response": "Error: Product not found"}), 404

    # إضافة رسالة الزبون
    history.append({"role": "user", "content": user_message})

    # استدعاء الذكاء الاصطناعي
    ai_response = generate_sales_response(history, product)
    
    return jsonify({"response": ai_response})
