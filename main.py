from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import asyncio
from scout import MarketRadar
from analyst import InstitutionalAnalyst
from vault import AlphaVault

# ================= إعدادات النظام =================
WATCHLIST_SECTORS = ["Solana Ecosystem", "AI Coins", "Memecoins", "Ethereum", "Layer 2"]
vault = AlphaVault()

# ================= المهام الخلفية =================
async def run_market_cycle():
    """المسح التلقائي للسوق"""
    print("🔄 [AUTO-PILOT] Starting Background Scan...")
    radar = MarketRadar()
    assets = await radar.scan_market(WATCHLIST_SECTORS)
    top_assets = assets[:5] 
    
    analyst = InstitutionalAnalyst()
    for asset in top_assets:
        try:
            signal = await analyst.analyze_asset(asset)
            await vault.save_intel(asset, signal)
        except Exception as e:
            print(f"❌ [ERROR] Auto-scan failed for {asset.symbol}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_market_cycle())
    yield

app = FastAPI(title="Alpha Radar Pro", lifespan=lifespan)

# ================= طلب البحث اليدوي =================
class SearchRequest(BaseModel):
    query: str

# ================= الواجهة (HTML + JS) =================
html_interface = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Alpha Radar | Institutional</title>
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
        body { background: var(--bg-color); color: var(--text-primary); font-family: 'Segoe UI', sans-serif; margin: 0; }
        
        /* Navbar & Search */
        .navbar { background: var(--card-bg); padding: 15px 30px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }
        .logo { font-size: 20px; font-weight: 800; letter-spacing: 1px; }
        .logo span { color: var(--accent); }
        
        .search-box { display: flex; gap: 10px; width: 400px; }
        .search-input { width: 100%; background: #0b0e11; border: 1px solid var(--border); color: white; padding: 10px 15px; border-radius: 6px; outline: none; transition: 0.3s; }
        .search-input:focus { border-color: var(--accent); }
        .search-btn { background: var(--accent); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; white-space: nowrap; }
        .search-btn:disabled { background: var(--border); cursor: not-allowed; }

        /* Main Content */
        .container { padding: 40px; max-width: 1400px; margin: 0 auto; }
        .section-title { font-size: 14px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 15px; letter-spacing: 1px; font-weight: 700; }

        /* Table */
        .data-table { width: 100%; border-collapse: collapse; background: var(--card-bg); border-radius: 8px; overflow: hidden; }
        th { text-align: left; padding: 15px; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; border-bottom: 1px solid var(--border); }
        td { padding: 15px; border-bottom: 1px solid var(--border); font-size: 14px; }
        tr:hover { background: #1c222b; cursor: pointer; }
        
        /* Badges */
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }
        .badge.HIGH { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .badge.MEDIUM { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .badge.LOW { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        
        .bullish { color: var(--success); }
        .bearish { color: var(--danger); }

        /* Modal */
        #modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; backdrop-filter: blur(5px); }
        .modal-content { background: var(--card-bg); width: 60%; max-width: 800px; margin: 50px auto; padding: 30px; border-radius: 12px; border: 1px solid var(--border); max-height: 80vh; overflow-y: auto; }
        .close { float: right; font-size: 24px; cursor: pointer; }
        .markdown-body { line-height: 1.6; color: #d1d5db; }
        .markdown-body h1, .markdown-body h2 { color: var(--accent); margin-top: 20px; }
    </style>
</head>
<body>

    <nav class="navbar">
        <div class="logo">ALPHA<span>RADAR</span></div>
        
        <div class="search-box">
            <input type="text" id="searchInput" class="search-input" placeholder="Search specific asset (e.g. PEPE, WIF)...">
            <button onclick="manualSearch()" id="searchBtn" class="search-btn">SCAN</button>
        </div>
    </nav>

    <div class="container">
        <div class="section-title">📡 Live Institutional Feed</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Asset</th>
                    <th>Price</th>
                    <th>Signal</th>
                    <th>Risk</th>
                    <th>Intel Summary</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody id="table-body">
                <tr><td colspan="6" style="text-align:center; padding:20px; color:#6b7280;">Loading feed...</td></tr>
            </tbody>
        </table>
    </div>

    <!-- Modal for Report -->
    <div id="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="modal-body" class="markdown-body"></div>
        </div>
    </div>

    <script>
        // دالة البحث اليدوي
        async function manualSearch() {
            const query = document.getElementById('searchInput').value;
            if (!query) return;

            const btn = document.getElementById('searchBtn');
            btn.innerText = "SCANNING...";
            btn.disabled = true;

            try {
                // نرسل طلب البحث
                const res = await fetch('/api/manual-scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });
                
                const data = await res.json();
                
                if (data.status === "success") {
                    // نفتح التقرير فوراً في النافذة
                    openModal(data.report.full_report);
                    // ونحدث الجدول أيضاً لأننا حفظنا النتيجة
                    loadData(); 
                } else {
                    alert("Analysis failed: " + data.detail);
                }
            } catch (e) {
                alert("Connection error");
            } finally {
                btn.innerText = "SCAN";
                btn.disabled = false;
            }
        }

        // دالة جلب البيانات للجدول
        async function loadData() {
            try {
                const res = await fetch('/api/feed');
                const data = await res.json();
                const tbody = document.getElementById('table-body');
                
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px;">System initializing...</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.forEach(item => {
                    const row = document.createElement('tr');
                    
                    let signalClass = 'neutral';
                    if (item.signal.includes('BULL')) signalClass = 'bullish';
                    if (item.signal.includes('BEAR') || item.signal.includes('RISK')) signalClass = 'bearish';

                    row.innerHTML = `
                        <td style="font-weight:bold; color:white;">${item.symbol}</td>
                        <td>$${item.price.toLocaleString()}</td>
                        <td class="${signalClass}">${item.signal}</td>
                        <td><span class="badge ${item.severity}">${item.severity}</span></td>
                        <td style="color:#d1d5db;">${item.headline}</td>
                        <td style="color:#6b7280; font-size:12px;">Just now</td>
                    `;
                    row.onclick = () => openModal(item.full_report);
                    tbody.appendChild(row);
                });
            } catch (e) { console.log(e); }
        }

        function openModal(report) {
            document.getElementById('modal').style.display = 'block';
            document.getElementById('modal-body').innerHTML = marked.parse(report);
        }

        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }

        loadData();
        // تحديث الجدول كل 30 ثانية
        setInterval(loadData, 30000);
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

# ================= نقطة الاتصال الجديدة للبحث اليدوي =================
@app.post("/api/manual-scan")
async def manual_scan(request: SearchRequest):
    """
    هذا هو المحرك الذي يقوم بالبحث الفوري عند الطلب
    """
    try:
        # 1. البحث عن العملة في DexScreener
        radar = MarketRadar()
        assets = await radar.scan_market([request.query])
        
        if not assets:
            raise HTTPException(status_code=404, detail="Asset not found or low liquidity")
            
        target_asset = assets[0] # نأخذ أفضل نتيجة
        
        # 2. تحليلها فوراً
        analyst = InstitutionalAnalyst()
        signal = await analyst.analyze_asset(target_asset)
        
        # 3. حفظها في قاعدة البيانات (ليراها الجميع في الجدول أيضاً)
        await vault.save_intel(target_asset, signal)
        
        return {"status": "success", "report": signal}
        
    except Exception as e:
        return {"status": "error", "detail": str(e)}
