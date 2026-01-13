from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import asyncio
from scout import MarketRadar
from analyst import InstitutionalAnalyst
from vault import AlphaVault

# إعدادات
WATCHLIST_SECTORS = ["Solana", "AI", "Meme"]
vault = AlphaVault()

# المهام الخلفية
async def run_market_cycle():
    radar = MarketRadar()
    assets = await radar.scan_market(WATCHLIST_SECTORS)
    top_assets = assets[:3] # نقلل العدد للسرعة
    
    analyst = InstitutionalAnalyst()
    for asset in top_assets:
        try:
            signal = await analyst.analyze_asset(asset)
            await vault.save_intel(asset, signal)
        except:
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_market_cycle())
    yield

app = FastAPI(title="Alpha Radar Mobile", lifespan=lifespan)

class SearchRequest(BaseModel):
    query: str

html_interface = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Alpha Radar</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-color: #0b0e11;
            --card-bg: #151a21;
            --text-primary: #e6e8eb;
            --text-secondary: #9ca3af;
            --accent: #3b82f6;
            --border: #2d3748;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }
        body { background: var(--bg-color); color: var(--text-primary); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding-bottom: 50px; }
        
        /* Navbar Mobile Friendly */
        .navbar { 
            background: var(--card-bg); padding: 15px; border-bottom: 1px solid var(--border); 
            display: flex; flex-direction: column; gap: 10px; position: sticky; top: 0; z-index: 10; 
        }
        .logo { font-size: 18px; font-weight: 800; letter-spacing: 1px; width: 100%; text-align: center; }
        .logo span { color: var(--accent); }
        
        .search-box { display: flex; gap: 5px; width: 100%; }
        .search-input { 
            width: 100%; background: #0b0e11; border: 1px solid var(--border); color: white; 
            padding: 12px; border-radius: 6px; outline: none; font-size: 16px; 
        }
        .search-btn { 
            background: var(--accent); color: white; border: none; padding: 0 20px; 
            border-radius: 6px; font-weight: 600; white-space: nowrap; 
        }

        /* Container & Mobile Table */
        .container { padding: 15px; max-width: 100%; }
        .section-title { font-size: 12px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 10px; font-weight: 700; }

        .table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
        .data-table { width: 100%; border-collapse: collapse; background: var(--card-bg); min-width: 600px; /* Forces scroll on small screens */ }
        
        th { text-align: left; padding: 12px; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid var(--border); background: #1a202c; }
        td { padding: 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
        tr:hover { background: #1c222b; }
        
        .badge { padding: 3px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; display: inline-block; }
        .badge.HIGH { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .badge.MEDIUM { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .badge.LOW { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        
        .bullish { color: var(--success); }
        .bearish { color: var(--danger); }

        /* Mobile Modal */
        #modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 100; backdrop-filter: blur(3px); }
        .modal-content { 
            background: var(--card-bg); width: 90%; height: 90%; margin: 5% auto; padding: 20px; 
            border-radius: 12px; border: 1px solid var(--border); overflow-y: auto; position: relative;
        }
        .close-btn { 
            position: absolute; top: 10px; right: 15px; font-size: 28px; color: var(--text-secondary); 
            background: none; border: none; cursor: pointer; z-index: 10;
        }
        .markdown-body { line-height: 1.6; color: #d1d5db; font-size: 14px; margin-top: 20px; }
        .markdown-body h1, .markdown-body h2 { color: var(--accent); margin-top: 15px; font-size: 18px; }
    </style>
</head>
<body>

    <nav class="navbar">
        <div class="logo">ALPHA<span>RADAR</span></div>
        <div class="search-box">
            <input type="text" id="searchInput" class="search-input" placeholder="Search (e.g. SOL)...">
            <button onclick="manualSearch()" id="searchBtn" class="search-btn">SCAN</button>
        </div>
    </nav>

    <div class="container">
        <div class="section-title">📡 Live Intelligence Feed</div>
        
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Risk</th>
                        <th>Summary</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    <tr><td colspan="5" style="text-align:center; padding:20px; color:#6b7280;">Initializing System...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Modal -->
    <div id="modal">
        <div class="modal-content">
            <button class="close-btn" onclick="closeModal()">&times;</button>
            <div id="modal-body" class="markdown-body"></div>
        </div>
    </div>

    <script>
        async function manualSearch() {
            const query = document.getElementById('searchInput').value;
            if (!query) return;

            const btn = document.getElementById('searchBtn');
            const originalText = btn.innerText;
            btn.innerText = "⌛";
            btn.disabled = true;

            try {
                const res = await fetch('/api/manual-scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });
                const data = await res.json();
                
                if (data.status === "success") {
                    openModal(data.report.full_report);
                    loadData(); 
                } else {
                    alert("Error: " + data.detail);
                }
            } catch (e) {
                alert("Connection failed. Check internet.");
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        }

        async function loadData() {
            try {
                const res = await fetch('/api/feed');
                const data = await res.json();
                const tbody = document.getElementById('table-body');
                
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px;">Scanning market... wait a moment.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.forEach(item => {
                    const row = document.createElement('tr');
                    let signalClass = item.signal.includes('BULL') ? 'bullish' : (item.signal.includes('BEAR') ? 'bearish' : '');
                    
                    row.innerHTML = `
                        <td style="font-weight:bold; color:white;">${item.symbol}</td>
                        <td>$${item.price.toLocaleString()}</td>
                        <td class="${signalClass}">${item.signal}</td>
                        <td><span class="badge ${item.severity}">${item.severity}</span></td>
                        <td style="color:#d1d5db; min-width: 150px;">${item.headline}</td>
                    `;
                    row.onclick = () => openModal(item.full_report);
                    tbody.appendChild(row);
                });
            } catch (e) { console.log("Feed error"); }
        }

        function openModal(report) {
            document.getElementById('modal').style.display = 'block';
            document.getElementById('modal-body').innerHTML = marked.parse(report);
        }

        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }

        loadData();
        setInterval(loadData, 20000); // تحديث كل 20 ثانية
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return html_interface

@app.get("/api/feed")
async def get_feed():
    return await vault.get_latest_feed()

@app.post("/api/manual-scan")
async def manual_scan(request: SearchRequest):
    try:
        radar = MarketRadar()
        assets = await radar.scan_market([request.query])
        
        if not assets:
            raise HTTPException(status_code=404, detail="Not found")
            
        target_asset = assets[0]
        analyst = InstitutionalAnalyst()
        signal = await analyst.analyze_asset(target_asset)
        await vault.save_intel(target_asset, signal)
        
        return {"status": "success", "report": signal}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
