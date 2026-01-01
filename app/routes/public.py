from flask import Blueprint, render_template, request, jsonify
from bson.objectid import ObjectId
from app.services.db import get_collection
from app.services.ai_agent import AIAgent
# تأكد أن TEMP_MEMORY مستوردة هنا
from app.services.utils import get_merchant_api_keys, check_credit_balance, deduct_credit, TEMP_MEMORY

bp = Blueprint('public', __name__)

@bp.route('/p/<product_id>')
def product_page(product_id):
    # محاولة البحث في الذاكرة (للمنتجات الجديدة)
    product = None
    if f"prod_{product_id}" in TEMP_MEMORY:
        product = TEMP_MEMORY[f"prod_{product_id}"]
    
    # محاولة البحث في قاعدة البيانات
    if not product:
        products_col = get_collection('products')
        if products_col:
            try:
                product = products_col.find_one({"_id": ObjectId(product_id)})
            except: pass

    if not product:
        return "<h1>المنتج غير موجود (تأكد من الرابط)</h1>", 404

    return render_template('product.html', product=product)

@bp.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        data = request.json
        user_input = data.get('message')
        history = data.get('history', [])
        input_type = data.get('type', 'text')
        merchant_id = "demo_merchant_id"

        # 1. جلب المفاتيح
        groq_key, gemini_key = get_merchant_api_keys(merchant_id)
        
        # 2. تشغيل العميل الذكي
        agent = AIAgent(groq_key, gemini_key)
        
        # 3. إعداد سياق المنتج (IPTV)
        # نحاول جلب "آخر منتج تمت إضافته" للذاكرة لاستخدامه كسياق
        # (حل مؤقت ذكي لكي يفهم الروبوت أنك تبيع IPTV)
        product_context = "منتج عام."
        merchant_rules = "كن مفيداً."
        
        # البحث عن آخر تعليمات في الذاكرة
        for key, val in TEMP_MEMORY.items():
            if key.startswith('prod_'):
                product_context = f"{val.get('name')} بسعر {val.get('price')}"
                merchant_rules = val.get('ai_instructions', merchant_rules)
        
        # البحث في قاعدة البيانات إذا وجدت
        products_col = get_collection('products')
        if products_col:
            last_prod = products_col.find_one(sort=[('_id', -1)])
            if last_prod:
                product_context = f"{last_prod.get('name')} بسعر {last_prod.get('price')}"
                merchant_rules = last_prod.get('ai_instructions', merchant_rules)

        # 4. الرد
        response = agent.think_and_speak(
            user_input=user_input,
            history=history,
            product_context=product_context,
            merchant_rules=merchant_rules,
            persona="amine",
            input_type=input_type
        )
        
        deduct_credit(merchant_id)
        return jsonify(response)

    except Exception as e:
        print(f"🔥 Server Error: {e}")
        # رد احتياطي بدل "انقطع الاتصال"
        return jsonify({"text": "سمحلي، كاين ضغط على السيرفر. عاود أكتبلي؟", "audio": None})
