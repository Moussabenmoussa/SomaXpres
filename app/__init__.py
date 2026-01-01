from flask import Flask
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# تهيئة قاعدة البيانات (Global)
mongo = MongoClient(os.getenv("MONGO_URI"))
db = mongo.get_database("somaxpres_db")

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY")

    # تسجيل المسارات (Blueprints)
    from app.routes.dashboard import dashboard_bp
    from app.routes.public import public_bp
    
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(public_bp, url_prefix='/') # الروت الرئيسي

    return app
