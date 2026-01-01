from flask import Blueprint, render_template, request, jsonify
from app.services.ai_agent import AIAgent
from app.services.utils import get_merchant_api_keys, check_credit_balance, deduct_credit

bp = Blueprint('public', __name__)

# 1. صفحة الهبوط (المنتج)
@bp.route('/p/<product_id>')
def product_page(product_id):
    # في المستقبل سنجلب المنتج من قاعدة البيانات
    # الآن سنصنع "منتج وهمي" لكي تعمل الصفحة الجديدة
    dummy_product = {
        "name": "ساعة رولكس فاخرة (Rolex Submariner)",
        "price": 3500,
        "description": "ساعة يد رجالية ذات جودة عالية، مقاومة للماء والخدش. تأتي في علبة فخمة مع ضمان لمدة 6 أشهر.",
        "image": "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?q=80&w=1000&auto=format&fit=crop"
    }
    
    # نمرر المنتج للصفحة
    return render_template('product.html', product=dummy_product)

# 2. نقطة الاتصال مع الروبوت (Chat API)
@bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_input = data.get('message')
    history = data.get('history', [])
    input_type = data.get('type', 'text')
    merchant_id = "demo_merchant_id"

    # نتجاوز فحص الرصيد مؤقتاً
    # if not check_credit_balance(merchant_id): ...

    groq_key, gemini_key = get_merchant_api_keys(merchant_id)
    
    agent = AIAgent(groq_key, gemini_key)
    
    # بيانات المنتج للذكاء الاصطناعي
    product_context = "ساعة رولكس 3500 دج، توصيل 58 ولاية."
    merchant_rules = "لا تخفيض، تأكد من الجدية."

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
