from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from engine import AsyncEliteAgent
import os
import datetime

# إعدادات التطبيق
app = FastAPI(title="Elite Crypto Hunter SaaS")

# الاتصال بقاعدة البيانات (MongoDB)
MONGO_URI = os.getenv("MONGO_URI") # سنضع الرابط في Render لاحقاً
client = AsyncIOMotorClient(MONGO_URI)
db = client["crypto_hunter_db"]
reports_collection = db["reports"]

class AnalysisRequest(BaseModel):
    target: str # اسم العملة أو المشروع

@app.get("/")
def home():
    return {"status": "Online", "message": "The Beast is awake."}

@app.post("/analyze")
async def analyze_crypto(request: AnalysisRequest):
    target = request.target.lower().strip()
    
    # 1. فحص قاعدة البيانات أولاً (توفير المال والوقت)
    # نبحث عن تقرير لنفس العملة تم إنشاؤه في آخر 24 ساعة
    existing_report = await reports_collection.find_one({
        "target": target,
        "created_at": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(hours=24)}
    })
    
    if existing_report:
        return {
            "source": "cache (MongoDB)", 
            "report": existing_report["report"],
            "timestamp": existing_report["created_at"]
        }

    # 2. إذا لم يوجد، نطلق الوحش
    try:
        agent = AsyncEliteAgent()
        report = await agent.execute_mission(request.target)
        
        # 3. حفظ التقرير في قاعدة البيانات
        new_record = {
            "target": target,
            "report": report,
            "created_at": datetime.datetime.utcnow()
        }
        await reports_collection.insert_one(new_record)
        
        return {"source": "live_agent", "report": report}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
