"""
💾 Database Service
MongoDB operations for storing signals and settings
"""

from pymongo import MongoClient, DESCENDING
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

class DatabaseService:
    """Service for MongoDB operations"""

    def __init__(self, mongo_uri: str = None):
        """
        Initialize database connection

        Args:
            mongo_uri: MongoDB connection string
        """
        self.mongo_uri = mongo_uri
        self.client = None
        self.db = None
        self.enabled = False

        if mongo_uri:
            try:
                self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                # Test connection
                self.client.server_info()
                self.db = self.client.crypto_signals
                self.enabled = True
                print("✅ MongoDB connected successfully")
                self._ensure_indexes()
            except Exception as e:
                print(f"⚠️ MongoDB connection failed: {e}")
                self.enabled = False
        else:
            print("⚠️ MongoDB disabled: No URI provided")

    def _ensure_indexes(self):
        """Create necessary indexes"""
        if not self.enabled:
            return

        try:
            # Signals collection indexes
            self.db.signals.create_index([('timestamp', DESCENDING)])
            self.db.signals.create_index([('symbol', 1)])
            self.db.signals.create_index([('type', 1)])
            self.db.signals.create_index([('strength', DESCENDING)])

            # TTL index to auto-delete old signals (30 days)
            self.db.signals.create_index(
                [('created_at', 1)],
                expireAfterSeconds=30 * 24 * 60 * 60
            )

        except Exception as e:
            print(f"⚠️ Index creation error: {e}")

    def save_signal(self, signal: Dict) -> Optional[str]:
        """
        Save a trading signal to database

        Args:
            signal: Signal dictionary

        Returns:
            Inserted document ID
        """
        if not self.enabled:
            return None

        try:
            signal['created_at'] = datetime.utcnow()
            result = self.db.signals.insert_one(signal)
            return str(result.inserted_id)

        except Exception as e:
            print(f"❌ Error saving signal: {e}")
            return None

    def get_signals(
        self,
        limit: int = 100,
        signal_type: str = None,
        symbol: str = None,
        min_strength: int = None,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get signals from database

        Args:
            limit: Maximum number of signals to return
            signal_type: Filter by 'LONG' or 'SHORT'
            symbol: Filter by symbol
            min_strength: Minimum signal strength
            hours: Get signals from last N hours

        Returns:
            List of signals
        """
        if not self.enabled:
            return []

        try:
            query = {}

            # Time filter
            if hours:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                query['created_at'] = {'$gte': cutoff}

            # Type filter
            if signal_type:
                query['type'] = signal_type.upper()

            # Symbol filter
            if symbol:
                query['symbol'] = symbol.upper()

            # Strength filter
            if min_strength:
                query['strength'] = {'$gte': min_strength}

            # Query
            cursor = self.db.signals.find(query).sort('created_at', DESCENDING).limit(limit)

            signals = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                if 'created_at' in doc:
                    doc['created_at'] = doc['created_at'].isoformat()
                signals.append(doc)

            return signals

        except Exception as e:
            print(f"❌ Error fetching signals: {e}")
            return []

    def get_signal_stats(self, hours: int = 24) -> Dict:
        """
        Get signal statistics

        Args:
            hours: Time period in hours

        Returns:
            Statistics dictionary
        """
        if not self.enabled:
            return {}

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            pipeline = [
                {'$match': {'created_at': {'$gte': cutoff}}},
                {'$group': {
                    '_id': None,
                    'total': {'$sum': 1},
                    'long_count': {'$sum': {'$cond': [{'$eq': ['$type', 'LONG']}, 1, 0]}},
                    'short_count': {'$sum': {'$cond': [{'$eq': ['$type', 'SHORT']}, 1, 0]}},
                    'avg_strength': {'$avg': '$strength'},
                    'max_strength': {'$max': '$strength'}
                }}
            ]

            result = list(self.db.signals.aggregate(pipeline))

            if result:
                stats = result[0]
                del stats['_id']
                stats['avg_strength'] = round(stats['avg_strength'], 1) if stats['avg_strength'] else 0
                return stats

            return {
                'total': 0,
                'long_count': 0,
                'short_count': 0,
                'avg_strength': 0,
                'max_strength': 0
            }

        except Exception as e:
            print(f"❌ Error fetching stats: {e}")
            return {}

    def get_settings(self) -> Dict:
        """
        Get bot settings from database

        Returns:
            Settings dictionary
        """
        if not self.enabled:
            return self._default_settings()

        try:
            settings = self.db.settings.find_one({'_id': 'bot_settings'})
            if settings:
                del settings['_id']
                return settings
            return self._default_settings()

        except Exception as e:
            print(f"❌ Error fetching settings: {e}")
            return self._default_settings()

    def update_settings(self, settings: Dict) -> bool:
        """
        Update bot settings

        Args:
            settings: New settings dictionary

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            settings['_id'] = 'bot_settings'
            settings['updated_at'] = datetime.utcnow()

            self.db.settings.replace_one(
                {'_id': 'bot_settings'},
                settings,
                upsert=True
            )
            return True

        except Exception as e:
            print(f"❌ Error updating settings: {e}")
            return False

    def _default_settings(self) -> Dict:
        """Return default settings"""
        return {
            'scan_interval': 5,  # minutes
            'min_signal_strength': 70,
            'timeframes': ['5m', '15m', '1h', '4h'],
            'markets': ['spot', 'futures'],
            'max_signals_per_scan': 10,
            'telegram_enabled': True,
            'top_coins_count': 50
        }

    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            print("📴 MongoDB connection closed")
