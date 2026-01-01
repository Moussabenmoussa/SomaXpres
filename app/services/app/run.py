import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # الحصول على المنفذ من بيئة السيرفر أو استخدام 10000 افتراضياً
    port = int(os.environ.get("PORT", 10000))
    # تشغيل السيرفر
    app.run(host='0.0.0.0', port=port)
