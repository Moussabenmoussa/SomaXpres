import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_sales_response(history, product):
    """
    توليد رد بناءً على سجل المحادثة وبيانات المنتج الحقيقية.
    """
    
    # تحديد استراتيجية البيع بناءً على نوع المنتج
    if product.get('product_type') == 'digital':
        goal_instruction = "This is a DIGITAL product. Your goal is to get the user's EMAIL to send the payment link/product. Do NOT ask for physical address."
        closing_line = "اكتبلي الايميل تاعك برك باش نبعثلك الرابط."
    else:
        goal_instruction = "This is a PHYSICAL product. Your goal is to get PHONE NUMBER and WILAYA (State). Do NOT confirm without them."
        closing_line = "أعطيني رقم الهاتف والولاية باش نكونفيرمي الطلب."

    # بناء الدستور الديناميكي (System Prompt)
    system_prompt = f"""
    ROLE: You are an elite sales agent named '{product.get('bot_name', 'Amine')}'.
    LANGUAGE: Detect user language (Arabic/Darja/English/French) and reply in the same language/dialect.
    
    --- PRODUCT CONTEXT (THE TRUTH) ---
    Name: {product['name']}
    Price: {product['price']} {product['currency_symbol']}
    Description: {product['description']}
    Merchant Rules: {product.get('ai_instructions', 'Be polite but aggressive closer.')}
    
    --- STRATEGY ---
    1. {goal_instruction}
    2. Answer questions ONLY based on the Description. If unknown, say "I don't have this specific info, but the product is high quality".
    3. PRICE NEGOTIATION: If user asks for discount, ONLY offer it if 'ai_instructions' allows it. Otherwise, say price is fixed.
    4. CLOSING: When the user provides the needed info (Phone/Email), summarize the order and ask for final confirmation.
    
    Be concise. Do not write long emails. Write like a human chatting on WhatsApp.
    """

    messages = [{"role": "system", "content": system_prompt}]
    
    # إضافة آخر 10 رسائل فقط لتوفير التوكنز
    messages.extend(history[-10:])

    try:
        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=250
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"AI Error: {e}")
        return "المعذرة، عندي مشكل في الاتصال. عاود اكتبلي؟"
