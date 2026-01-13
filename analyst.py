# monster_analyst.py
import asyncio
import aiohttp
import json
import logging
import time
from typing import Dict, Optional
from pydantic import BaseModel
import joblib
import numpy as np

# ---------------- إعدادات ----------------
LOG_LEVEL = logging.INFO
FETCH_TIMEOUT = 10
MODEL_PATH = "signal_model.joblib"  # النموذج الذي سينتجه train_model.py
FEATURE_ORDER = ["avg_trade","buy_ratio","whale_score","imbalance","volume_24h"]

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("monster_analyst")

class AlphaSignal(BaseModel):
    asset_symbol: str
    signal: str
    severity: str
    headline: str
    full_report: str
    whale_index: int

# compute_features كما في السابق
def compute_features(asset, pair_data, thresholds=None) -> Dict:
    try:
        txns = pair_data.get("txns", {}).get("h24", {}) if pair_data else {}
        buys = int(txns.get("buys", 0))
        sells = int(txns.get("sells", 0))
    except Exception:
        buys = sells = 0

    total_tx = max(0, buys + sells)
    buy_ratio = (buys / total_tx) * 100 if total_tx > 0 else 50.0
    volume_24h = float(getattr(asset, "volume_24h", 0) or 0)
    avg_trade = (volume_24h / total_tx) if total_tx > 0 else 0.0
    imbalance = buys - sells
    whale_score = min(100, int((avg_trade / max(1, (thresholds or {}).get("whale_trade_usd", 1000))) * 100))

    return {
        "buys": buys,
        "sells": sells,
        "total_tx": total_tx,
        "buy_ratio": buy_ratio,
        "avg_trade": avg_trade,
        "volume_24h": volume_24h,
        "imbalance": imbalance,
        "whale_score": whale_score
    }

# Dispatcher بسيط
class AlertDispatcher:
    def __init__(self):
        self.clients = set()
    async def register(self, websocket):
        self.clients.add(websocket)
    async def unregister(self, websocket):
        self.clients.discard(websocket)
    async def broadcast(self, message: dict):
        if not self.clients:
            return
        payload = json.dumps(message)
        coros = []
        for ws in list(self.clients):
            try:
                coros.append(ws.send(payload))
            except Exception:
                logger.exception("Queue send failed")
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

# المحلل مع دعم ML
class InstitutionalAnalyst:
    def __init__(self, model_path: Optional[str] = None, session: aiohttp.ClientSession = None):
        self._external_session = session
        self._own_session: Optional[aiohttp.ClientSession] = None
        self.dispatcher = AlertDispatcher()
        self.model = None
        self.scaler = None
        if model_path:
            try:
                self.model, self.scaler = joblib.load(model_path)
                logger.info("Loaded ML model from %s", model_path)
            except Exception:
                logger.exception("Failed to load model, falling back to rules")
                self.model = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._external_session:
            return self._external_session
        if not self._own_session or self._own_session.closed:
            self._own_session = aiohttp.ClientSession()
        return self._own_session

    async def close(self):
        if self._own_session and not self._own_session.closed:
            await self._own_session.close()

    async def fetch_pair(self, chain: str, pair_address: str) -> dict:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
        session = await self._get_session()
        try:
            async with session.get(url, timeout=FETCH_TIMEOUT) as resp:
                if resp.status != 200:
                    logger.warning("Non-200 response %s for %s", resp.status, url)
                    return {}
                try:
                    return await resp.json()
                except aiohttp.ContentTypeError:
                    text = await resp.text()
                    logger.error("Invalid JSON from %s: %s", url, text[:200])
                    return {}
        except Exception:
            logger.exception("Error fetching pair data")
            return {}

    def _predict_with_ml(self, features: Dict) -> Dict[str, float]:
        if not self.model or not self.scaler:
            return {}
        x = np.array([[features.get(f, 0) for f in FEATURE_ORDER]])
        try:
            x_s = self.scaler.transform(x)
        except Exception:
            # إذا لم يتم تهيئة scaler بشكل صحيح، نعيد القيم الخام بعد fit_transform
            try:
                x_s = self.scaler.fit_transform(x)
            except Exception:
                x_s = x
        probs = self.model.predict_proba(x_s)[0]
        classes = list(self.model.classes_)
        return dict(zip(classes, probs))

    def _rule_based(self, features: Dict) -> Dict[str, float]:
        # قواعد احتياطية بسيطة
        avg_trade = features.get("avg_trade", 0)
        buy_ratio = features.get("buy_ratio", 50)
        whale_score = features.get("whale_score", 0)
        score_buy = 0.0
        score_sell = 0.0
        if avg_trade > 1000 and buy_ratio > 55:
            score_buy += 0.8 + (whale_score / 500)
        if avg_trade < 100 and buy_ratio > 60:
            score_buy += 0.4
        if buy_ratio < 40:
            score_sell += 0.9
        neutral = max(0.0, 1.0 - (score_buy + score_sell))
        total = score_buy + score_sell + neutral
        if total == 0:
            return {"BUY":0.0,"SELL":0.0,"NEUTRAL":1.0}
        return {"BUY":score_buy/total,"SELL":score_sell/total,"NEUTRAL":neutral/total}

    async def analyze_asset(self, asset) -> AlphaSignal:
        start_ts = time.time()
        symbol = getattr(asset, "symbol", "UNKNOWN")
        logger.info("Analyze %s", symbol)

        if not getattr(asset, "pair_address", None) or not getattr(asset, "chain", None):
            return AlphaSignal(asset_symbol=symbol, signal="ERROR", severity="LOW",
                               headline="Missing pair/chain", full_report="Missing pair_address or chain", whale_index=0)

        data = await self.fetch_pair(asset.chain, asset.pair_address)
        pair = None
        if data:
            pairs = data.get("pairs") or []
            if pairs:
                pair = pairs[0]

        features = compute_features(asset, pair or {})
        logger.debug("Features: %s", features)

        probs = {}
        # حاول ML أولاً ثم القواعد كاحتياط
        if self.model and self.scaler:
            try:
                probs = self._predict_with_ml(features)
            except Exception:
                logger.exception("ML prediction failed, falling back to rules")
                probs = self._rule_based(features)
        else:
            probs = self._rule_based(features)

        logger.info("Probs: %s", probs)
        best_signal = max(probs.items(), key=lambda x: x[1])[0]
        confidence = float(probs.get(best_signal, 0.0))

        whale_index = int(features.get("whale_score", 0))
        if confidence > 0.75 or whale_index > 70:
            severity = "HIGH"
        elif confidence > 0.5:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        headline = f"{best_signal} (conf {confidence:.2f}) avg ${features.get('avg_trade',0):.0f}"
        full_report = (
            f"Order flow analysis for {symbol}:\n"
            f"- Buys: {features['buys']} Sells: {features['sells']}\n"
            f"- Buy ratio: {features['buy_ratio']:.1f}%\n"
            f"- Avg trade: ${features['avg_trade']:.2f}\n"
            f"- Whale index: {whale_index}\n"
            f"- Latency: {time.time()-start_ts:.2f}s\n"
        )

        signal_obj = AlphaSignal(
            asset_symbol=symbol,
            signal=best_signal,
            severity=severity,
            headline=headline,
            full_report=full_report,
            whale_index=whale_index
        )

        # بث التنبيه
        try:
            asyncio.create_task(self.dispatcher.broadcast({
                "asset": symbol,
                "signal": best_signal,
                "confidence": confidence,
                "severity": severity,
                "headline": headline,
                "features": features,
                "ts": int(time.time())
            }))
        except Exception:
            logger.exception("Broadcast scheduling failed")

        return signal_obj

# مثال تشغيل سريع
if __name__ == "__main__":
    class DummyAsset:
        def __init__(self, symbol, chain, pair_address, volume_24h):
            self.symbol = symbol
            self.chain = chain
            self.pair_address = pair_address
            self.volume_24h = volume_24h

    async def demo():
        analyst = InstitutionalAnalyst(model_path=MODEL_PATH)
        asset = DummyAsset("TEST", "solana", "0xdeadbeef", 250000)
        sig = await analyst.analyze_asset(asset)
        print(sig.json(indent=2))
        await analyst.close()

    asyncio.run(demo())
