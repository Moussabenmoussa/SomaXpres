from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
import datetime

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    # 1. تعريف قيم افتراضية (أصفار) لتجنب تعطل الموقع إذا فشلت قاعدة البيانات
    chart_data = {
        "labels": ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"],
        "visits": [0, 0, 0, 0, 0, 0, 0],
        "orders": [0, 0, 0, 0, 0, 0, 0]
    }
    products_count = 0
    orders_count = 0
    total_views = 0
    conversion_rate = 0
    recent_orders = []

    try:
        # 2. محاولة جلب البيانات الحقيقية
        # إذا كان هناك خطأ في الاتصال، سينتقل الكود فوراً إلى except ولن يتعطل
        products_count = db.products.count_documents({}) 
        orders_count = db.orders.count_documents({}) 
        
        # حساب الزيارات
        pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
        views_result = list(db.products.aggregate(pipeline))
        if views_result:
            total_views = views_result[0]['total_views']
        
        # حساب نسبة التحويل
        if total_views > 0:
            conversion_rate = round((orders_count / total_views) * 100, 2)

        # جلب آخر الطلبات
        recent_orders = list(db.orders.find().sort("created_at", -1).limit(5))
        
        # تحديث بيانات الرسم البياني (هنا نضع بيانات وهمية للزيارات الحالية كمثال)
        # في التطوير المستقبلي سنربطها بالتواريخ الحقيقية
        chart_data["visits"] = [10, 25, 15, 30, 40, 20, total_views]
        chart_data["orders"] = [1, 2, 0, 3, 5, 2, orders_count]

    except Exception as e:
        # طباعة الخطأ في السجلات (Logs) فقط، وعدم إيقاف الموقع
        print(f"⚠️ Database Error: {e}")

    # 3. عرض الصفحة (الآن المتغيرات مضمونة الوجود سواء نجح الاتصال أم فشل)
    return render_template('dashboard/index.html', 
                           products_count=products_count,
                           orders_count=orders_count,
                           total_views=total_views,
                           conversion_rate=conversion_rate,
                           recent_orders=recent_orders,
                           chart_data=chart_data) # <--- هذا هو المتغير الذي كان مفقوداً

# --- دالة إضافة المنتج ---
@dashboard_bp.route('/products/new', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            price = float(request.form.get('price'))
            currency = request.form.get('currency', '$')
            description = request.form.get('description')
            product_type = request.form.get('product_type')
            image_url = request.form.get('image_url')
            bot_name = request.form.get('bot_name')
            ai_instructions = request.form.get('ai_instructions')
            
            new_product = {
                "merchant_id": "admin_1", 
                "name": name,
                "price": price,
                "currency_symbol": currency,
                "description": description,
                "product_type": product_type,
                "images": [image_url] if image_url else [],
                "bot_name": bot_name,
                "ai_instructions": ai_instructions,
                "created_at": datetime.datetime.utcnow(),
                "views": 0,
                "orders_count": 0
            }
            
            db.products.insert_one(new_product)
            return redirect(url_for('dashboard.index'))
        except Exception as e:
            return f"Error saving pro
