import os
import datetime
import uvicorn
import requests
import threading
import time
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from pymongo import MongoClient
from typing import Optional, List

# --- CONFIGURATION ---
# Render Environment Variables
ADMIN_PASSWORD = os.environ.get("SECRET_KEY", "admin123") 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MONGO_URI = os.environ.get("MONGO_URI")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL") 
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL") 

GROQ_MODEL = "llama-3.3-70b-versatile"

# --- MONGODB CONNECTION ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["iptv_store"]
    
    # Collections
    codes_col = db["codes"]
    trials_col = db["trials"]
    orders_col = db["orders"]
    users_col = db["users"] 
    config_col = db["config"]
    
    # Ensure System Prompt Exists
    if not config_col.find_one({"key": "system_prompt"}):
        default_prompt = """You are 'Sami', the official support agent for DARPRO4K IPTV.
Tone: Professional, helpful, and concise.
Language Rule: Match the user's language (Arabic/English/French).
Goal: Help with subscription plans and technical queries.
--- PRICING ---
Trial: Free (24h)
1 Month: $7
3 Months: $17
6 Months: $21
1 Year: $35 (Best Value)
--- RULES ---
1. Payment: PayPal to 'ninomino7001@gmail.com'.
2. Activation: User must submit email & Transaction ID.
3. Issues: If code not received or complex issue, direct to Management WhatsApp: https://wa.link/ysruwg"""
        config_col.insert_one({"key": "system_prompt", "value": default_prompt})
        
    print("✅ Database Connected.")
except Exception as e:
    print(f"❌ DB Error: {e}")

# --- PROFESSIONAL EMAIL TEMPLATES ---
def get_email_template(type, data):
    
    header = """
    <div style="background-color:#0f172a; padding:20px; text-align:center;">
        <h1 style="color:#3b82f6; font-family:Arial, sans-serif; margin:0;">DARPRO4K <span style="color:#ffffff;">IPTV</span></h1>
    </div>
    """
    
    footer = """
    <div style="background-color:#f1f5f9; padding:20px; text-align:center; font-size:12px; color:#64748b; font-family:Arial;">
        <p>Need help? Contact us on WhatsApp <a href="https://wa.link/ysruwg">Here</a></p>
        <p>&copy; 2025 DARPRO4K. All rights reserved.</p>
    </div>
    """

    body = ""
    
    if type == 'trial':
        body = f"""
        <div style="padding:30px; background-color:#ffffff; font-family:Arial, sans-serif; color:#334155;">
            <h2 style="color:#0f172a;">Your 24H Free Trial is Ready! 🚀</h2>
            <p>Thank you for trying DARPRO4K. Below is your activation code.</p>
            
            <div style="background-color:#eff6ff; border:1px solid #bfdbfe; padding:20px; text-align:center; margin:20px 0; border-radius:8px;">
                <span style="font-size:14px; color:#64748b; display:block; margin-bottom:5px;">ACTIVATION CODE</span>
                <span style="font-size:24px; font-weight:bold; color:#2563eb; font-family:monospace; letter-spacing:2px;">{data['code']}</span>
            </div>

            <h3>How to Start Watching:</h3>
            <ol style="line-height:1.6;">
                <li>Download our App: <a href="https://play.google.com/store/apps/details?id=com.mbm_soft.darplayer" style="color:#2563eb; font-weight:bold;">Click Here</a></li>
                <li>Open the App.</li>
                <li>Enter the code above.</li>
            </ol>
        </div>
        """
        
    elif type == 'order':
        body = f"""
        <div style="padding:30px; background-color:#ffffff; font-family:Arial, sans-serif; color:#334155;">
            <h2 style="color:#16a34a;">Payment Confirmed! ✅</h2>
            <p>Welcome to the family! Your subscription for <strong>{data['plan']}</strong> is now active.</p>
            
            <div style="background-color:#f0fdf4; border:1px solid #bbf7d0; padding:20px; text-align:center; margin:20px 0; border-radius:8px;">
                <span style="font-size:14px; color:#64748b; display:block; margin-bottom:5px;">YOUR PREMIUM CODE</span>
                <span style="font-size:28px; font-weight:bold; color:#16a34a; font-family:monospace; letter-spacing:2px;">{data['code']}</span>
            </div>

            <h3>Installation Guide:</h3>
            <ol style="line-height:1.6;">
                <li>Download <strong>DAR Player</strong> from Google Play: <a href="https://play.google.com/store/apps/details?id=com.mbm_soft.darplayer">Download Link</a></li>
                <li>Launch the app.</li>
                <li>Paste your Premium Code.</li>
                <li>Enjoy 4K Streaming!</li>
            </ol>
        </div>
        """
        
    elif type == 'marketing':
        body = f"""
        <div style="padding:30px; background-color:#ffffff; font-family:Arial, sans-serif; color:#334155;">
            {data['content']}
            <br><br>
            <a href="{API_PUBLIC_URL if API_PUBLIC_URL else '#'}" style="display:inline-block; background-color:#2563eb; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;">Visit Website</a>
        </div>
        """

    return f"{header}{body}{footer}"

# --- BREVO EMAIL SENDER ---
def send_email_brevo(to_email, subject, html_content):
    if not BREVO_API_KEY:
        print("Brevo API Key missing")
        return False
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": "DARPRO4K Team", "email": SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print(f"Email sent to {to_email}")
            return True
        else:
            print(f"Brevo Error: {response.text}")
            return False
    except Exception as e:
        print(f"Email Exception: {e}")
        return False

# --- TELEGRAM UTILS ---
def send_telegram_msg(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def set_webhook_bg():
    time.sleep(5)
    if RENDER_EXTERNAL_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={RENDER_EXTERNAL_URL}/webhook"
        requests.get(url)

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=set_webhook_bg, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class ChatRequest(BaseModel):
    message: str

class SmartRequest(BaseModel):
    type: str; text: str

class CodeAddRequest(BaseModel):
    password: str; type: str; codes: List[str]

class OrderRequest(BaseModel):
    email: str; transaction_id: str; plan: str

class TrialRequest(BaseModel):
    email: str

class MarketingRequest(BaseModel):
    password: str
    subject: str
    content: str
    limit: int

class PromptUpdateRequest(BaseModel):
    password: str
    new_prompt: str

# --- ENDPOINTS ---

@app.get("/")
def home(): return {"status": "Active", "service": "DARPRO4K System"}

@app.get("/status")
def status(): return {"status": "Online"}

# 1. AI Chat
@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client: return {"response": "AI Unavailable"}
    try:
        config = config_col.find_one({"key": "system_prompt"})
        prompt = config["value"] if config else "Helpful assistant."
        completion = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role":"system","content":prompt},{"role":"user","content":req.message}])
        return {"response": completion.choices[0].message.content}
    except: return {"response": "System busy."}

# 2. Smart Assistant
@app.post("/smart-ask")
def smart_ask(req: SmartRequest):
    client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
    if not client: return {"response": "Error"}
    sys_prompt = "You are a sales & movie expert. Reply in user's language."
    try:
        comp = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role":"system","content":sys_prompt},{"role":"user","content":req.text}])
        return {"response": comp.choices[0].message.content}
    except: return {"response": "Error"}

# 3. Get Trial
@app.post("/get-trial")
def get_trial(req: TrialRequest):
    client_ip = "0.0.0.0" 
    
    existing = trials_col.find_one({"email": req.email})
    if existing:
        pass

    code_doc = codes_col.find_one({"type": "trial", "is_sold": False})
    if not code_doc:
        raise HTTPException(404, "No trial codes available.")

    codes_col.update_one({"_id": code_doc["_id"]}, {"$set": {"is_sold": True}})
    
    users_col.update_one(
        {"email": req.email}, 
        {"$set": {"source": "trial", "joined_at": datetime.datetime.now()}}, 
        upsert=True
    )
    
    trials_col.insert_one({"email": req.email, "ip": client_ip, "timestamp": datetime.datetime.now().isoformat()})

    email_html = get_email_template("trial", {"code": code_doc["code"]})
    threading.Thread(target=send_email_brevo, args=(req.email, "Your Free Trial Code - DARPRO4K", email_html)).start()

    return {"message": "Code sent to email"}

# 4. Submit Order
@app.post("/submit-order")
def submit_order(order: OrderRequest):
    order_id = f"ORD-{datetime.datetime.now().strftime('%H%M%S')}"
    
    orders_col.insert_one({
        "order_id": order_id, "email": order.email, "trans_id": order.transaction_id, 
        "plan": order.plan, "status": "pending", "created_at": datetime.datetime.now()
    })
    
    users_col.update_one({"email": order.email}, {"$set": {"source": "order"}}, upsert=True)

    msg = f"🚨 *NEW ORDER*\nPlan: {order.plan}\nTxID: `{order.transaction_id}`\nEmail: {order.email}\nID: `{order_id}`"
    kb = {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"apv:{order_id}"},{"text": "❌ Reject", "callback_data": f"rej:{order_id}"}]]}
    
    threading.Thread(target=send_telegram_msg, args=(msg, kb)).start()
    return {"status": "pending", "order_id": order_id}

# 5. Check Order Status
@app.get("/check-order")
def check_order(order_id: str):
    order = orders_col.find_one({"order_id": order_id})
    if not order: return {"status": "not_found"}
    return {"status": order["status"]}

# 6. Webhook
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try: data = await request.json()
    except: return {}
    
    if "callback_query" in data:
        cb = data["callback_query"]
        action_data = cb["data"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb["id"]})

        try: action, order_id = action_data.split(":")
        except: return {}
        
        order = orders_col.find_one({"order_id": order_id})
        if not order: return {}

        plan_map = {"1 Month":"1m", "3 Months":"3m", "6 Months":"6m", "12 Months":"12m", "Yearly":"12m"}
        db_type = plan_map.get(order.get("plan"), "1m")

        new_text = ""
        if action == "apv":
            code_doc = codes_col.find_one({"type": db_type, "is_sold": False})
            if code_doc:
                code_val = code_doc["code"]
                codes_col.update_one({"_id": code_doc["_id"]}, {"$set": {"is_sold": True}})
                orders_col.update_one({"order_id": order_id}, {"$set": {"status": "approved", "assigned_code": code_val}})
                
                email_html = get_email_template("order", {"plan": order['plan'], "code": code_val})
                threading.Thread(target=send_email_brevo, args=(order['email'], "Activation Successful - DARPRO4K", email_html)).start()
                
                new_text = f"✅ *APPROVED*\nUser: {order['email']}\nCode Emailed: `{code_val}`"
            else:
                new_text = f"⚠️ *NO STOCK* for {db_type}. Order: {order_id}"
                
        elif action == "rej":
            orders_col.update_one({"order_id": order_id}, {"$set": {"status": "rejected"}})
            new_text = f"❌ *REJECTED*\nOrder: {order_id}"

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText", 
                      json={"chat_id": chat_id, "message_id": msg_id, "text": new_text, "parse_mode": "Markdown"})

    return {"status": "ok"}

# --- MARKETING ENDPOINT (FIXED: Background Task) ---
def process_broadcast_queue(subject, content, limit, db_uri, brevo_key, sender):
    """Worker function to send emails in background"""
    try:
        # Re-connect in thread
        client = MongoClient(db_uri)
        db = client["iptv_store"]
        users_col = db["users"]
        
        # Select users who haven't received ads recently
        users = list(users_col.find({}).sort("last_marketing_date", 1).limit(limit))
        
        email_html = get_email_template("marketing", {"content": content})
        
        sent_count = 0
        for user in users:
            if "email" in user:
                # Send logic logic here directly to avoid circular dependency
                url = "https://api.brevo.com/v3/smtp/email"
                payload = {
                    "sender": {"name": "DARPRO4K Team", "email": sender},
                    "to": [{"email": user["email"]}],
                    "subject": subject,
                    "htmlContent": email_html
                }
                headers = {"accept": "application/json", "api-key": brevo_key, "content-type": "application/json"}
                
                try:
                    res = requests.post(url, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        users_col.update_one({"_id": user["_id"]}, {"$set": {"last_marketing_date": datetime.datetime.now()}})
                        sent_count += 1
                        time.sleep(0.2) # Rate limit safe
                except:
                    pass
        print(f"Broadcast finished: {sent_count} emails sent.")
    except Exception as e:
        print(f"Broadcast Error: {e}")

@app.post("/admin/broadcast")
def broadcast_email(req: MarketingRequest, background_tasks: BackgroundTasks):
    if req.password.strip() != ADMIN_PASSWORD: raise HTTPException(403, "Invalid Password")
    
    # Send immediately to UI, process in background
    background_tasks.add_task(
        process_broadcast_queue, 
        req.subject, 
        req.content, 
        req.limit, 
        MONGO_URI, 
        BREVO_API_KEY, 
        SENDER_EMAIL
    )
                
    return {"message": "Broadcast started in background. You can close this window."}

# --- ADMIN STATS ---
@app.get("/admin/stats")
def get_stats(password: str):
    if password.strip() != ADMIN_PASSWORD: raise HTTPException(403)
    stock = list(codes_col.aggregate([{"$match": {"is_sold": False}}, {"$group": {"_id": "$type", "count": {"$sum": 1}}}]))
    users_count = users_col.count_documents({})
    return {"stock": {r["_id"]: r["count"] for r in stock}, "total_users": users_count}

@app.post("/admin/add-codes")
def add_codes(req: CodeAddRequest):
    if req.password.strip() != ADMIN_PASSWORD: raise HTTPException(403)
    docs = [{"type": req.type, "code": c.strip(), "is_sold": False} for c in req.codes if c.strip()]
    if docs: codes_col.insert_many(docs)
    return {"message": f"Added {len(docs)} codes."}

@app.get("/admin/get-prompt")
def get_prompt(password: str):
    if password.strip() != ADMIN_PASSWORD: raise HTTPException(403)
    r = config_col.find_one({"key": "system_prompt"})
    return {"prompt": r["value"] if r else ""}

@app.post("/admin/update-prompt")
def update_prompt(req: PromptUpdateRequest):
    if req.password.strip() != ADMIN_PASSWORD: raise HTTPException(403)
    config_col.update_one({"key": "system_prompt"}, {"$set": {"value": req.new_prompt}}, upsert=True)
    return {"message": "Updated"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
