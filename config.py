import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # مفتاح التشفير للجلسات (Cookies)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_somaxpres_2025')
    
    # إعدادات قاعدة البيانات
    MONGO_URI = os.environ.get('MONGO_URI')
    DB_NAME = os.environ.get('DB_NAME', 'somaxpres_db')

    # إعدادات الذكاء الاصطناعي الافتراضية (للتجربة المجانية)
    # سيتم استبدالها لاحقاً بمفاتيح التاجر من قاعدة البيانات
    PLATFORM_GROQ_KEY = os.environ.get('PLATFORM_GROQ_KEY')
    PLATFORM_GEMINI_KEY = os.environ.get('PLATFORM_GEMINI_KEY')

    # إعدادات السيرفر
    DEBUG = False
    TESTING = False
