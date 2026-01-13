import os
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from scout import AssetData
from analyst import AlphaSignal

# محاولة الاتصال بـ MongoDB (إذا وجد الرابط في البيئة)
MONGO_URI = os.getenv("MONGO_URI")
DB_CLIENT = AsyncIOMotorClient(MONGO_URI) if MONGO_URI else None

class AlphaVault:
    def __init__(self):
        self.collection = None
        if DB_CLIENT:
            db = DB_CLIENT["institutional_intel_db"]
            self.collection = db["alpha_reports"]
        else:
            print("⚠️ [VAULT] Running in InMemory Mode (No MongoDB detected). Data will be lost on restart.")
            self.in_memory_db = {} # مخزن مؤقت للتجربة

    async def save_intel(self, asset: AssetData, signal: AlphaSignal):
        """حفظ أو تحديث تقرير العملة"""
        record = {
            "symbol": asset.symbol,
            "name": asset.name,
            "price": asset.price_usd,
            "signal": signal.signal,
            "severity": signal.severity,
            "headline": signal.headline,
            "full_report": signal.full_report,
            "updated_at": datetime.datetime.utcnow()
        }

        if self.collection:
            # Upsert: تحديث القديم أو إنشاء جديد
            await self.collection.update_one(
                {"symbol": asset.symbol},
                {"$set": record},
                upsert=True
            )
        else:
            self.in_memory_db[asset.symbol] = record

    async def get_latest_feed(self):
        """جلب كل التقارير لواجهة المستخدم"""
        if self.collection:
            cursor = self.collection.find({}).sort("updated_at", -1)
            return await cursor.to_list(length=100)
        else:
            return list(self.in_memory_db.values())
