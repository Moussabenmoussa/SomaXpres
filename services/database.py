def _default_settings(self) -> Dict:
    return {
        'scan_interval': 5,          # دقائق
        'min_signal_strength': 70,   # الحد الأدنى
        'timeframes': ['5m', '15m', '1h', '4h'],
        'markets': ['spot', 'futures'],
        'top_coins_count': 50
    }
