"""
📡 Binance Service
Handles all communication with Binance API (Spot & Futures)
"""

import requests
from datetime import datetime
from typing import List, Dict, Optional

class BinanceService:
    """Service for fetching data from Binance API"""

    # Base URLs
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"

    # Timeframe mappings
    TIMEFRAMES = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d',
        '1w': '1w'
    }

    def __init__(self):
        """Initialize the service"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CryptoSignalsBot/1.0'
        })

    def get_base_url(self, market_type: str) -> str:
        """Get base URL for market type"""
        if market_type.lower() == 'futures':
            return self.FUTURES_BASE_URL
        return self.SPOT_BASE_URL

    def get_top_coins(self, limit: int = 50, market_type: str = 'spot') -> List[Dict]:
        """
        Get top coins by 24h trading volume

        Args:
            limit: Number of coins to return
            market_type: 'spot' or 'futures'

        Returns:
            List of coin data with symbol, price, volume, change
        """
        try:
            base_url = self.get_base_url(market_type)

            if market_type.lower() == 'futures':
                endpoint = f"{base_url}/fapi/v1/ticker/24hr"
            else:
                endpoint = f"{base_url}/api/v3/ticker/24hr"

            response = self.session.get(endpoint, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Filter USDT pairs and sort by volume
            usdt_pairs = [
                {
                    'symbol': item['symbol'],
                    'price': float(item['lastPrice']),
                    'price_change': float(item['priceChangePercent']),
                    'volume_24h': float(item['quoteVolume']),
                    'high_24h': float(item['highPrice']),
                    'low_24h': float(item['lowPrice']),
                    'trades_24h': int(item.get('count', 0))
                }
                for item in data
                if item['symbol'].endswith('USDT')
                and not any(x in item['symbol'] for x in ['UP', 'DOWN', 'BEAR', 'BULL'])
                and float(item['quoteVolume']) > 1000000  # Min $1M volume
            ]

            # Sort by volume and return top coins
            sorted_coins = sorted(usdt_pairs, key=lambda x: x['volume_24h'], reverse=True)
            return sorted_coins[:limit]

        except Exception as e:
            print(f"Error fetching top coins: {e}")
            return []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        market_type: str = 'spot',
        limit: int = 200
    ) -> List[Dict]:
        """
        Get OHLCV (candlestick) data for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            timeframe: Candle timeframe
            market_type: 'spot' or 'futures'
            limit: Number of candles to fetch

        Returns:
            List of OHLCV data
        """
        try:
            base_url = self.get_base_url(market_type)

            if market_type.lower() == 'futures':
                endpoint = f"{base_url}/fapi/v1/klines"
            else:
                endpoint = f"{base_url}/api/v3/klines"

            params = {
                'symbol': symbol.upper(),
                'interval': self.TIMEFRAMES.get(timeframe, '1h'),
                'limit': limit
            }

            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse candlestick data
            ohlcv = []
            for candle in data:
                ohlcv.append({
                    'timestamp': datetime.fromtimestamp(candle[0] / 1000),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]),
                    'quote_volume': float(candle[7]),
                    'trades': int(candle[8])
                })

            return ohlcv

        except Exception as e:
            print(f"Error fetching OHLCV for {symbol}: {e}")
            return []

    def get_orderbook(
        self,
        symbol: str,
        market_type: str = 'spot',
        limit: int = 20
    ) -> Dict:
        """
        Get order book data

        Args:
            symbol: Trading pair symbol
            market_type: 'spot' or 'futures'
            limit: Depth of order book

        Returns:
            Order book with bids and asks
        """
        try:
            base_url = self.get_base_url(market_type)

            if market_type.lower() == 'futures':
                endpoint = f"{base_url}/fapi/v1/depth"
            else:
                endpoint = f"{base_url}/api/v3/depth"

            params = {
                'symbol': symbol.upper(),
                'limit': limit
            }

            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return {
                'bids': [[float(b[0]), float(b[1])] for b in data['bids']],
                'asks': [[float(a[0]), float(a[1])] for a in data['asks']],
                'bid_total': sum(float(b[1]) for b in data['bids']),
                'ask_total': sum(float(a[1]) for a in data['asks'])
            }

        except Exception as e:
            print(f"Error fetching orderbook for {symbol}: {e}")
            return {'bids': [], 'asks': [], 'bid_total': 0, 'ask_total': 0}

    def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Get funding rate for futures

        Args:
            symbol: Trading pair symbol

        Returns:
            Funding rate data
        """
        try:
            endpoint = f"{self.FUTURES_BASE_URL}/fapi/v1/fundingRate"
            params = {
                'symbol': symbol.upper(),
                'limit': 1
            }

            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data:
                return {
                    'symbol': data[0]['symbol'],
                    'funding_rate': float(data[0]['fundingRate']),
                    'funding_time': datetime.fromtimestamp(data[0]['fundingTime'] / 1000)
                }
            return None

        except Exception as e:
            print(f"Error fetching funding rate for {symbol}: {e}")
            return None

    def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Get open interest for futures

        Args:
            symbol: Trading pair symbol

        Returns:
            Open interest data
        """
        try:
            endpoint = f"{self.FUTURES_BASE_URL}/fapi/v1/openInterest"
            params = {'symbol': symbol.upper()}

            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return {
                'symbol': data['symbol'],
                'open_interest': float(data['openInterest']),
                'timestamp': datetime.now()
            }

        except Exception as e:
            print(f"Error fetching open interest for {symbol}: {e}")
            return None
