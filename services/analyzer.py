"""
📊 Technical Analyzer
Advanced technical analysis for crypto trading signals
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import ta
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator

class TechnicalAnalyzer:
    """Advanced technical analysis engine"""

    def __init__(self):
        """Initialize analyzer with default settings"""
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
        self.ema_short = 9
        self.ema_medium = 21
        self.ema_long = 50
        self.ema_trend = 200

    def prepare_dataframe(self, ohlcv: List[Dict]) -> pd.DataFrame:
        """Convert OHLCV list to pandas DataFrame"""
        df = pd.DataFrame(ohlcv)
        df.set_index('timestamp', inplace=True)
        return df

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""

        # RSI
        rsi = RSIIndicator(close=df['close'], window=self.rsi_period)
        df['rsi'] = rsi.rsi()

        # MACD
        macd = MACD(
            close=df['close'],
            window_slow=self.macd_slow,
            window_fast=self.macd_fast,
            window_sign=self.macd_signal
        )
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()

        # EMAs
        df['ema_9'] = EMAIndicator(close=df['close'], window=self.ema_short).ema_indicator()
        df['ema_21'] = EMAIndicator(close=df['close'], window=self.ema_medium).ema_indicator()
        df['ema_50'] = EMAIndicator(close=df['close'], window=self.ema_long).ema_indicator()
        df['ema_200'] = EMAIndicator(close=df['close'], window=self.ema_trend).ema_indicator()

        # Bollinger Bands
        bb = BollingerBands(close=df['close'], window=self.bb_period, window_dev=self.bb_std)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # Stochastic
        stoch = StochasticOscillator(high=df['high'], low=df['low'], close=df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()

        # ATR (for stop loss calculation)
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'])
        df['atr'] = atr.average_true_range()

        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        # OBV
        obv = OnBalanceVolumeIndicator(close=df['close'], volume=df['volume'])
        df['obv'] = obv.on_balance_volume()

        # Support and Resistance (simplified)
        df['resistance'] = df['high'].rolling(window=20).max()
        df['support'] = df['low'].rolling(window=20).min()

        return df

    def detect_candlestick_patterns(self, df: pd.DataFrame) -> Dict:
        """Detect candlestick patterns"""
        patterns = {}

        # Get last 3 candles
        if len(df) < 3:
            return patterns

        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]

        body = last['close'] - last['open']
        body_size = abs(body)
        candle_range = last['high'] - last['low']

        # Doji
        if candle_range > 0 and body_size / candle_range < 0.1:
            patterns['doji'] = True

        # Hammer (bullish)
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        if candle_range > 0:
            if lower_wick > body_size * 2 and upper_wick < body_size * 0.5:
                patterns['hammer'] = True

        # Shooting Star (bearish)
        if candle_range > 0:
            if upper_wick > body_size * 2 and lower_wick < body_size * 0.5:
                patterns['shooting_star'] = True

        # Engulfing patterns
        prev_body = prev['close'] - prev['open']
        if body > 0 and prev_body < 0:  # Bullish engulfing
            if last['open'] < prev['close'] and last['close'] > prev['open']:
                patterns['bullish_engulfing'] = True
        elif body < 0 and prev_body > 0:  # Bearish engulfing
            if last['open'] > prev['close'] and last['close'] < prev['open']:
                patterns['bearish_engulfing'] = True

        return patterns

    def calculate_signal_strength(self, indicators: Dict) -> int:
        """
        Calculate overall signal strength (0-100)

        Args:
            indicators: Dictionary of indicator values

        Returns:
            Signal strength percentage
        """
        score = 50  # Start neutral

        # RSI contribution (-15 to +15)
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            score += 15  # Oversold = bullish
        elif rsi < 40:
            score += 8
        elif rsi > 70:
            score -= 15  # Overbought = bearish
        elif rsi > 60:
            score -= 8

        # MACD contribution (-15 to +15)
        macd_hist = indicators.get('macd_histogram', 0)
        macd_cross = indicators.get('macd_cross', 'none')
        if macd_cross == 'bullish':
            score += 15
        elif macd_cross == 'bearish':
            score -= 15
        elif macd_hist > 0:
            score += 5
        else:
            score -= 5

        # EMA contribution (-15 to +15)
        ema_trend = indicators.get('ema_trend', 'neutral')
        if ema_trend == 'strong_bullish':
            score += 15
        elif ema_trend == 'bullish':
            score += 8
        elif ema_trend == 'strong_bearish':
            score -= 15
        elif ema_trend == 'bearish':
            score -= 8

        # Bollinger Bands contribution (-10 to +10)
        bb_position = indicators.get('bb_position', 'middle')
        if bb_position == 'lower':
            score += 10  # Near lower band = potential bounce
        elif bb_position == 'upper':
            score -= 10  # Near upper band = potential reversal

        # Volume contribution (-10 to +10)
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 2:
            score += 10 if indicators.get('price_direction', 0) > 0 else -10
        elif volume_ratio > 1.5:
            score += 5 if indicators.get('price_direction', 0) > 0 else -5

        # Candlestick patterns (-10 to +10)
        patterns = indicators.get('patterns', {})
        if patterns.get('bullish_engulfing') or patterns.get('hammer'):
            score += 10
        if patterns.get('bearish_engulfing') or patterns.get('shooting_star'):
            score -= 10

        # Clamp to 0-100
        return max(0, min(100, score))

    def analyze(self, ohlcv: List[Dict], symbol: str, timeframe: str) -> Dict:
        """
        Perform complete technical analysis

        Args:
            ohlcv: OHLCV data
            symbol: Trading pair symbol
            timeframe: Candle timeframe

        Returns:
            Complete analysis with signal and targets
        """
        if not ohlcv or len(ohlcv) < 50:
            return {'error': 'Insufficient data'}

        # Prepare data
        df = self.prepare_dataframe(ohlcv)
        df = self.calculate_indicators(df)

        # Get latest values
        last = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = last['close']
        atr = last['atr']

        # Detect MACD crossover
        macd_cross = 'none'
        if last['macd'] > last['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            macd_cross = 'bullish'
        elif last['macd'] < last['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            macd_cross = 'bearish'

        # Determine EMA trend
        ema_trend = 'neutral'
        if last['ema_9'] > last['ema_21'] > last['ema_50'] > last['ema_200']:
            ema_trend = 'strong_bullish'
        elif last['ema_9'] > last['ema_21'] > last['ema_50']:
            ema_trend = 'bullish'
        elif last['ema_9'] < last['ema_21'] < last['ema_50'] < last['ema_200']:
            ema_trend = 'strong_bearish'
        elif last['ema_9'] < last['ema_21'] < last['ema_50']:
            ema_trend = 'bearish'

        # Bollinger Band position
        bb_position = 'middle'
        if current_price <= last['bb_lower']:
            bb_position = 'lower'
        elif current_price >= last['bb_upper']:
            bb_position = 'upper'

        # Price direction
        price_direction = 1 if current_price > prev['close'] else -1

        # Detect patterns
        patterns = self.detect_candlestick_patterns(df)

        # Build indicators dict
        indicators = {
            'rsi': round(last['rsi'], 2),
            'macd': round(last['macd'], 6),
            'macd_signal': round(last['macd_signal'], 6),
            'macd_histogram': round(last['macd_histogram'], 6),
            'macd_cross': macd_cross,
            'ema_9': round(last['ema_9'], 2),
            'ema_21': round(last['ema_21'], 2),
            'ema_50': round(last['ema_50'], 2),
            'ema_200': round(last['ema_200'], 2),
            'ema_trend': ema_trend,
            'bb_upper': round(last['bb_upper'], 2),
            'bb_middle': round(last['bb_middle'], 2),
            'bb_lower': round(last['bb_lower'], 2),
            'bb_position': bb_position,
            'stoch_k': round(last['stoch_k'], 2),
            'stoch_d': round(last['stoch_d'], 2),
            'atr': round(atr, 4),
            'volume_ratio': round(last['volume_ratio'], 2),
            'support': round(last['support'], 2),
            'resistance': round(last['resistance'], 2),
            'price_direction': price_direction,
            'patterns': patterns
        }

        # Calculate signal strength
        strength = self.calculate_signal_strength(indicators)

        # Determine signal type
        if strength >= 65:
            signal = 'LONG'
        elif strength <= 35:
            signal = 'SHORT'
        else:
            signal = 'NEUTRAL'

        # Calculate entry, stop loss, and take profits
        if signal == 'LONG':
            entry = current_price
            stop_loss = round(current_price - (atr * 1.5), 4)
            tp1 = round(current_price + (atr * 1), 4)
            tp2 = round(current_price + (atr * 2), 4)
            tp3 = round(current_price + (atr * 3), 4)
            sl_percent = round((entry - stop_loss) / entry * 100, 2)
            tp1_percent = round((tp1 - entry) / entry * 100, 2)
            tp2_percent = round((tp2 - entry) / entry * 100, 2)
            risk_reward = round(tp2_percent / sl_percent, 2) if sl_percent > 0 else 0

        elif signal == 'SHORT':
            entry = current_price
            stop_loss = round(current_price + (atr * 1.5), 4)
            tp1 = round(current_price - (atr * 1), 4)
            tp2 = round(current_price - (atr * 2), 4)
            tp3 = round(current_price - (atr * 3), 4)
            sl_percent = round((stop_loss - entry) / entry * 100, 2)
            tp1_percent = round((entry - tp1) / entry * 100, 2)
            tp2_percent = round((entry - tp2) / entry * 100, 2)
            risk_reward = round(tp2_percent / sl_percent, 2) if sl_percent > 0 else 0

        else:
            entry = current_price
            stop_loss = 0
            tp1 = tp2 = tp3 = 0
            sl_percent = tp1_percent = tp2_percent = 0
            risk_reward = 0

        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'current_price': round(current_price, 4),
            'signal': signal,
            'strength': strength,
            'entry': entry,
            'stop_loss': stop_loss,
            'stop_loss_percent': sl_percent,
            'take_profit_1': tp1,
            'take_profit_1_percent': tp1_percent,
            'take_profit_2': tp2,
            'take_profit_2_percent': tp2_percent,
            'take_profit_3': tp3,
            'risk_reward': risk_reward,
            'indicators': indicators
        }
