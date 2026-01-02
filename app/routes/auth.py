from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from app.services.email_service import send_verification_code
import random
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        
        user = db.users.find_one({"email": email})
        
        if user and check_password_hash(user['password'], password):
            if user.get('status') == 'pending':
                flash('يرجى تفعيل حسابك أولاً', 'warning')
                session['pending_email'] = email
                return redirect(url_for('auth.verify'))
                
            session['user_id'] = str(user['_id'])
            session['store_name'] = user.get('store_name')
            return redirect(url_for('dashboard.index'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        store_name = request.form.get('store_name')
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        
        # 1. التحقق من وجود المستخدم
        if db.users.find_one({"email": email}):
            flash('هذا البريد مسجل مسبقاً', 'error')
            return redirect(url_for('auth.login'))
            
        # 2. إنشاء كود التفعيل
        otp_code = str(random.randint(100000, 999999))
        
        # 3. حفظ المستخدم (غير مفعل)
        new_user = {
            "store_name": store_name,
            "email": email,
            "password": generate_password_hash(password),
            "status": "pending", # أهم حقل
            "otp_code": otp_code,
            "created_at": datetime.datetime.utcnow()
        }
        db.users.insert_one(new_user)
        
        # 4. إرسال الكود وتوجيه للتحقق
        send_verification_code(email, otp_code)
        session['pending_email'] = email # نحفظ الايميل مؤقتاً للتحقق
        
        flash('تم إرسال رمز التفعيل إلى بريدك', 'success')
        return redirect(url_for('auth.verify'))

    return render_template('auth/signup.html')

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_email' not in session:
        return redirect(url_for('auth.signup'))
        
    if request.method == 'POST':
        code = request.form.get('code')
        email = session['pending_email']
        
        user = db.users.find_one({"email": email})
        
        if user and user.get('otp_code') == code:
            # تفعيل الحساب
            db.users.update_one({"email": email}, {"$set": {"status": "active", "otp_code": None}})
            
            # تسجيل الدخول فوراً
            session['user_id'] = str(user['_id'])
            session.pop('pending_email', None)
            
            flash('تم تفعيل حسابك بنجاح!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('الرمز غير صحيح، حاول مرة أخرى', 'error')
            
    return render_template('auth/verify.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
