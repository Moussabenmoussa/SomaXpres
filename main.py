import os
import datetime
import uvicorn
import requests
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from pymongo import MongoClient
from typing import Optional, List

# --- CONFIGURATION (Loaded from Render Env) ---
# يتم سحب هذه القيم من إعدادات Render التي أرسلتها في الصورة
ADMIN_PASSWORD = os.environ.get("SECRET_KEY", "admin123") 
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("CHAT_ID")
MONGO_URI = os.environ.get("MONGO_URI")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Render URL - يفضل إضافته في Environment Variables باسم RENDER_EXTERNAL_URL
# مثال: https://your-app-name.onrender.com
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL") 

# --- MONGODB SETUP ---
try:
    # الاتصال بقاعدة البيانات السحابية
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["iptv_store"] # اسم قاعدة البيانات
    
    # تعريف الجداول (Collections)
    codes_col = db["codes"]
    trials_col = db["trials"]
    orders_col = db["orders"]
    config_col = db["config"]
    
    # إضافة الدستور الافتراضي إذا لم يكن موجوداً
    if not config_col.find_one({"key": "system_prompt"}):
        default_prompt = """You are 'Sami', a senior support specialist for StreamKey.
Tone: Professional, warm, and concise. 
Language Rule: ALWAYS respond in the SAME LANGUAGE the user uses.
Goal: Assist with subscriptions and activation.
--- PRICING ---
Trial: Free (24h)
1 Month: $7
3 Months: $17
6 Months: $21
1 Year: $35 (Best Value)
--- RULES ---
1. Payment via PayPal: 'ninomino7001@gmail.com'.
2. Activation: Send Transaction ID via the website form."""
        config_col.insert_one({"key": "system_prompt", "value": default_prompt})
        
    print("✅ Connected to MongoDB Atlas successfully.")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# --- TELEGRAM UTILS ---
def send_telegram_msg(text, reply_markup=None):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        print("Telegram tokens missing.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        # Render has stable internet, standard requests work fine
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def set_webhook_background():
    """Sets webhook automatically after server boot"""
    if not RENDER_EXTERNAL_URL:
        print("⚠️ Warning: RENDER_EXTERNAL_URL not set in env vars. Webhook might not work.")
        return
        
    time.sleep(5) # Wait for server to be fully ready
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        res = requests.get(url, timeout=10)
        print(f"Webhook Setup: {res.text}")
    except Exception as e:
        print(f"Webhook Setup Failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start webhook setup in background
    threading.Thread(target=set_webhook_background, daemon=True).start()
    yield

# --- APP INIT ---
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class ChatRequest(BaseModel):
    message: str

class SmartRequest(BaseModel):
    type: str 
    text: str

class CodeAddRequest(BaseModel):
    password: str
    type: str
    codes: List[str]

class OrderRequest(BaseModel):
    email: str
    transaction_id: str
    plan: str

class PromptUpdateRequest(BaseModel):
    password: str
    new_prompt: str

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Running", "service": "StreamKey on Render"}

@app.get("/status")
def status():
    try:
        # Check DB connection
        db.command("ping")
        return {"status": "Online", "database": "Connected"}
    except:
        return {"status": "Online", "database": "Disconnected"}

# 1. AI Chat
@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client: return {"response": "AI Config Error (Check API Key)"}
    
    try:
        cfg = config_col.find_one({"key": "system_prompt"})
        prompt = cfg["value"] if cfg else "You are a helpful assistant."

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": req.message}],
            temperature=0.7, max_tokens=250
        )
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        print(f"Groq Error: {e}")
        return {"response": "System is currently busy."}

# 2. Smart Assistant
@app.post("/smart-ask")
def smart_ask_endpoint(req: SmartRequest):
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client: return {"response": "Unavailable"}

    if req.type == 'content':
        sys = "You are a movie guide. Suggest 3 items based on input. Same language as user."
        usr = f"Suggest content for: {req.text}"
    else:
        sys = "You are a sales rep. Recommend 1 plan (Trial/1M/1Y) based on input. Same language as user."
        usr = f"Recommend plan for: {req.text}"

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            temperature=0.7, max_tokens=300
        )
        return {"response": completion.choices[0].message.content}
    except:
        return {"response": "Error processing request."}

# 3. Get Trial
@app.post("/get-trial")
def get_trial(request: Request):
    client_ip = request.headers.get("x-forwarded-for") or request.client.host
    
    # Check IP Limit in Mongo
    existing_trial = trials_col.find_one({"ip": client_ip})
    if existing_trial:
        last = datetime.datetime.fromisoformat(existing_trial["timestamp"])
        if datetime.datetime.now() - last < datetime.timedelta(hours=24):
            raise HTTPException(400, "Trial limit reached (1 per 24h).")

    # Get Code from Mongo
    code_doc = codes_col.find_one({"type": "trial", "is_sold": False})
    if not code_doc:
        raise HTTPException(404, "No trial codes available.")
    
    # Update DB (Atomic operation safe)
    codes_col.update_one({"_id": code_doc["_id"]}, {"$set": {"is_sold": True}})
    trials_col.update_one(
        {"ip": client_ip}, 
        {"$set": {"timestamp": datetime.datetime.now().isoformat()}}, 
        upsert=True
    )
    
    return {"code": code_doc["code"], "message": "Success"}

# 4. Submit Order
@app.post("/submit-order")
def submit_order(order: OrderRequest):
    order_id = f"ORD-{datetime.datetime.now().strftime('%H%M%S')}"
    
    new_order = {
        "order_id": order_id,
        "email": order.email,
        "trans_id": order.transaction_id,
        "plan": order.plan,
        "status": "pending",
        "assigned_code": None,
        "created_at": datetime.datetime.now()
    }
    orders_col.insert_one(new_order)

    msg_text = f"🚨 *NEW ORDER*\n📦 Plan: {order.plan}\n💰 TxID: `{order.transaction_id}`\n📧 Email: {order.email}\n🆔 ID: `{order_id}`"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{order_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{order_id}"}
        ]]
    }
    
    # Send notification asynchronously
    threading.Thread(target=send_telegram_msg, args=(msg_text, keyboard)).start()
    
    return {"status": "pending", "order_id": order_id, "message": "Verifying..."}

# 5. Check Order
@app.get("/check-order")
def check_order(order_id: str):
    order = orders_col.find_one({"order_id": order_id})
    if not order: return {"status": "not_found"}
    return {"status": order["status"], "code": order.get("assigned_code")}

# 6. Telegram Webhook (The Control Center)
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
    except:
        return {"status": "invalid_json"}
    
    if "callback_query" in data:
        cb = data["callback_query"]
        cb_id = cb["id"]
        action_data = cb["data"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        
        # Stop loading spinner on Telegram
        threading.Thread(target=requests.post, args=(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",), kwargs={"json": {"callback_query_id": cb_id}}).start()

        try:
            action, order_id = action_data.split(":")
        except:
            return {"status": "bad_data"}
        
        order = orders_col.find_one({"order_id": order_id})
        
        if not order:
            send_telegram_msg(f"Order {order_id} not found in DB.")
            return {}

        # Map plan names to DB types
        plan_map = {"1 Month": "1m", "3 Months": "3m", "6 Months": "6m", "12 Months": "12m", "Yearly": "12m"}
        db_type = plan_map.get(order.get("plan"), "1m")

        new_text = ""
        if action == "approve":
            code_doc = codes_col.find_one({"type": db_type, "is_sold": False})
            
            if code_doc:
                code_val = code_doc["code"]
                # Update Inventory
                codes_col.update_one({"_id": code_doc["_id"]}, {"$set": {"is_sold": True}})
                # Update Order
                orders_col.update_one({"order_id": order_id}, {"$set": {"status": "approved", "assigned_code": code_val}})
                
                new_text = f"✅ *APPROVED*\nID: {order_id}\nCode: `{code_val}`"
            else:
                new_text = f"⚠️ *NO STOCK* for {db_type}. Order ID: {order_id}\nPlease add codes and try again."
                
        elif action == "reject":
            orders_col.update_one({"order_id": order_id}, {"$set": {"status": "rejected"}})
            new_text = f"❌ *REJECTED*\nID: {order_id}"

        # Update the Telegram message to remove buttons
        edit_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        payload = {"chat_id": chat_id, "message_id": msg_id, "text": new_text, "parse_mode": "Markdown"}
        requests.post(edit_url, json=payload)

    return {"status": "ok"}

# --- ADMIN ENDPOINTS (MongoDB Version) ---

@app.post("/admin/add-codes")
def add_codes(req: CodeAddRequest):
    if req.password.strip() != ADMIN_PASSWORD: raise HTTPException(403, "Invalid Password")
    
    docs = [{"type": req.type, "code": c.strip(), "is_sold": False} for c in req.codes if c.strip()]
    if docs:
        codes_col.insert_many(docs)
        
    return {"message": f"Added {len(docs)} codes to {req.type}."}

@app.get("/admin/stats")
def get_stats(password: str):
    if password.strip() != ADMIN_PASSWORD: raise HTTPException(403, "Unauthorized")
    
    pipeline = [
        {"$match": {"is_sold": False}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}}
    ]
    results = list(codes_col.aggregate(pipeline))
    # Convert list to dict for easier frontend consumption
    stats = {r["_id"]: r["count"] for r in results}
    return stats

@app.get("/admin/get-prompt")
def get_prompt(password: str):
    if password.strip() != ADMIN_PASSWORD: raise HTTPException(403, "Unauthorized")
    row = config_col.find_one({"key": "system_prompt"})
    return {"prompt": row["value"] if row else ""}

@app.post("/admin/update-prompt")
def update_prompt(req: PromptUpdateRequest):
    if req.password.strip() != ADMIN_PASSWORD: raise HTTPException(403, "Unauthorized")
    config_col.update_one(
        {"key": "system_prompt"}, 
        {"$set": {"value": req.new_prompt}}, 
        upsert=True
    )
    return {"message": "Prompt updated successfully"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
