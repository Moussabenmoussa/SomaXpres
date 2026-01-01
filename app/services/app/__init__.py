from flask import Flask
from flask_cors import CORS
from config import Config
from .services.db import init_db

def create_app():
    # 1. إنشاء تطبيق فلاسك
    app = Flask(__name__)
    
    # 2. تحميل الإعدادات من ملف config.py
    app.config.from_object(Config)
    
    # 3. تفعيل CORS (للسماح للمتصفح بالاتصال من أي مكان)
    CORS(app)
    
    # 4. تهيئة قاعدة البيانات
    init_db(app)

    # 5. تسجيل الموجهات (Blueprints)
    # ملاحظة: سنقوم بإلغاء التعليق هنا عندما ننشئ ملفات routes في الدفعة القادمة
    # from .routes import public, dashboard, api
    # app.register_blueprint(public.bp)
    # app.register_blueprint(dashboard.bp)
    # app.register_blueprint(api.bp)

    # فحص صحة السيرفر
    @app.route('/health')
    def health_check():
        from .services.db import get_db
        db_status = "Connected" if get_db() is not None else "Disconnected"
        return {
            "status": "online", 
            "app": "SomaXpres AI", 
            "database": db_status
        }

    return app
