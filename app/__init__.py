from flask import Flask
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

mongo = MongoClient(os.getenv("MONGO_URI"))
db = mongo.get_database("somaxpres_db")

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev_key_123")

    # تسجيل المسارات
    from app.routes.dashboard import dashboard_bp
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(public_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    return app
