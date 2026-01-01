from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

mongo_client = None
db = None

def init_db(app):
    global mongo_client, db
    uri = app.config['MONGO_URI']
    db_name = app.config['DB_NAME']

    if not uri:
        print("⚠️ تحذير: لم يتم العثور على رابط MONGO_URI.")
        return

    try:
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')
        db = mongo_client[db_name]
        print(f"✅ تم الاتصال بقاعدة البيانات: {db_name}")
    except Exception as e:
        print(f"❌ خطأ في قاعدة البيانات: {e}")

def get_db():
    return db

def get_collection(collection_name):
    if db is not None:
        return db[collection_name]
    return None
