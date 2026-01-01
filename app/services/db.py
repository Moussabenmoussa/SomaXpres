from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# متغيرات عامة لحفظ الاتصال
mongo_client = None
db = None

def init_db(app):
    """
    تهيئة الاتصال بقاعدة البيانات عند تشغيل السيرفر
    """
    global mongo_client, db
    
    uri = app.config['MONGO_URI']
    db_name = app.config['DB_NAME']

    if not uri:
        print("⚠️ تحذير: لم يتم العثور على رابط MONGO_URI في المتغيرات.")
        return

    try:
        # إنشاء اتصال مع مهلة زمنية قصيرة للتأكد من السرعة
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # فحص الاتصال الحقيقي
        mongo_client.admin.command('ping')
        
        db = mongo_client[db_name]
        print(f"✅ تم الاتصال بقاعدة البيانات بنجاح: {db_name}")
        
    except ConnectionFailure:
        print("❌ فشل الاتصال بقاعدة البيانات MongoDB (تأكد من الرابط أو IP Whitelist)")
    except Exception as e:
        print(f"❌ خطأ غير متوقع في قاعدة البيانات: {e}")

def get_db():
    """
    دالة لاستدعاء قاعدة البيانات من أي ملف آخر
    """
    return db

def get_collection(collection_name):
    """
    دالة مساعدة لجلب جدول معين بسرعة
    """
    if db is not None:
        return db[collection_name]
    return None
