from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
from scout import MarketRadar
from analyst import InstitutionalAnalyst
from vault import AlphaVault

# ================= إعدادات النظام =================
# العملات أو القطاعات التي يراقبها الرادار تلقائياً
WATCHLIST_SECTORS = ["Solana Ecosystem", "AI Coins", "Memecoins", "Ethereum", "Layer 2"]

vault = AlphaVault()

# ================= المهام الخلفية (The Auto-Pilot) =================
async def run_market_cycle():
    """هذه الوظيفة تعمل وحدها في الخلفية لجلب البيانات وتحليلها"""
    print("🔄 [SYSTEM] Starting Market Intelligence Cycle...")
    
    # 1. الرادار: جلب العملات النشطة
    radar = MarketRadar()
    assets = await radar.scan_market(WATCHLIST_SECTORS)
    
    # نأخذ أفضل 5 عملات فقط لتوفير موارد الـ API في النسخة التجريبية
    # في النسخة المدفوعة يمكنك زيادة الرقم
    top_assets = assets[:5] 
    
    # 2. المحلل: فحص كل عملة
    analyst = InstitutionalAnalyst()
    for asset in top_assets:
        try:
            signal = await analyst.analyze_asset(asset)
            # 3. المخزن: حفظ النتيجة
            await vault.save_intel(asset, signal)
            print(f"✅ [SAVED] Report for {asset.symbol} stored in Vault.")
        except Exception as e:
            print(f"❌ [ERROR] Failed to analyze {asset.symbol}: {e}")
            
    print("💤 [SYSTEM] Cycle complete. Sleeping...")

# تشغيل الدورة عند بدء السيرفر
@asynccontextmanager
async def lifespan(app: FastAPI):
    # شغل المسح مرة واحدة عند الإقلاع
    asyncio.create_task(run_market_cycle())
    yield

app = FastAPI(title="Institutional Crypto Radar", lifespan=lifespan)

# ================= واجهة المستخدم (Nansen Style) =================
# واجهة احترافية، جداول نظيفة، ألوان هادئة
html_interface = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Alpha Radar | Institutional View</title>
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
        body { background: var(--bg-color); color: var(--text-primary); font-family: 'Inter', sans-serif; margin: 0; padding: 0; }
        
        /* Header */
        .navbar { background: var(--card-bg); padding: 15px 30px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 20px; font-weight: 700; letter-spacing: 1px; color: var(--text-primary); }
        .logo span { color: var(--accent); }
        .status { font-size: 12px; color: var(--success); display: flex; align-items: center; gap: 5px; }
        .dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; }

        /* Main Layout */
        .container { padding: 40px; max-width: 1400px; margin: 0 auto; }
        .header-section { display: flex; justify-content: space-between; margin-bottom: 20px; }
        h2 { font-weight: 500; margin: 0; }
        .refresh-btn { background: var(--accent); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        .refresh-btn:hover { opacity: 0.9; }

        /* Data Table (The Nansen Look) */
        .data-table { width: 100%; border-collapse: collapse; background: var(--card-bg); border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        th { text-align: left; padding: 16px; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; border-bottom: 1px solid var(--border); }
        td { padding: 16px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: middle; }
        tr:last-child td { border-bottom: none; }
        tr:hover { background: #1c222b; cursor: pointer; }

        /* Badges */
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
        .badge.HIGH { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
        .badge.MEDIUM { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }
        .badge.LOW { background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }
        
        .signal-text { font-weight: 600; }
        .bullish { color: var(--success); }
        .bearish { color: var(--danger); }
        .neutral { color: var(--text-secondary); }

        /* Modal for Reports */
        #modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; backdrop-filter: blur(5px); }
        .modal-content { background: var(--card-bg); width: 60%; max-width: 800px; margin: 50px auto; padding: 30px; border-radius: 12px; border: 1px solid var(--border); max-height: 80vh; overflow-y: auto; }
        .close { float: right; font-size: 24px; cursor: pointer; color: var(--text-secondary); }
        .markdown-body { line-height: 1.6; color: #d1d5db; }
        .markdown-body h1, .markdown-body h2 { color: var(--accent); margin-top: 20px; }
        .markdown-body strong { color: white; }

        /* Loading */
        .loading { text-align: center; padding: 20px; color: var(--text-secondary); }

    </style>
</head>
<body>

    <nav class="navbar">
        <div class="logo">ALPHA<span>RADAR</span></div>
        <div class="status"><div class="dot"></div> LIVE FEED</div>
    </nav>

    <div class="container">
        <div class="header-section">
            <h2>Institutional Intel Feed</h2>
            <button class="refresh-btn" onclick="loadData()">Refresh Data</button>
        </div>

        <table class="data-table">
            <thead>
                <tr>
                    <th>Asset</th>
                    <th>Price</th>
                    <th>AI Signal</th>
                    <th>Risk Level</th>
                    <th>Intelligence Summary</th>
                    <th>Last Updated</th>
                </tr>
            </thead>
            <tbody id="table-body">
                <tr><td colspan="6" class="loading">Loading intelligent data...</td></tr>
            </tbody>
        </table>
    </div>

    <!-- Modal for Full Report -->
    <div id="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="modal-body" class="markdown-body"></div>
        </div>
    </div>

    <script>
        async function loadData() {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '<tr><td colspan="6" class="loading">Fetching latest intel from Vault...</td></tr>';
            
            try {
                const res = await fetch('/api/feed');
                const data = await res.json();
                
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="loading">System is initializing... waiting for first scan cycle. Try again in 1 minute.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.forEach(item => {
                    const row = document.createElement('tr');
                    
                    // Signal Color Logic
                    let signalClass = 'neutral';
                    if (item.signal.includes('BULL')) signalClass = 'bullish';
                    if (item.signal.includes('BEAR') || item.signal.includes('RISK')) signalClass = 'bearish';

                    row.innerHTML = `
                        <td style="font-weight:bold; color:white;">${item.symbol} <span style="font-size:12px; color:#6b7280;">${item.name}</span></td>
                        <td>$${item.price.toLocaleString()}</td>
                        <td class="signal-text ${signalClass}">${item.signal}</td>
                        <td><span class="badge ${item.severity}">${item.severity}</span></td>
                        <td style="color:#d1d5db;">${item.headline}</td>
                        <td style="color:#6b7280; font-size:12px;">Just now</td>
                    `;
                    
                    // Click to open report
                    row.onclick = () => openModal(item.full_report);
                    tbody.appendChild(row);
                });
            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red">Connection Failed</td></tr>';
            }
        }

        function openModal(report) {
            document.getElementById('modal').style.display = 'block';
            document.getElementById('modal-body').innerHTML = marked.parse(report);
        }

        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }

        // Load data on startup
        loadData();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return html_interface

@app.get("/api/feed")
async def get_feed():
    """API لجلب البيانات للواجهة"""
    return await vault.get_latest_feed()

@app.post("/api/force-scan")
async def force_scan(background_tasks: BackgroundTasks):
    """زر طوارئ للمدير: إجبار النظام على المسح الآن"""
    background_tasks.add_task(run_market_cycle)
    return {"status": "Market scan initiated in background"}
