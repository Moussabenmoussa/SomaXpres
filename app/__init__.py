from flask import Flask
from flask_cors import CORS
from config import Config
from .services.db import init_db

def create_app():
    # 1. إنشاء تطبيق فلاسك
    app = Flask(__name__)
    
    # 2. تحميل الإعدادات
    app.config.from_object(Config)
    
    # 3. تفعيل CORS
    CORS(app)
    
    # 4. تهيئة قاعدة البيانات
    init_db(app)

    # 5. تسجيل الموجهات (تم التفعيل)
    from .routes import public, dashboard
    app.register_blueprint(public.bp)
    app.register_blueprint(dashboard.bp)

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
