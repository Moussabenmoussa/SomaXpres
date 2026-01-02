from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
from functools import wraps
import datetime
import json

dashboard_bp = Blueprint('dashboard', __name__)

# دالة الحماية (تمنع الدخول بدون تسجيل)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@dashboard_bp.route('/')
@login_required
def index():
    chart_data = {"labels": [], "visits": [], "orders": []}
    products_count = 0
    orders_count = 0
    total_views = 0
    conversion_rate = 0
    recent_orders = []
    my_products = []
    recent_activities = []

    try:
        products_count = db.products.count_documents({}) 
        orders_count = db.orders.count_documents({}) 
        my_products = list(db.products.find().sort("created_at", -1).limit(20))
        
        pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
        views_result = list(db.products.aggregate(pipeline))
        if views_result:
            total_views = views_result[0]['total_views']
        
        if total_views > 0:
            conversion_rate = round((orders_count / total_views) * 100, 2)

        recent_orders = list(db.orders.find().sort("created_at", -1).limit(5))
        recent_activities = list(db.activity_logs.find().sort("timestamp", -1).limit(10))

    except Exception as e:
        print(f"Warning: {e}")

    return render_template('dashboard/index.html', 
                           products_count=products_count,
                           orders_count=orders_count,
                           total_views=total_views,
                           conversion_rate=conversion_rate,
                           recent_orders=recent_orders,
                           my_products=my_products,
                           recent_activities=recent_activities)

@dashboard_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            price = float(request.form.get('price'))
            old_price = request.form.get('old_price')
            description = request.form.get('description')
            
            images_json = request.form.get('images_list')
            images = json.loads(images_json) if images_json else []
            
            colors = [c.strip() for c in request.form.get('colors', '').split(',') if c.strip()]
            sizes = [s.strip() for s in request.form.get('sizes', '').split(',') if s.strip()]
            
            offer_end_time = request.form.get('offer_end_time')
            coupon_value = request.form.get('coupon_value')
            coupon_code = request.form.get('coupon_code')
            ai_instructions = request.form.get('ai_instructions')
            
            new_product = {
                "merchant_id": session['user_id'], # ربط المنتج بصاحب الحساب
                "name": name,
                "price": price,
                "old_price": float(old_price) if old_price else None,
                "currency_symbol": "دج",
                "description": description,
                "product_type": "physical",
                "images": images,
                "colors": colors,
                "sizes": sizes,
                "offer_end_time": offer_end_time,
                "coupon": {"code": coupon_code, "value": coupon_value} if coupon_code else None,
                "ai_instructions": ai_instructions,
                "created_at": datetime.datetime.utcnow(),
                "views": 0,
                "sales_count": 0
            }
            
            db.products.insert_one(new_product)
            return redirect(url_for('dashboard.index'))
        except Exception as e:
            return f"Error: {e}"

    return render_template('dashboard/add_product.html')
