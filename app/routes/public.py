from flask import Blueprint, render_template, request, jsonify, redirect
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
            
        # زيادة عدد الزيارات
        db.products.update_one({"_id": ObjectId(product_id)}, {"$inc": {"views": 1}})
        
        return render_template('product.html', product=product)

    except Exception as e:
        error_trace = traceback.format_exc()
        return f"System Error: {str(e)}", 500

# --- مسار جديد: استقبال الطلب من الاستمارة (Form Order) ---
@public_bp.route('/api/order/new', methods=['POST'])
def new_order_api():
    try:
        data = request.json
        
        # التحقق من البيانات
        if not data.get('phone') or not data.get('wilaya'):
            return jsonify({"success": False, "msg": "يرجى إدخال الهاتف والولاية"}), 400

        new_order = {
            "merchant_id": "admin_1", # في المستقبل سيكون ديناميكياً
            "product_id": data.get('product_id'),
            "product_name": data.get('product_name'),
            "customer_name": data.get('name'),
            "customer_phone": data.get('phone'),
            "customer_wilaya": data.get('wilaya'),
            "customer_commune": data.get('commune'), # البلدية
            "quantity": data.get('quantity', 1),
            "variant_color": data.get('color'),
            "variant_size": data.get('size'),
            "total_price": data.get('total_price'),
            "status": "pending", # قيد المراجعة
            "source": "form", # لتمييز الطلب (جاء من الاستمارة وليس الشات)
            "created_at": datetime.datetime.utcnow()
        }
        
        # حفظ الطلب
        db.orders.insert_one(new_order)
        
        # تسجيل النشاط في Live Feed
        db.activity_logs.insert_one({
            "type": "order",
            "bot_name": "System",
            "product_name": data.get('product_name'),
            "action": "New Order (Form)",
            "timestamp": datetime.datetime.utcnow()
        })

        return jsonify({"success": True, "msg": "تم استلام طلبك بنجاح!"})

    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

# --- مسار الشات (موجود سابقاً) ---
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
        
        # تسجيل نشاط الشات
        db.activity_logs.insert_one({
            "type": "chat",
            "bot_name": product.get('bot_name', 'Agent'),
            "product_name": product.get('name', 'Unknown'),
            "action": "Talking to customer",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return jsonify({"response": ai_response})

    except Exception as e:
        return jsonify({"response": f"Server Error: {str(e)}"}), 500
