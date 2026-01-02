import os
import requests
import json
from threading import Thread
from flask import render_template_string

# إعدادات Brevo
BREVO_URL = "https://api.brevo.com/v3/smtp/email"

def _send_async_email(payload):
    """دالة داخلية ترسل الطلب لـ Brevo في الخلفية"""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        print("❌ Error: BREVO_API_KEY is missing!")
        return

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(BREVO_URL, data=json.dumps(payload), headers=headers)
        if response.status_code == 201:
            print(f"✅ Email sent successfully to {payload['to'][0]['email']}")
        else:
            print(f"⚠️ Email Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def send_order_notification(order_data):
    """
    الدالة الرئيسية التي تستدعيها عند وصول طلب جديد.
    تقوم بتجهيز القالب وإطلاق عملية الإرسال في الخلفية.
    """
    sender_email = os.getenv("SENDER_EMAIL", "noreply@somaxpres.dz")
    
    # 1. إيميل للتاجر (إشعار بطلب جديد)
    merchant_payload = {
        "sender": {"name": "SomaXpres Bot", "email": sender_email},
        "to": [{"email": sender_email}], # يرسل لنفسك (التاجر) مؤقتاً
        "subject": f"🔔 طلب جديد: {order_data.get('product_name')} ({order_data.get('total_price')} دج)",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; direction: rtl; text-align: right;">
            <h2>مرحباً، لديك زبون جديد! 🤑</h2>
            <p>تم تسجيل طلب جديد عبر المنصة.</p>
            <hr>
            <ul>
                <li><strong>المنتج:</strong> {order_data.get('product_name')}</li>
                <li><strong>الزبون:</strong> {order_data.get('customer_name')}</li>
                <li><strong>الهاتف:</strong> <a href="tel:{order_data.get('customer_phone')}">{order_data.get('customer_phone')}</a></li>
                <li><strong>الولاية:</strong> {order_data.get('customer_wilaya')} - {order_data.get('customer_commune')}</li>
                <li><strong>السعر:</strong> {order_data.get('total_price')} دج</li>
            </ul>
            <a href="https://somaxpres.onrender.com/dashboard" style="background: #000; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px;">عرض الطلب في اللوحة</a>
        </div>
        """
    }

    # إطلاق الإرسال في خيط منفصل (Thread) لعدم تعطيل الزبون
    Thread(target=_send_async_email, args=(merchant_payload,)).start()


# ... (نفس الـ imports السابقة)

def send_verification_code(email, code):
    """إرسال كود التفعيل (OTP) للمستخدم الجديد"""
    sender_email = os.getenv("SENDER_EMAIL", "noreply@somaxpres.dz")
    
    payload = {
        "sender": {"name": "SomaXpres Security", "email": sender_email},
        "to": [{"email": email}],
        "subject": f"رمز التفعيل الخاص بك: {code}",
        "htmlContent": f"""
        <div style="font-family: Arial, text-align: center; padding: 20px;">
            <h2>مرحباً بك في SomaXpres 🚀</h2>
            <p>لتفعيل حسابك والبدء في البيع، استخدم الرمز التالي:</p>
            <h1 style="background: #eee; padding: 10px; letter-spacing: 5px; display: inline-block;">{code}</h1>
            <p>لا تشارك هذا الرمز مع أحد.</p>
        </div>
        """
    }
    
    # إرسال في الخلفية
    Thread(target=_send_async_email, args=(payload,)).start()
