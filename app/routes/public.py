from flask import Blueprint, render_template, request, jsonify, abort
from bson.objectid import ObjectId
from app.services.db import get_collection
from app.services.ai_agent import AIAgent
from app.services.utils import get_merchant_api_keys, check_credit_balance, deduct_credit, TEMP_MEMORY

bp = Blueprint('public', __name__)

# 1. صفحة المنتج (الديناميكية الحقيقية)
@bp.route('/p/<product_id>')
def product_page(product_id):
    products_col = get_collection('products')
    product = None

    # أ. محاولة البحث في قاعدة البيانات (MongoDB)
    if products_col is not None:
        try:
            product = products_col.find_one({"_id": ObjectId(product_id)})
        except:
            pass # إذا كان الآيدي غير صالح

    # ب. محاولة البحث في الذاكرة المؤقتة (إذا كانت القاعدة معطلة)
    if not product:
        # البحث عن المنتج الذي تم إنشاؤه مؤخراً في الذاكرة
        # (هذا حل احتياطي للتجربة إذا لم تكن MongoDB متصلة)
        for key, val in TEMP_MEMORY.items():
            if key == f"prod_{product_id}" or key == product_id:
                product = val
                break
    
    # ج. إذا لم نجد المنتج، نعرض صفحة خطأ 404
    if not product:
        return "<h1>عذراً، هذا المنتج غير موجود أو تم حذفه!</h1>", 404

    # د. عرض المنتج الحقيقي
    return render_template('product.html', product=product)


# 2. نقطة الاتصال مع الروبوت (Chat API)
@bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_input = data.get('message')
    history = data.get('history', [])
    input_type = data.get('type', 'text')
    merchant_id = "demo_merchant_id"

    # جلب المفاتيح
    groq_key, gemini_key = get_merchant_api_keys(merchant_id)
    agent = AIAgent(groq_key, gemini_key)
    
    # --- هنا الذكاء: جلب سياق المنتج الحالي ---
    # نحاول معرفة المنتج الذي يتحدث عنه الزبون من الرابط السابق (Referer) أو نفترض أنه آخر منتج
    # للتبسيط الآن، سنستخدم سياقاً عاماً أو نبحث عن المنتج إذا تم تمرير الـ ID
    
    # (ملاحظة: لجعل الروبوت يعرف المنتج بدقة، يجب أن يرسل product_id مع الطلب،
    # لكن حالياً سنستخدم الذاكرة أو قاعدة البيانات لجلب آخر منتج تمت زيارته أو تفاصيل عامة)
    
    # حل مؤقت ذكي: الروبوت سيستخدم "تعليمات المنتج" المخزنة إذا وجدت
    product_context = "منتج مميز من SomaXpres."
    merchant_rules = "كن لبقاً ومحترفاً."
    
    # محاولة جلب "دستور المنتج" من آخر منتج مضاف (للتجربة)
    products_col = get_collection('products')
    if products_col:
        last_product = products_col.find_one(sort=[('_id', -1)])
        if last_product:
            product_context = f"{last_product.get('name')} بسعر {last_product.get('price')} دج."
            merchant_rules = last_product.get('ai_instructions', merchant_rules)

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
