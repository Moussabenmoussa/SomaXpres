from flask import Blueprint, render_template, request, jsonify
from app.services.ai_agent import AIAgent
from app.services.utils import get_merchant_api_keys, check_credit_balance, deduct_credit

bp = Blueprint('public', __name__)

@bp.route('/p/<product_id>')
def product_page(product_id):
    return render_template('product.html', product_id=product_id)

@bp.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    merchant_id = "demo_merchant_id"

    # تجاوز فحص الرصيد مؤقتاً للتجربة إذا لم تكن قاعدة البيانات جاهزة
    # if not check_credit_balance(merchant_id):
    #    return jsonify({"text": "المتجر مشغول.", "audio": None})

    groq_key, gemini_key = get_merchant_api_keys(merchant_id)
    agent = AIAgent(groq_key, gemini_key)
    
    response = agent.think_and_speak(
        user_input=data.get('message'),
        history=data.get('history', []),
        product_context="ساعة رولكس 3500 دج.",
        merchant_rules="ممنوع التخفيض.",
        persona="amine",
        input_type=data.get('type', 'text')
    )
    
    deduct_credit(merchant_id)
    return jsonify(response)
