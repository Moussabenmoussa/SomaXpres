from flask import Blueprint, render_template, request, jsonify, current_app
from app.services.ai_agent import AIAgent
from app.services.utils import get_merchant_api_keys, check_credit_balance, deduct_credit

bp = Blueprint('public', __name__)

# 1. صفحة الهبوط (المنتج)
@bp.route('/p/<product_id>')
def product_page(product_id):
    # في الواقع سنجلب بيانات المنتج من قاعدة البيانات
    # الآن سنرسل بيانات وهمية للتجربة
    return render_template('product.html', product_id=product_id)

# 2. نقطة الاتصال مع الروبوت (Chat API)
@bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_input = data.get('message')
    history = data.get('history', [])
    input_type = data.get('type', 'text') # voice or text
    merchant_id = "demo_merchant_id" # سنستخدم تاجر افتراضي للتجربة

    # 1. فحص الرصيد
    if not check_credit_balance(merchant_id):
        return jsonify({"text": "عذراً، المتجر مشغول حالياً. يرجى ترك رقمك.", "audio": None})

    # 2. جلب المفاتيح (الخاصة أو العامة)
    groq_key, gemini_key = get_merchant_api_keys(merchant_id)
    
    # 3. تشغيل العقل (أمين)
    agent = AIAgent(groq_key, gemini_key)
    
    # بيانات المنتج (وهمية حالياً)
    product_context = "ساعة رولكس تقليد درجة أولى. السعر 3500 دج. التوصيل متوفر 58 ولاية. ضمان 6 أشهر."
    merchant_rules = "ممنوع التخفيض. التوصيل للعاصمة مجاني، باقي الولايات 400 دج."

    response = agent.think_and_speak(
        user_input=user_input,
        history=history,
        product_context=product_context,
        merchant_rules=merchant_rules,
        persona="amine", # يمكن تغييرها لسارة
        input_type=input_type
    )

    # 4. خصم الرصيد (نقطة واحدة)
    deduct_credit(merchant_id)

    return jsonify(response)
