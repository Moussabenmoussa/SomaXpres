import os
import requests
import json
from threading import Thread

# إعدادات Brevo API
BREVO_URL = "https://api.brevo.com/v3/smtp/email"

def _send_async_email(payload):
    """إرسال الطلب لـ Brevo في الخلفية لعدم تعطيل الموقع"""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        print("❌ Error: BREVO_API_KEY is missing in Environment Variables!")
        return

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(BREVO_URL, data=json.dumps(payload), headers=headers)
        if response.status_code == 201:
            print(f"✅ Email sent successfully.")
        else:
            print(f"⚠️ Email Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def send_verification_code(email, code):
    """إرسال كود التفعيل (OTP) للمسجل الجديد"""
    sender_email = os.getenv("SENDER_EMAIL", "no-reply@somaxpres.dz")
    
    payload = {
        "sender": {"name": "SomaXpres Security", "email": sender_email},
        "to": [{"email": email}],
        "subject": f"رمز التفعيل: {code}",
        "htmlContent": f"""
        <div style="font-family: Arial; text-align: center; padding: 20px; background-color: #f9f9f9;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">مرحباً بك في SomaXpres 🚀</h2>
                <p style="color: #666;">لقد قمت بإنشاء حساب تاجر جديد. لتفعيل حسابك، استخدم الرمز التالي:</p>
                <h1 style="background: #eee; padding: 15px; letter-spacing: 10px; border-radius: 5px; margin: 20px 0;">{code}</h1>
                <p style="color: #999; font-size: 12px;">لا تشارك هذا الرمز مع أحد.</p>
            </div>
        </div>
        """
    }
    Thread(target=_send_async_email, args=(payload,)).start()

def send_order_notification(order_data):
    """إشعار بطلب جديد للتاجر"""
    sender_email = os.getenv("SENDER_EMAIL", "no-reply@somaxpres.dz")
    
    payload = {
        "sender": {"name": "SomaXpres Bot", "email": sender_email},
        "to": [{"email": sender_email}], # يرسل لنفسك مؤقتاً
        "subject": f"🔔 طلب جديد: {order_data.get('product_name')}",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; direction: rtl; text-align: right;">
            <h2>مرحباً، لديك زبون جديد! 🤑</h2>
            <hr>
            <ul>
                <li><strong>المنتج:</strong> {order_data.get('product_name')}</li>
                <li><strong>الزبون:</strong> {order_data.get('customer_name')}</li>
                <li><strong>الهاتف:</strong> <a href="tel:{order_data.get('customer_phone')}">{order_data.get('customer_phone')}</a></li>
                <li><strong>الولاية:</strong> {order_data.get('customer_wilaya')}</li>
                <li><strong>السعر:</strong> {order_data.get('total_price')} دج</li>
            </ul>
        </div>
        """
    }
    Thread(target=_send_async_email, args=(payload,)).start()
