"""
Scope: CRYPTO

Sources:
- Binance public REST pour OHLCV + ticker 24h
- CoinGecko pour market cap / dominance / variation + fallback prix / OHLC
- yfinance comme fallback robuste final
"""

from __future__ import annotations

import time as _time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import pandas as pd
import yfinance as yf

from crypto_universe import CRYPTO_BY_SYMBOL, CRYPTO_SYMBOLS

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


def _log_source_event(
    level: str,
    source: str,
    symbol: str,
    action: str,
    ms: float,
    message: str,
    *,
    url: Optional[str] = None,
    rows: Optional[int] = None,
) -> None:
    row_info = f" rows={rows}" if rows is not None else ""
    url_info = f" url={url}" if url else ""
    print(
        f"[crypto-data][{level}][{source}] symbol={symbol} action={action} "
        f"ms={ms:.1f}{row_info}{url_info} msg={message}"
    )


def _normalize_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s == "MATIC":
        return "POL"
    return s


def _meta(symbol: str) -> Dict[str, str]:
    return CRYPTO_BY_SYMBOL.get(_normalize_symbol(symbol), {})


def _binance_pair(symbol: str) -> str:
    meta = _meta(symbol)
    return meta.get("pair") or f"{_normalize_symbol(symbol)}USDT"


def _coingecko_id(symbol: str) -> Optional[str]:
    return _meta(symbol).get("coingecko_id")


def _yahoo_symbol(symbol: str) -> str:
    meta = _meta(symbol)
    return meta.get("yahoo_symbol") or f"{_normalize_symbol(symbol)}-USD"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _fetch_binance_klines(pair: str, interval: str, limit: int, symbol: str) -> Optional[pd.DataFrame]:
    url = f"{BINANCE_BASE}/api/v3/klines"
    started = _time.perf_counter()
    try:
        with _client() as client:
            r = client.get(url, params={"symbol": pair, "interval": interval, "limit": limit})
            r.raise_for_status()
            raw = r.json()
        if not raw:
            ms = (_time.perf_counter() - started) * 1000
            _log_source_event("FAIL", "binance", symbol, f"ohlcv_{interval}", ms, "empty response", url=url, rows=0)
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
        df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume", "quote_volume"]].dropna()
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "binance", symbol, f"ohlcv_{interval}", ms, "success", url=url, rows=len(df))
        return df
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "binance", symbol, f"ohlcv_{interval}", ms, f"{type(exc).__name__}: {exc}", url=url, rows=0)
        return None


def _fetch_coingecko_ohlcv(symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
    cg_id = _coingecko_id(symbol)
    if not cg_id:
        return None
    started = _time.perf_counter()
    ohlc_url = f"{COINGECKO_BASE}/coins/{cg_id}/ohlc"
    market_url = f"{COINGECKO_BASE}/coins/{cg_id}/market_chart"
    try:
        with _client() as client:
            ohlc_resp = client.get(ohlc_url, params={"vs_currency": "usd", "days": days})
            ohlc_resp.raise_for_status()
            ohlc_raw = ohlc_resp.json()
            chart_resp = client.get(market_url, params={"vs_currency": "usd", "days": days, "interval": "daily"})
            chart_resp.raise_for_status()
            chart_raw = chart_resp.json()
        if not ohlc_raw:
            ms = (_time.perf_counter() - started) * 1000
            _log_source_event("FAIL", "coingecko", symbol, "ohlcv_daily", ms, "empty OHLC response", url=ohlc_url, rows=0)
            return None

        ohlc_df = pd.DataFrame(ohlc_raw, columns=["ts", "Open", "High", "Low", "Close"])
        ohlc_df["Date"] = pd.to_datetime(ohlc_df["ts"], unit="ms", utc=True)
        ohlc_df = ohlc_df.set_index("Date")[["Open", "High", "Low", "Close"]]
        volume_map = {}
        for ts, vol in chart_raw.get("total_volumes", []):
            key = pd.to_datetime(ts, unit="ms", utc=True).floor("D")
            volume_map[key] = _safe_float(vol)
        ohlc_df["Volume"] = [volume_map.get(idx.floor("D"), 0.0) for idx in ohlc_df.index]
        ohlc_df["quote_volume"] = ohlc_df["Volume"]
        ohlc_df = ohlc_df.dropna()
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "coingecko", symbol, "ohlcv_daily", ms, "success", url=ohlc_url, rows=len(ohlc_df))
        return ohlc_df
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "coingecko", symbol, "ohlcv_daily", ms, f"{type(exc).__name__}: {exc}", url=ohlc_url, rows=0)
        return None


def _fetch_yfinance_ohlcv(symbol: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    ticker = _yahoo_symbol(symbol)
    started = _time.perf_counter()
    try:
        kwargs = {
            "progress": False,
            "auto_adjust": False,
            "threads": False,
        }
        if timeframe == "4h":
            raw = yf.download(ticker, period="60d", interval="1h", **kwargs)
            if raw is None or raw.empty:
                ms = (_time.perf_counter() - started) * 1000
                _log_source_event("FAIL", "yfinance", symbol, "ohlcv_4h", ms, "empty response", url=ticker, rows=0)
                return None
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]].dropna()
            df.index = pd.to_datetime(df.index, utc=True)
            df = df.resample("4h").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }).dropna()
            df["quote_volume"] = df["Volume"]
        else:
            raw = yf.download(ticker, period="730d", interval="1d", **kwargs)
            if raw is None or raw.empty:
                ms = (_time.perf_counter() - started) * 1000
                _log_source_event("FAIL", "yfinance", symbol, "ohlcv_daily", ms, "empty response", url=ticker, rows=0)
                return None
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]].dropna()
            df.index = pd.to_datetime(df.index, utc=True)
            df["quote_volume"] = df["Volume"]
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "yfinance", symbol, f"ohlcv_{timeframe}", ms, "success", url=ticker, rows=len(df))
        return df
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "yfinance", symbol, f"ohlcv_{timeframe}", ms, f"{type(exc).__name__}: {exc}", url=ticker, rows=0)
        return None


def _fetch_binance_price(symbol: str) -> Optional[Dict]:
    pair = _binance_pair(symbol)
    url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    started = _time.perf_counter()
    try:
        with _client() as client:
            r = client.get(url, params={"symbol": pair})
            r.raise_for_status()
            data = r.json()
        price = float(data["lastPrice"])
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "binance", symbol, "price", ms, "success", url=url)
        return {
            "symbol": symbol,
            "price": round(price, 4 if price < 10 else 2),
            "change_pct": round(_safe_float(data.get("priceChangePercent")), 2),
            "change_abs": round(_safe_float(data.get("priceChange")), 4 if price < 10 else 2),
            "volume_24h": _safe_float(data.get("quoteVolume")),
            "trades_24h": int(_safe_float(data.get("count"))),
            "source": "binance",
        }
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "binance", symbol, "price", ms, f"{type(exc).__name__}: {exc}", url=url)
        return None


def _fetch_coingecko_price(symbol: str) -> Optional[Dict]:
    cg_id = _coingecko_id(symbol)
    if not cg_id:
        return None
    url = f"{COINGECKO_BASE}/simple/price"
    started = _time.perf_counter()
    try:
        with _client() as client:
            r = client.get(
                url,
                params={
                    "ids": cg_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true",
                },
            )
            r.raise_for_status()
            payload = r.json().get(cg_id, {})
        price = _safe_float(payload.get("usd"))
        if price <= 0:
            raise ValueError("missing usd price")
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "coingecko", symbol, "price", ms, "success", url=url)
        return {
            "symbol": symbol,
            "price": round(price, 4 if price < 10 else 2),
            "change_pct": round(_safe_float(payload.get("usd_24h_change")), 2),
            "change_abs": 0.0,
            "volume_24h": _safe_float(payload.get("usd_24h_vol")),
            "trades_24h": 0,
            "source": "coingecko",
        }
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "coingecko", symbol, "price", ms, f"{type(exc).__name__}: {exc}", url=url)
        return None


def _fetch_yfinance_price(symbol: str) -> Optional[Dict]:
    ticker = _yahoo_symbol(symbol)
    started = _time.perf_counter()
    try:
        hist = yf.download(ticker, period="7d", interval="1d", progress=False, auto_adjust=False, threads=False)
        if hist is None or hist.empty:
            raise ValueError("empty history")
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        hist = hist.rename(columns=str.title)
        last_close = float(hist["Close"].dropna().iloc[-1])
        prev_close = float(hist["Close"].dropna().iloc[-2]) if len(hist["Close"].dropna()) >= 2 else last_close
        volume = float(hist["Volume"].dropna().iloc[-1]) if "Volume" in hist else 0.0
        change_abs = last_close - prev_close
        change_pct = (change_abs / prev_close * 100.0) if prev_close else 0.0
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "yfinance", symbol, "price", ms, "success", url=ticker)
        return {
            "symbol": symbol,
            "price": round(last_close, 4 if last_close < 10 else 2),
            "change_pct": round(change_pct, 2),
            "change_abs": round(change_abs, 4 if last_close < 10 else 2),
            "volume_24h": volume * last_close,
            "trades_24h": 0,
            "source": "yfinance",
        }
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "yfinance", symbol, "price", ms, f"{type(exc).__name__}: {exc}", url=ticker)
        return None


def get_crypto_ohlcv(symbol: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    global _last_daily_update_ts, _last_h4_update_ts
    sym = _normalize_symbol(symbol)
    now = _time.time()

    if timeframe == "4h":
        entry = _ohlcv_4h_cache.get(sym)
        if entry and (now - entry["ts"]) < OHLCV_4H_TTL:
            return entry["df"]
        df = _first_not_none(
            _fetch_binance_klines(_binance_pair(sym), "4h", 500, sym),
            _fetch_yfinance_ohlcv(sym, "4h"),
        )
        if df is not None and len(df) >= 120:
            _ohlcv_4h_cache[sym] = {"df": df, "ts": now}
            _last_h4_update_ts = now
        return df

    entry = _ohlcv_daily_cache.get(sym)
    if entry and (now - entry["ts"]) < OHLCV_DAILY_TTL:
        return entry["df"]

    df = _first_not_none(
        _fetch_binance_klines(_binance_pair(sym), "1d", 500, sym),
        _fetch_coingecko_ohlcv(sym, 365),
        _fetch_yfinance_ohlcv(sym, "1d"),
    )
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

    out = _first_not_none(
        _fetch_binance_price(sym),
        _fetch_coingecko_price(sym),
        _fetch_yfinance_price(sym),
    )
    if out is not None:
        out["ts"] = now
        _price_cache[sym] = out
        _last_price_update_ts = now
    return out


def get_crypto_market_snapshots() -> Dict[str, Dict]:
    global _last_market_update_ts
    now = _time.time()
    if _markets_cache and (now - _markets_cache.get("ts", 0)) < MARKETS_TTL:
        return _markets_cache["data"]

    ids = ",".join(filter(None, (_coingecko_id(symbol) for symbol in CRYPTO_SYMBOLS)))
    url = f"{COINGECKO_BASE}/coins/markets"
    started = _time.perf_counter()
    try:
        with _client() as client:
            r = client.get(
                url,
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
                "market_cap": _safe_float(item.get("market_cap")),
                "market_cap_rank": item.get("market_cap_rank"),
                "volume_24h": _safe_float(item.get("total_volume")),
                "change_24h": _safe_float(item.get("price_change_percentage_24h_in_currency")),
                "change_7d": _safe_float(item.get("price_change_percentage_7d_in_currency")),
                "change_30d": _safe_float(item.get("price_change_percentage_30d_in_currency")),
                "liquidity_score": _safe_float(item.get("liquidity_score")),
                "image": item.get("image"),
            }
        _markets_cache.update({"ts": now, "data": out})
        _last_market_update_ts = now
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "coingecko", "ALL", "markets", ms, "success", url=url, rows=len(out))
        return out
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "coingecko", "ALL", "markets", ms, f"{type(exc).__name__}: {exc}", url=url, rows=0)
        return _markets_cache.get("data", {})


def get_crypto_global_metrics() -> Dict:
    global _last_global_update_ts
    now = _time.time()
    if _global_cache and (now - _global_cache.get("ts", 0)) < GLOBAL_TTL:
        return _global_cache["data"]

    url = f"{COINGECKO_BASE}/global"
    started = _time.perf_counter()
    try:
        with _client() as client:
            r = client.get(url)
            r.raise_for_status()
            payload = r.json().get("data", {})
        out = {
            "btc_dominance": _safe_float(payload.get("market_cap_percentage", {}).get("btc")),
            "eth_dominance": _safe_float(payload.get("market_cap_percentage", {}).get("eth")),
            "total_market_cap": _safe_float(payload.get("total_market_cap", {}).get("usd")),
            "total_volume": _safe_float(payload.get("total_volume", {}).get("usd")),
            "market_cap_change_24h": _safe_float(payload.get("market_cap_change_percentage_24h_usd")),
            "active_cryptocurrencies": int(_safe_float(payload.get("active_cryptocurrencies"))),
        }
        _global_cache.update({"ts": now, "data": out})
        _last_global_update_ts = now
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("OK", "coingecko", "ALL", "global", ms, "success", url=url)
        return out
    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        _log_source_event("FAIL", "coingecko", "ALL", "global", ms, f"{type(exc).__name__}: {exc}", url=url)
        return _global_cache.get("data", {})


def debug_crypto_sources() -> Dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    entries: List[Dict[str, object]] = []

    def _pack(source_name: str, started: float, error_message: Optional[str], sample_price_btc: Optional[float], btc_rows: int, eth_rows: int) -> None:
        entries.append(
            {
                "source_name": source_name,
                "status": "OK" if error_message is None else "FAIL",
                "latency_ms": round((_time.perf_counter() - started) * 1000, 1),
                "error_message": error_message,
                "sample_price_BTC": sample_price_btc,
                "sample_ohlcv_rows_BTC": btc_rows,
                "sample_ohlcv_rows_ETH": eth_rows,
                "timestamp": now,
            }
        )

    started = _time.perf_counter()
    try:
        btc_price = _fetch_binance_price("BTC")
        btc = _fetch_binance_klines(_binance_pair("BTC"), "1d", 30, "BTC")
        eth = _fetch_binance_klines(_binance_pair("ETH"), "1d", 30, "ETH")
        _pack("binance", started, None if (btc_price or btc is not None or eth is not None) else "all samples empty", btc_price.get("price") if btc_price else None, len(btc) if btc is not None else 0, len(eth) if eth is not None else 0)
    except Exception as exc:
        _pack("binance", started, f"{type(exc).__name__}: {exc}", None, 0, 0)

    started = _time.perf_counter()
    try:
        btc_price = _fetch_coingecko_price("BTC")
        btc = _fetch_coingecko_ohlcv("BTC", 365)
        eth = _fetch_coingecko_ohlcv("ETH", 365)
        _pack("coingecko", started, None if (btc_price or btc is not None or eth is not None) else "all samples empty", btc_price.get("price") if btc_price else None, len(btc) if btc is not None else 0, len(eth) if eth is not None else 0)
    except Exception as exc:
        _pack("coingecko", started, f"{type(exc).__name__}: {exc}", None, 0, 0)

    started = _time.perf_counter()
    try:
        btc_price = _fetch_yfinance_price("BTC")
        btc = _fetch_yfinance_ohlcv("BTC", "1d")
        eth = _fetch_yfinance_ohlcv("ETH", "1d")
        _pack("yfinance", started, None if (btc_price or btc is not None or eth is not None) else "all samples empty", btc_price.get("price") if btc_price else None, len(btc) if btc is not None else 0, len(eth) if eth is not None else 0)
    except Exception as exc:
        _pack("yfinance", started, f"{type(exc).__name__}: {exc}", None, 0, 0)

    return {
        "timestamp": now,
        "sources": entries,
    }


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
    meta = _meta(symbol)
    return meta.get("sector", "Crypto")
