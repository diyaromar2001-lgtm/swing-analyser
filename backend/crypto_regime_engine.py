"""
Scope: CRYPTO
"""

from __future__ import annotations

import time as _time
from typing import Dict, List

import numpy as np

from crypto_data import (
    get_crypto_global_metrics,
    get_crypto_market_snapshots,
    get_crypto_ohlcv,
)
from crypto_universe import CRYPTO_SYMBOLS
from indicators import sma, rsi, atr

_cache: Dict[str, object] = {}
_CACHE_TTL = 3600
_last_regime_update_ts: float = 0.0


def _empty(error: str = "Crypto regime unavailable") -> Dict:
    return {
        "crypto_regime": "CRYPTO_NO_TRADE",
        "regime_label": "No Trade",
        "active_crypto_strategies": [],
        "active_strategy": "NO_TRADE",
        "confidence": 0,
        "reasons": [error],
        "risk_status": "HIGH",
        "data_status": "MISSING",
        "btc_price": 0.0,
        "btc_sma50": 0.0,
        "btc_sma200": 0.0,
        "btc_rsi": 0.0,
        "eth_price": 0.0,
        "eth_sma50": 0.0,
        "eth_sma200": 0.0,
        "eth_rsi": 0.0,
        "btc_dominance": 0.0,
        "total_market_cap": 0.0,
        "breadth_pct": 0.0,
        "momentum_30d": 0.0,
        "volatility_btc": 0.0,
    }


def invalidate_cache() -> None:
    global _last_regime_update_ts
    _cache.clear()
    _last_regime_update_ts = 0.0


def compute_crypto_regime(fast: bool = False) -> Dict:
    global _last_regime_update_ts
    now = _time.time()
    cached = _cache.get("data")
    cached_age = now - _cache.get("ts", 0) if _cache else None
    if _cache and ((cached_age is not None and cached_age < _CACHE_TTL) or fast):
        if not fast and isinstance(cached, dict) and cached.get("data_status") == "MISSING":
            pass
        else:
            return _cache["data"]  # type: ignore[index]
    if fast and not _cache:
        return _empty("Crypto regime cache unavailable in fast mode")

    btc_df = get_crypto_ohlcv("BTC", "1d", allow_download=not fast)
    eth_df = get_crypto_ohlcv("ETH", "1d", allow_download=not fast)
    if btc_df is None or eth_df is None or len(btc_df) < 220 or len(eth_df) < 220:
        data = _empty("BTC/ETH history insufficient")
        _cache.update({"ts": now, "data": data})
        _last_regime_update_ts = now
        return data

    btc_close = btc_df["Close"]
    eth_close = eth_df["Close"]

    btc_price = float(btc_close.iloc[-1])
    eth_price = float(eth_close.iloc[-1])
    btc_sma50 = float(sma(btc_close, 50).iloc[-1])
    btc_sma200 = float(sma(btc_close, 200).iloc[-1])
    eth_sma50 = float(sma(eth_close, 50).iloc[-1])
    eth_sma200 = float(sma(eth_close, 200).iloc[-1])
    btc_rsi = float(rsi(btc_close, 14).iloc[-1])
    eth_rsi = float(rsi(eth_close, 14).iloc[-1])
    btc_volatility = float(atr(btc_df["High"], btc_df["Low"], btc_close, 14).iloc[-1] / btc_price * 100)

    breadth_count = 0
    breadth_total = 0
    perf_30d: List[float] = []
    for symbol in CRYPTO_SYMBOLS:
        df = get_crypto_ohlcv(symbol, "1d", allow_download=not fast)
        if df is None or len(df) < 220:
            continue
        close = df["Close"]
        price = float(close.iloc[-1])
        sma50_v = float(sma(close, 50).iloc[-1])
        sma200_v = float(sma(close, 200).iloc[-1])
        breadth_total += 1
        if price > sma50_v and price > sma200_v:
            breadth_count += 1
        if len(close) >= 31:
            perf_30d.append((price / float(close.iloc[-31]) - 1.0) * 100.0)

    breadth_pct = round((breadth_count / max(breadth_total, 1)) * 100.0, 1)
    momentum_30d = round(float(np.mean(perf_30d)) if perf_30d else 0.0, 2)
    global_metrics = get_crypto_global_metrics(allow_download=not fast)
    btc_dom = float(global_metrics.get("btc_dominance", 0.0))
    total_mcap = float(global_metrics.get("total_market_cap", 0.0))
    market_cap_change = float(global_metrics.get("market_cap_change_24h", 0.0))

    regime = "CRYPTO_RANGE"
    label = "Crypto Range"
    active = ["MEAN_REVERSION_RANGE"]
    active_strategy = "MEAN_REVERSION"
    risk_status = "MEDIUM"
    confidence = 55
    reasons: List[str] = []

    btc_bull = btc_price > btc_sma50 > btc_sma200
    eth_bull = eth_price > eth_sma50 > eth_sma200
    btc_bear = btc_price < btc_sma200
    eth_bear = eth_price < eth_sma200

    if btc_bear and eth_bear:
        regime = "CRYPTO_NO_TRADE" if btc_volatility > 7.0 else "CRYPTO_BEAR"
        label = "Crypto Bear" if regime == "CRYPTO_BEAR" else "Crypto No Trade"
        active = []
        active_strategy = "NO_TRADE"
        risk_status = "HIGH"
        confidence = 88
        reasons = ["BTC sous SMA200", "ETH sous SMA200", "Régime défensif crypto"]
    elif btc_volatility > 8.0 or market_cap_change <= -8.0:
        regime = "CRYPTO_HIGH_VOLATILITY"
        label = "High Volatility"
        active = []
        active_strategy = "NO_TRADE"
        risk_status = "HIGH"
        confidence = 84
        reasons = [f"Volatilité BTC élevée ({btc_volatility:.1f}%)", "Risque de whipsaw élevé"]
    elif btc_bull and eth_bull and breadth_pct >= 55 and momentum_30d > 4:
        regime = "CRYPTO_BULL"
        label = "Crypto Bull"
        active = [
            "BTC_ETH_TREND_BREAKOUT",
            "PULLBACK_UPTREND",
            "MOMENTUM_RELATIVE_STRENGTH",
            "BTC_LEADER_ROTATION",
        ]
        active_strategy = "BREAKOUT"
        risk_status = "LOW"
        confidence = min(96, int(60 + breadth_pct * 0.35))
        reasons = ["BTC et ETH en double uptrend", f"Breadth positive ({breadth_pct:.1f}%)", "Momentum global crypto positif"]
    elif btc_price > btc_sma200 and abs(btc_price - btc_sma50) / max(btc_sma50, 1) < 0.04:
        regime = "CRYPTO_PULLBACK"
        label = "Crypto Pullback"
        active = ["PULLBACK_UPTREND", "BTC_LEADER_ROTATION"]
        active_strategy = "PULLBACK"
        risk_status = "MEDIUM"
        confidence = 72
        reasons = ["BTC au-dessus SMA200", "Retour proche SMA50", "Setup de repli potentiel"]
    elif breadth_pct < 42 or momentum_30d < -2:
        regime = "CRYPTO_BEAR"
        label = "Crypto Bear"
        active = []
        active_strategy = "NO_TRADE"
        risk_status = "HIGH"
        confidence = 73
        reasons = ["Breadth détériorée", "Momentum moyen crypto négatif"]
    else:
        reasons = ["Tendance crypto mitigée", "Privilégier sélectivité maximale"]

    data = {
        "crypto_regime": regime,
        "regime_label": label,
        "active_crypto_strategies": active,
        "active_strategy": active_strategy,
        "confidence": confidence,
        "reasons": reasons,
        "risk_status": risk_status,
        "data_status": "OK",
        "btc_price": round(btc_price, 2),
        "btc_sma50": round(btc_sma50, 2),
        "btc_sma200": round(btc_sma200, 2),
        "btc_rsi": round(btc_rsi, 1),
        "eth_price": round(eth_price, 2),
        "eth_sma50": round(eth_sma50, 2),
        "eth_sma200": round(eth_sma200, 2),
        "eth_rsi": round(eth_rsi, 1),
        "btc_dominance": round(btc_dom, 2),
        "total_market_cap": round(total_mcap, 2),
        "breadth_pct": breadth_pct,
        "momentum_30d": momentum_30d,
        "volatility_btc": round(btc_volatility, 2),
    }
    _cache.update({"ts": now, "data": data})
    _last_regime_update_ts = now
    return data
