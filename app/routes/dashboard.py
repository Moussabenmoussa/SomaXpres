from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
import datetime

dashboard_bp = Blueprint('dashboard', __name__)

# ملاحظة: في النسخة النهائية سنضيف @login_required هنا
# للتأكد من أن المستخدم مسجل دخول

@dashboard_bp.route('/')
def index():
    """الصفحة الرئيسية للوحة التحكم (الإحصائيات)"""
    # هنا نجلب الإحصائيات الحقيقية من الـ DB
    return render_template('dashboard/index.html')

@dashboard_bp.route('/products/new', methods=['GET', 'POST'])
def add_product():
    """صفحة إضافة منتج جديد + إعدادات الذكاء"""
    
    if request.method == 'POST':
        # 1. جمع البيانات الأساسية
        name = request.form.get('name')
        price = float(request.form.get('price'))
        currency = request.form.get('currency', '$') # العملة الافتراضية
        description = request.form.get('description')
        product_type = request.form.get('product_type') # physical or digital
        
        # 2. جمع صور المنتج (روابط مؤقتاً)
        # في النسخة المتقدمة سنستخدم رفع الملفات (File Upload)
        image_url = request.form.get('image_url')
        
        # 3. إعدادات "عقل الروبوت"
        bot_name = request.form.get('bot_name')
        ai_instructions = request.form.get('ai_instructions')
        
        # 4. بناء كائن المنتج (Document)
        new_product = {
            "merchant_id": session.get('user_id', 'admin_1'), # ربط بالتاجر
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
        
        # 5. الحفظ في MongoDB
        db.products.insert_one(new_product)
        
        flash('تم نشر المنتج وتدريب الروبوت بنجاح!', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('dashboard/add_product.html')
