"""
Scope: CRYPTO

Sources:
- Binance public REST pour OHLCV + ticker 24h
- CoinGecko pour market cap / dominance / variation
"""

from __future__ import annotations

import time as _time
from typing import Dict, List, Optional

import httpx
import pandas as pd

from crypto_universe import CRYPTO_BY_SYMBOL, CRYPTO_SYMBOLS, CRYPTO_UNIVERSE

BINANCE_BASE = "https://api.binance.com"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

_price_cache: Dict[str, dict] = {}
_ohlcv_daily_cache: Dict[str, dict] = {}
_ohlcv_4h_cache: Dict[str, dict] = {}
_markets_cache: dict = {}
_global_cache: dict = {}
_last_price_update_ts: float = 0.0
_last_daily_update_ts: float = 0.0
_last_h4_update_ts: float = 0.0
_last_market_update_ts: float = 0.0
_last_global_update_ts: float = 0.0

PRICE_TTL = 60
OHLCV_4H_TTL = 900
OHLCV_DAILY_TTL = 3600
MARKETS_TTL = 300
GLOBAL_TTL = 900


def _client() -> httpx.Client:
    return httpx.Client(timeout=15, headers={"User-Agent": "swing-analyser-crypto/1.0"})


def _normalize_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s == "MATIC":
        return "POL"
    return s


def _binance_pair(symbol: str) -> str:
    meta = CRYPTO_BY_SYMBOL.get(_normalize_symbol(symbol))
    return meta["pair"] if meta else f"{_normalize_symbol(symbol)}USDT"


def _coingecko_id(symbol: str) -> Optional[str]:
    meta = CRYPTO_BY_SYMBOL.get(_normalize_symbol(symbol))
    return meta.get("coingecko_id") if meta else None


def _fetch_binance_klines(pair: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    try:
        with _client() as client:
            r = client.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": pair, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            raw = r.json()
        if not raw:
            return None
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time", "Open", "High", "Low", "Close", "Volume",
                "close_time", "quote_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ],
        )
        for col in ["Open", "High", "Low", "Close", "Volume", "quote_volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume", "quote_volume"]]
        return df.dropna()
    except Exception:
        return None


def get_crypto_ohlcv(symbol: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    global _last_daily_update_ts, _last_h4_update_ts
    sym = _normalize_symbol(symbol)
    pair = _binance_pair(sym)
    now = _time.time()
    if timeframe == "4h":
        entry = _ohlcv_4h_cache.get(sym)
        if entry and (now - entry["ts"]) < OHLCV_4H_TTL:
            return entry["df"]
        df = _fetch_binance_klines(pair, "4h", 500)
        if df is not None and len(df) >= 120:
            _ohlcv_4h_cache[sym] = {"df": df, "ts": now}
            _last_h4_update_ts = now
        return df

    entry = _ohlcv_daily_cache.get(sym)
    if entry and (now - entry["ts"]) < OHLCV_DAILY_TTL:
        return entry["df"]
    df = _fetch_binance_klines(pair, "1d", 500)
    if df is not None and len(df) >= 220:
        _ohlcv_daily_cache[sym] = {"df": df, "ts": now}
        _last_daily_update_ts = now
    return df


def get_crypto_price_snapshot(symbol: str) -> Optional[Dict]:
    global _last_price_update_ts
    sym = _normalize_symbol(symbol)
    now = _time.time()
    entry = _price_cache.get(sym)
    if entry and (now - entry["ts"]) < PRICE_TTL:
        return entry

    pair = _binance_pair(sym)
    try:
        with _client() as client:
            r = client.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": pair})
            r.raise_for_status()
            data = r.json()
        price = float(data["lastPrice"])
        out = {
            "symbol": sym,
            "price": round(price, 4 if price < 10 else 2),
            "change_pct": round(float(data.get("priceChangePercent", 0.0)), 2),
            "change_abs": round(float(data.get("priceChange", 0.0)), 4 if price < 10 else 2),
            "volume_24h": float(data.get("quoteVolume", 0.0)),
            "trades_24h": int(data.get("count", 0)),
            "ts": now,
        }
        _price_cache[sym] = out
        _last_price_update_ts = now
        return out
    except Exception:
        return None


def get_crypto_market_snapshots() -> Dict[str, Dict]:
    global _last_market_update_ts
    now = _time.time()
    if _markets_cache and (now - _markets_cache.get("ts", 0)) < MARKETS_TTL:
        return _markets_cache["data"]

    ids = ",".join(
        filter(None, (_coingecko_id(symbol) for symbol in CRYPTO_SYMBOLS))
    )
    try:
        with _client() as client:
            r = client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ids,
                    "price_change_percentage": "24h,7d,30d",
                    "per_page": 250,
                    "page": 1,
                },
            )
            r.raise_for_status()
            raw = r.json()
        by_id = {item["id"]: item for item in raw}
        out: Dict[str, Dict] = {}
        for symbol in CRYPTO_SYMBOLS:
            cg_id = _coingecko_id(symbol)
            item = by_id.get(cg_id or "")
            if not item:
                continue
            out[symbol] = {
                "market_cap": float(item.get("market_cap") or 0.0),
                "market_cap_rank": item.get("market_cap_rank"),
                "volume_24h": float(item.get("total_volume") or 0.0),
                "change_24h": float(item.get("price_change_percentage_24h_in_currency") or 0.0),
                "change_7d": float(item.get("price_change_percentage_7d_in_currency") or 0.0),
                "change_30d": float(item.get("price_change_percentage_30d_in_currency") or 0.0),
                "liquidity_score": float(item.get("liquidity_score") or 0.0),
                "image": item.get("image"),
            }
        _markets_cache.update({"ts": now, "data": out})
        _last_market_update_ts = now
        return out
    except Exception:
        return _markets_cache.get("data", {})


def get_crypto_global_metrics() -> Dict:
    global _last_global_update_ts
    now = _time.time()
    if _global_cache and (now - _global_cache.get("ts", 0)) < GLOBAL_TTL:
        return _global_cache["data"]

    try:
        with _client() as client:
            r = client.get(f"{COINGECKO_BASE}/global")
            r.raise_for_status()
            payload = r.json().get("data", {})
        out = {
            "btc_dominance": float(payload.get("market_cap_percentage", {}).get("btc", 0.0)),
            "eth_dominance": float(payload.get("market_cap_percentage", {}).get("eth", 0.0)),
            "total_market_cap": float(payload.get("total_market_cap", {}).get("usd", 0.0)),
            "total_volume": float(payload.get("total_volume", {}).get("usd", 0.0)),
            "market_cap_change_24h": float(payload.get("market_cap_change_percentage_24h_usd", 0.0)),
            "active_cryptocurrencies": int(payload.get("active_cryptocurrencies", 0)),
        }
        _global_cache.update({"ts": now, "data": out})
        _last_global_update_ts = now
        return out
    except Exception:
        return _global_cache.get("data", {})


def get_crypto_data_freshness() -> Dict[str, Optional[float]]:
    daily_ts = max((v.get("ts", 0) for v in _ohlcv_daily_cache.values()), default=0)
    h4_ts = max((v.get("ts", 0) for v in _ohlcv_4h_cache.values()), default=0)
    price_ts = max((v.get("ts", 0) for v in _price_cache.values()), default=0)
    market_ts = _markets_cache.get("ts", 0)
    global_ts = _global_cache.get("ts", 0)
    return {
        "price_ts": _last_price_update_ts or price_ts,
        "daily_ts": _last_daily_update_ts or daily_ts,
        "h4_ts": _last_h4_update_ts or h4_ts,
        "market_ts": _last_market_update_ts or market_ts,
        "global_ts": _last_global_update_ts or global_ts,
    }


def clear_crypto_caches() -> None:
    global _last_price_update_ts, _last_daily_update_ts, _last_h4_update_ts, _last_market_update_ts, _last_global_update_ts
    _price_cache.clear()
    _ohlcv_daily_cache.clear()
    _ohlcv_4h_cache.clear()
    _markets_cache.clear()
    _global_cache.clear()
    _last_price_update_ts = 0.0
    _last_daily_update_ts = 0.0
    _last_h4_update_ts = 0.0
    _last_market_update_ts = 0.0
    _last_global_update_ts = 0.0


def available_crypto_symbols() -> List[str]:
    return list(CRYPTO_SYMBOLS)


def crypto_sector(symbol: str) -> str:
    meta = CRYPTO_BY_SYMBOL.get(_normalize_symbol(symbol), {})
    return meta.get("sector", "Crypto")
