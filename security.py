from fastapi import HTTPException, Response

# --- القائمة السوداء للإيميلات المؤقتة ---
BLOCKED_DOMAINS = [
    "10minutemail.com", "guerrillamail.com", "sharklasers.com", "yopmail.com", 
    "temp-mail.org", "mailinator.com", "throwawaymail.com", "getairmail.com",
    "tempmail.net", "dispostable.com", "fake-box.com", "mail.tm", "maildrop.cc"
]

def verify_trial_eligibility(email: str, ip: str, fingerprint: str, trials_collection):
    """
    يفحص أهلية المستخدم للحصول على تجربة مجانية.
    يرفع استثناء (Error 400) إذا تم كشف احتيال.
    """
    
    # 1. فحص نطاق الإيميل
    try:
        domain = email.split('@')[-1].lower()
        if domain in BLOCKED_DOMAINS:
            raise HTTPException(status_code=400, detail="Temporary emails are not allowed.")
    except:
        pass # If email format is wrong, let validator handle it

    # 2. فحص تكرار الإيميل
    if trials_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Trial already claimed for this email.")

    # 3. فحص تكرار عنوان الشبكة (IP)
    if trials_collection.find_one({"ip": ip}):
        raise HTTPException(status_code=400, detail="Trial limit reached for this network.")

    # 4. فحص بصمة الجهاز (Fingerprint)
    if fingerprint:
        if trials_collection.find_one({"fingerprint": fingerprint}):
            raise HTTPException(status_code=400, detail="This device has already used a free trial.")

def get_fingerprint_script():
    """
    يعيد كود جافاسكريبت للواجهة
    """
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
