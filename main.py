from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from engine import AsyncEliteAgent

app = FastAPI(title="Sniper Alpha Tool")

html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ ALPHA SNIPER ⚡</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { background: #000; color: #ff3333; font-family: 'Courier New', monospace; display: flex; flex-direction: column; align-items: center; padding: 50px; }
        .box { border: 2px solid #ff3333; padding: 40px; width: 100%; max-width: 700px; background: #110000; }
        h1 { text-align: center; letter-spacing: 5px; margin-bottom: 40px; }
        input { width: 70%; padding: 15px; background: #000; border: 1px solid #ff3333; color: #fff; font-family: inherit; font-size: 18px; }
        button { width: 25%; padding: 15px; background: #ff3333; color: #000; border: none; font-weight: bold; cursor: pointer; font-size: 18px; }
        button:hover { background: #cc0000; }
        #result { margin-top: 30px; display: none; line-height: 1.5; font-size: 16px; border-top: 1px dashed #ff3333; padding-top: 20px; }
        strong { color: #fff; }
    </style>
</head>
<body>
    <div class="box">
        <h1>⚠️ INSIDER SNIPER</h1>
        <div style="display:flex; gap:10px;">
            <input type="text" id="target" placeholder="COIN (e.g. SOL, PEPE)...">
            <button onclick="scan()" id="btn">HUNT</button>
        </div>
        <div id="result"></div>
    </div>
    <script>
        async function scan() {
            const target = document.getElementById('target').value;
            const btn = document.getElementById('btn');
            const res = document.getElementById('result');
            
            if(!target) return;
            
            btn.innerText = "HUNTING...";
            btn.disabled = true;
            res.style.display = "none";
            res.innerHTML = "";

            try {
                const req = await fetch('/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({target: target})
                });
                const data = await req.json();
                res.innerHTML = marked.parse(data.report);
                res.style.display = "block";
            } catch (e) {
                res.innerText = "CONNECTION FAILED.";
                res.style.display = "block";
            }
            btn.innerText = "HUNT";
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

class Req(BaseModel):
    target: str

@app.get("/", response_class=HTMLResponse)
def home():
    return html_content

@app.post("/analyze")
async def analyze(r: Req):
    agent = AsyncEliteAgent()
    return {"report": await agent.execute_mission(r.target)}
