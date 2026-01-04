"""
🚀 Crypto Signals Bot - Main Application
Professional Trading Signals for Binance (Spot & Futures)
"""

import os
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Import services
from services.binance_service import BinanceService
from services.analyzer import TechnicalAnalyzer
from services.telegram_service import TelegramService
from services.database import DatabaseService

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize services
binance = BinanceService()
analyzer = TechnicalAnalyzer()
telegram = TelegramService(
    bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID')
)
db = DatabaseService(os.getenv('MONGODB_URI'))

# Global state
signals_cache = []
last_update = None
is_running = False

# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Render main dashboard"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get bot status"""
    return jsonify({
        'is_running': is_running,
        'last_update': last_update.isoformat() if last_update else None,
        'signals_count': len(signals_cache),
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/signals')
def get_signals():
    """Get latest signals"""
    limit = request.args.get('limit', 50, type=int)
    signal_type = request.args.get('type', 'all')  # all, long, short
    min_strength = request.args.get('min_strength', 0, type=int)

    filtered = signals_cache

    if signal_type != 'all':
        filtered = [s for s in filtered if s['type'].lower() == signal_type.lower()]

    if min_strength > 0:
        filtered = [s for s in filtered if s['strength'] >= min_strength]

    return jsonify({
        'signals': filtered[:limit],
        'total': len(filtered),
        'last_update': last_update.isoformat() if last_update else None
    })

@app.route('/api/signals/history')
def get_signals_history():
    """Get signals history from database"""
    limit = request.args.get('limit', 100, type=int)
    signals = db.get_signals(limit=limit)
    return jsonify({'signals': signals})

@app.route('/api/top-coins')
def get_top_coins():
    """Get top 50 coins by volume"""
    try:
        coins = binance.get_top_coins(limit=50)
        return jsonify({'coins': coins})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """Analyze a specific symbol"""
    try:
        timeframe = request.args.get('timeframe', '1h')
        market_type = request.args.get('market', 'spot')  # spot or futures

        # Get OHLCV data
        ohlcv = binance.get_ohlcv(symbol, timeframe, market_type)

        if not ohlcv:
            return jsonify({'error': 'No data available'}), 404

        # Analyze
        analysis = analyzer.analyze(ohlcv, symbol, timeframe)

        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update bot settings"""
    if request.method == 'GET':
        settings = db.get_settings()
        return jsonify(settings)
    else:
        new_settings = request.json
        db.update_settings(new_settings)
        return jsonify({'success': True})

# =============================================================================
# SIGNAL SCANNER
# =============================================================================

def scan_for_signals():
    """Scan top coins for trading signals"""
    global signals_cache, last_update, is_running

    is_running = True
    new_signals = []

    try:
        # Get settings
        settings = db.get_settings()
        min_strength = settings.get('min_signal_strength', 70)
        timeframes = settings.get('timeframes', ['15m', '1h', '4h'])
        markets = settings.get('markets', ['spot', 'futures'])

        # Get top coins
        top_coins = binance.get_top_coins(limit=50)

        for coin in top_coins:
            symbol = coin['symbol']

            for market in markets:
                for tf in timeframes:
                    try:
                        # Get OHLCV data
                        ohlcv = binance.get_ohlcv(symbol, tf, market)

                        if not ohlcv or len(ohlcv) < 50:
                            continue

                        # Analyze
                        analysis = analyzer.analyze(ohlcv, symbol, tf)

                        # Check if signal is strong enough
                        if analysis['signal'] != 'NEUTRAL' and analysis['strength'] >= min_strength:
                            signal = {
                                'symbol': symbol,
                                'market': market.upper(),
                                'timeframe': tf,
                                'type': analysis['signal'],
                                'strength': analysis['strength'],
                                'entry': analysis['entry'],
                                'stop_loss': analysis['stop_loss'],
                                'take_profit_1': analysis['take_profit_1'],
                                'take_profit_2': analysis['take_profit_2'],
                                'take_profit_3': analysis['take_profit_3'],
                                'risk_reward': analysis['risk_reward'],
                                'indicators': analysis['indicators'],
                                'timestamp': datetime.utcnow().isoformat(),
                                'price': coin['price'],
                                'volume_24h': coin['volume_24h']
                            }

                            new_signals.append(signal)

                            # Save to database
                            db.save_signal(signal)

                            # Send to Telegram
                            telegram.send_signal(signal)

                    except Exception as e:
                        print(f"Error analyzing {symbol} {tf}: {e}")
                        continue

                    # Small delay to avoid rate limits
                    time.sleep(0.1)

        # Update cache
        signals_cache = sorted(new_signals, key=lambda x: x['strength'], reverse=True)
        last_update = datetime.utcnow()

        print(f"✅ Scan complete: {len(new_signals)} signals found")

    except Exception as e:
        print(f"❌ Scan error: {e}")

    finally:
        is_running = False

# =============================================================================
# SCHEDULER
# =============================================================================

def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()

    # Scan every 5 minutes
    scheduler.add_job(scan_for_signals, 'interval', minutes=5, id='signal_scanner')

    # Initial scan
    scheduler.add_job(scan_for_signals, 'date', id='initial_scan')

    scheduler.start()
    print("🚀 Scheduler started")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Start scheduler in background
    start_scheduler()

    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
