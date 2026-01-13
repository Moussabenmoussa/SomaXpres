import os
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from scout import AssetData
from analyst import AlphaSignal

# التحقق من وجود الرابط قبل الاتصال
MONGO_URI = os.getenv("MONGO_URI")
# تأكد أن الرابط ليس فارغاً وليس كلمة Localhost
DB_CLIENT = AsyncIOMotorClient(MONGO_URI) if (MONGO_URI and "mongodb" in MONGO_URI) else None

class AlphaVault:
    def __init__(self):
        self.collection = None
        self.in_memory_db = {} # الذاكرة المؤقتة (للهاتف والتجربة)

        if DB_CLIENT:
            try:
                db = DB_CLIENT["institutional_intel_db"]
                self.collection = db["alpha_reports"]
            except:
                self.collection = None
        
        if self.collection is None:
            print("⚠️ [VAULT] Running in Memory Mode (Phone/Demo).")

    async def save_intel(self, asset: AssetData, signal: AlphaSignal):
        """حفظ التقرير"""
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

        # التصحيح هنا: نستخدم is not None
        if self.collection is not None:
            try:
                await self.collection.update_one(
                    {"symbol": asset.symbol},
                    {"$set": record},
                    upsert=True
                )
            except:
                self.in_memory_db[asset.symbol] = record
        else:
            self.in_memory_db[asset.symbol] = record

    async def get_latest_feed(self):
        """جلب البيانات"""
        # التصحيح هنا أيضاً
        if self.collection is not None:
            try:
                cursor = self.collection.find({}).sort("updated_at", -1)
                return await cursor.to_list(length=100)
            except:
                return list(self.in_memory_db.values())
        else:
            return list(self.in_memory_db.values())
