from fastapi import HTTPException, Response

# قائمة حظر الإيميلات المؤقتة
BLOCKED_DOMAINS = [
    "10minutemail.com", "guerrillamail.com", "sharklasers.com", "yopmail.com", 
    "temp-mail.org", "mailinator.com", "throwawaymail.com", "getairmail.com",
    "tempmail.net", "dispostable.com", "fake-box.com", "mail.tm", "maildrop.cc"
]

def verify_trial_eligibility(email: str, ip: str, fingerprint: str, trials_collection):
    """
    نسخة صارمة جداً: ترفض أي طلب بدون بصمة جهاز واضحة.
    """
    
    # 1. القاتل الصامت للـ VPN: رفض الطلب إذا لم تصل البصمة
    # إذا كان المتصفح بطيئاً أو يحاول التحايل بإخفاء البصمة، سيتم طرده فوراً
    if not fingerprint or fingerprint == "null" or len(str(fingerprint)) < 5:
        raise HTTPException(status_code=400, detail="Security Check Loading... Please wait 5 seconds and click again.")

    # 2. فحص هل البصمة موجودة مسبقاً (هنا يتم كشف الـ VPN)
    # حتى لو غيرت الدولة 100 مرة، بصمة جهازك تبقى مسجلة هنا
    if trials_collection.find_one({"fingerprint": fingerprint}):
        raise HTTPException(status_code=400, detail="This device has already taken a Free Trial.")

    # 3. فحص الإيميلات المؤقتة
    try:
        domain = email.split('@')[-1].lower()
        if domain in BLOCKED_DOMAINS:
            raise HTTPException(status_code=400, detail="Temporary emails are blocked.")
    except:
        pass 

    # 4. فحص تكرار الإيميل (طبقة حماية إضافية)
    if trials_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already used.")

    # 5. فحص IP (للحالات العادية بدون VPN)
    if trials_collection.find_one({"ip": ip}):
        raise HTTPException(status_code=400, detail="Trial limit reached for this IP.")

def get_fingerprint_script():
    js_content = """
    (function() {
        var script = document.createElement('script');
        script.src = "https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js";
        script.onload = function() {
            FingerprintJS.load().then(function(fp) {
                fp.get().then(function(result) {
                    window.userFingerprint = result.visitorId;
                    console.log("Secured: " + result.visitorId);
                });
            });
        };
        document.head.appendChild(script);
    })();
    """
    return Response(content=js_content, media_type="application/javascript")
