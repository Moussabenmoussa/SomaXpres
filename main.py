from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from engine import AsyncEliteAgent

app = FastAPI(title="Elite Crypto Hunter")

# ================= واجهة المستخدم (The Dashboard) =================
html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Hunter Elite</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body {
            background-color: #000000;
            color: #00ff41;
            font-family: 'Courier New', Courier, monospace;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            width: 90%;
            max-width: 900px;
            border: 1px solid #00ff41;
            padding: 20px;
            box-shadow: 0 0 15px #00ff41;
            background: #0d0d0d;
        }
        h1 { text-align: center; text-transform: uppercase; border-bottom: 1px dashed #00ff41; padding-bottom: 10px; }
        .input-group { display: flex; gap: 10px; margin: 20px 0; }
        input {
            flex: 1; padding: 15px; background: #000; color: #00ff41;
            border: 1px solid #00ff41; font-family: inherit; font-size: 16px;
        }
        button {
            padding: 15px 30px; background: #00ff41; color: #000; font-weight: bold;
            border: none; cursor: pointer; font-family: inherit; font-size: 16px;
        }
        button:hover { background: #00cc33; }
        button:disabled { background: #333; color: #555; cursor: wait; }
        #result {
            margin-top: 20px; padding: 20px; border-top: 1px solid #333;
            display: none; line-height: 1.6; color: #e0e0e0;
        }
        #result strong { color: #fff; }
        #result h1, #result h2 { color: #00ff41; margin-top: 20px; }
        .loader { display: none; text-align: center; color: #00ff41; margin: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👁️ CLASSIFIED CRYPTO INTEL 👁️</h1>
        <div class="input-group">
            <input type="text" id="target" placeholder="ENTER TARGET NAME (e.g. BTC, KASPA, PEPE)...">
            <button onclick="analyze()" id="btn">INITIATE SCAN</button>
        </div>
        <div class="loader" id="loader">
            <p>ACCESSING SATELLITE DATA...</p>
            <p>ANALYZING BLOCKCHAIN...</p>
            <p>PLEASE WAIT...</p>
        </div>
        <div id="result"></div>
    </div>
    <script>
        async function analyze() {
            const target = document.getElementById('target').value;
            if (!target) return alert("NO TARGET SPECIFIED");

            const btn = document.getElementById('btn');
            const loader = document.getElementById('loader');
            const resultDiv = document.getElementById('result');

            btn.disabled = true;
            btn.innerText = "SCANNING...";
            loader.style.display = "block";
            resultDiv.style.display = "none";

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target: target })
                });
                const data = await response.json();
                
                resultDiv.innerHTML = marked.parse(data.report);
                resultDiv.style.display = "block";
            } catch (error) {
                resultDiv.innerHTML = `<p style="color:red">CONNECTION LOST: ${error.message}</p>`;
                resultDiv.style.display = "block";
            } finally {
                btn.disabled = false;
                btn.innerText = "INITIATE SCAN";
                loader.style.display = "none";
            }
        }
    </script>
</body>
</html>
"""

class AnalysisRequest(BaseModel):
    target: str

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content

@app.post("/analyze")
async def analyze_crypto(request: AnalysisRequest):
    try:
        agent = AsyncEliteAgent()
        report = await agent.execute_mission(request.target)
        return {"status": "success", "report": report}
    except Exception as e:
        # حتى لو حدث خطأ، سنعرضه في الواجهة بدلاً من 500
        return {"status": "error", "report": f"SYSTEM FAILURE: {str(e)}"}
