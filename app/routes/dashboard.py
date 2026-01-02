from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
import datetime
import json 
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    # القيم الافتراضية
    products_count = 0
    orders_count = 0
    total_views = 0
    conversion_rate = 0
    recent_orders = []
    my_products = []
    recent_activities = [] # <--- القائمة الجديدة للنشاطات

    try:
        # جلب الإحصائيات
        products_count = db.products.count_documents({}) 
        orders_count = db.orders.count_documents({}) 
        
        # جلب المنتجات
        my_products = list(db.products.find().sort("created_at", -1).limit(20))

        # حساب الزيارات
        pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
        views_result = list(db.products.aggregate(pipeline))
        if views_result:
            total_views = views_result[0]['total_views']
        
        if total_views > 0:
            conversion_rate = round((orders_count / total_views) * 100, 2)

        # جلب الطلبات
        recent_orders = list(db.orders.find().sort("created_at", -1).limit(5))
        
        # --- جلب النشاطات الحقيقية من قاعدة البيانات (Real Feed) ---
        # نجلب آخر 10 نشاطات مسجلة
        recent_activities = list(db.activity_logs.find().sort("timestamp", -1).limit(10))

    except Exception as e:
        print(f"⚠️ Database Warning: {e}")

    # لاحظ أننا حذفنا chart_data من هنا
    return render_template('dashboard/index.html', 
                           products_count=products_count,
                           orders_count=orders_count,
                           total_views=total_views,
                           conversion_rate=conversion_rate,
                           recent_orders=recent_orders,
                           my_products=my_products,
                           recent_activities=recent_activities) # تمرير النشاطات


@dashboard_bp.route('/products/new', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        try:
            # البيانات الأساسية
            name = request.form.get('name')
            price = float(request.form.get('price'))
            old_price = request.form.get('old_price') # قد يكون فارغاً
            description = request.form.get('description')
            
            # الصور (تأتي كسلسلة نصية JSON من الجافاسكريبت)
            images_json = request.form.get('images_list')
            images = json.loads(images_json) if images_json else []
            
            # المتغيرات (Colors & Sizes)
            colors_str = request.form.get('colors', '')
            sizes_str = request.form.get('sizes', '')
            
            colors = [c.strip() for c in colors_str.split(',') if c.strip()]
            sizes = [s.strip() for s in sizes_str.split(',') if s.strip()]
            
            # العروض والكوبونات
            offer_end_time = request.form.get('offer_end_time')
            coupon_value = request.form.get('coupon_value')
            coupon_code = request.form.get('coupon_code')
            
            # الذكاء الاصطناعي
            ai_instructions = request.form.get('ai_instructions')
            
            new_product = {
                "merchant_id": "admin_1", 
                "name": name,
                "price": price,
                "old_price": float(old_price) if old_price else None,
                "currency_symbol": "دج", # افتراضي
                "description": description,
                "product_type": "physical", # افتراضي للمنتجات الملموسة
                "images": images, # قائمة الصور
                "colors": colors, # قائمة الألوان
                "sizes": sizes,   # قائمة المقاسات
                "offer_end_time": offer_end_time, # تاريخ انتهاء العرض
                "coupon": {
                    "code": coupon_code,
                    "value": coupon_value
                } if coupon_code else None,
                "ai_instructions": ai_instructions,
                "created_at": datetime.datetime.utcnow(),
                "views": 0,
                "orders_count": 0,
                # إعدادات وهمية للبداية (Social Proof)
                "rating": 4.8, 
                "sales_count": 120 + int(datetime.datetime.now().timestamp() % 50) # رقم عشوائي للمبيعات
            }
            
            db.products.insert_one(new_product)
            return redirect(url_for('dashboard.index'))
        except Exception as e:
            return f"Error saving product: {e}"

    return render_template('dashboard/add_product.html')
