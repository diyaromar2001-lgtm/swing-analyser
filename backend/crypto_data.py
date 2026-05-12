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
_ohlcv_1m_cache: Dict[str, dict] = {}
_ohlcv_5m_cache: Dict[str, dict] = {}
_ohlcv_15m_cache: Dict[str, dict] = {}
_markets_cache: dict = {}
_global_cache: dict = {}
_last_price_update_ts: float = 0.0
_last_daily_update_ts: float = 0.0
_last_h4_update_ts: float = 0.0
_last_market_update_ts: float = 0.0
_last_global_update_ts: float = 0.0
_last_intraday_update_ts: float = 0.0

PRICE_TTL = 60
OHLCV_4H_TTL = 900
OHLCV_DAILY_TTL = 3600
OHLCV_1M_TTL = 300  # 5 min cache for 1m data (fresh)
OHLCV_5M_TTL = 600  # 10 min cache for 5m data
OHLCV_15M_TTL = 900  # 15 min cache for 15m data
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
        exc_type = type(exc).__name__
        exc_detail = str(exc)[:200]  # First 200 chars of exception

        # Try to extract HTTP status if available
        http_status = ""
        if hasattr(exc, "response") and exc.response is not None:
            http_status = f" [HTTP {exc.response.status_code}]"

        error_msg = f"{exc_type}: {exc_detail}{http_status}"
        _log_source_event("FAIL", "binance", symbol, f"ohlcv_{interval}", ms, error_msg, url=url, rows=0)

        # Also print to stdout for visibility in logs
        print(f"[BINANCE_DEBUG] {symbol} {interval}: {error_msg} | URL: {url}?symbol={pair}&interval={interval}&limit={limit} | Duration: {ms:.1f}ms")

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


def _yf_history_safe_crypto(ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """
    Robust yfinance history fetcher for crypto that avoids "Invalid Crumb" errors.
    Uses yf.Ticker().history() instead of yf.download() for better reliability.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        # Note: progress parameter is NOT valid for history() - only for download()
        df = ticker_obj.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _fetch_yfinance_ohlcv(symbol: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    ticker = _yahoo_symbol(symbol)
    started = _time.perf_counter()
    try:
        if timeframe == "4h":
            raw = _yf_history_safe_crypto(ticker, period="60d", interval="1h")
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
            raw = _yf_history_safe_crypto(ticker, period="730d", interval="1d")
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
        hist = _yf_history_safe_crypto(ticker, period="7d", interval="1d")
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


def get_crypto_ohlcv(symbol: str, timeframe: str = "1d", allow_download: bool = True) -> Optional[pd.DataFrame]:
    global _last_daily_update_ts, _last_h4_update_ts
    sym = _normalize_symbol(symbol)
    now = _time.time()

    if timeframe == "4h":
        entry = _ohlcv_4h_cache.get(sym)
        if entry and ((now - entry["ts"]) < OHLCV_4H_TTL or not allow_download):
            return entry["df"]
        if not allow_download:
            return None
        df = _first_not_none(
            _fetch_binance_klines(_binance_pair(sym), "4h", 500, sym),
            _fetch_yfinance_ohlcv(sym, "4h"),
        )
        if df is not None and len(df) >= 120:
            _ohlcv_4h_cache[sym] = {"df": df, "ts": now}
            _last_h4_update_ts = now
        return df

    entry = _ohlcv_daily_cache.get(sym)
    if entry and ((now - entry["ts"]) < OHLCV_DAILY_TTL or not allow_download):
        return entry["df"]
    if not allow_download:
        return None

    df = _first_not_none(
        _fetch_binance_klines(_binance_pair(sym), "1d", 500, sym),
        _fetch_coingecko_ohlcv(sym, 365),
        _fetch_yfinance_ohlcv(sym, "1d"),
    )
    if df is not None and len(df) >= 220:
        _ohlcv_daily_cache[sym] = {"df": df, "ts": now}
        _last_daily_update_ts = now
    return df


def get_crypto_price_snapshot(symbol: str, allow_download: bool = True) -> Optional[Dict]:
    global _last_price_update_ts
    sym = _normalize_symbol(symbol)
    now = _time.time()
    entry = _price_cache.get(sym)
    if entry and ((now - entry["ts"]) < PRICE_TTL or not allow_download):
        return entry
    if not allow_download:
        return None

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


def get_crypto_market_snapshots(allow_download: bool = True) -> Dict[str, Dict]:
    global _last_market_update_ts
    now = _time.time()
    if _markets_cache and ((now - _markets_cache.get("ts", 0)) < MARKETS_TTL or not allow_download):
        return _markets_cache["data"]
    if not allow_download:
        return _markets_cache.get("data", {})

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


def get_crypto_global_metrics(allow_download: bool = True) -> Dict:
    global _last_global_update_ts
    now = _time.time()
    if _global_cache and ((now - _global_cache.get("ts", 0)) < GLOBAL_TTL or not allow_download):
        return _global_cache["data"]
    if not allow_download:
        return _global_cache.get("data", {})

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


# ── Intraday Provider Fallback Chain ──────────────────────────────────────────

def _fetch_coinbase_klines(symbol: str, granularity: int = 300, limit: int = 300) -> Optional[pd.DataFrame]:
    """Fetch 5m candles from Coinbase Pro API (public, no auth)."""
    pair = f"{symbol}-USD"
    url = "https://api.exchange.coinbase.com/products/{}/candles".format(pair)
    started = _time.perf_counter()
    print(f"[COINBASE_DEBUG] {symbol} request started: pair={pair} granularity={granularity} limit={limit}")

    try:
        with _client() as client:
            print(f"[COINBASE_DEBUG] {symbol} making HTTP request to {url}")
            r = client.get(url, params={"granularity": granularity, "limit": limit})
            print(f"[COINBASE_DEBUG] {symbol} HTTP {r.status_code}")
            r.raise_for_status()
            raw = r.json()
            print(f"[COINBASE_DEBUG] {symbol} got response: {type(raw)} len={len(raw) if isinstance(raw, list) else 'N/A'}")

        if not raw or not isinstance(raw, list):
            ms = (_time.perf_counter() - started) * 1000
            print(f"[COINBASE_DEBUG] {symbol} FAIL: empty or non-list response after {ms:.1f}ms")
            _log_source_event("FAIL", "coinbase", symbol, "ohlcv_5m", ms, "empty response", url=url, rows=0)
            return None

        # Coinbase format: [[time, low, high, open, close, volume], ...]
        df = pd.DataFrame(
            raw,
            columns=["open_time", "Low", "High", "Open", "Close", "Volume"],
        )
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Date"] = pd.to_datetime(df["open_time"], unit="s", utc=True)
        df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].dropna()

        ms = (_time.perf_counter() - started) * 1000
        print(f"[COINBASE_DEBUG] {symbol} SUCCESS: {len(df)} candles in {ms:.1f}ms")
        _log_source_event("OK", "coinbase", symbol, "ohlcv_5m", ms, "success", url=url, rows=len(df))
        return df

    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        error_detail = f"{type(exc).__name__}: {str(exc)[:100]}"
        print(f"[COINBASE_DEBUG] {symbol} EXCEPTION after {ms:.1f}ms: {error_detail}")
        _log_source_event("FAIL", "coinbase", symbol, "ohlcv_5m", ms, error_detail, url=url, rows=0)
        return None


def _fetch_kraken_ohlc(symbol: str, interval: int = 5) -> Optional[pd.DataFrame]:
    """Fetch 5m candles from Kraken API (public, no auth)."""
    # Kraken pair format: XXBTZUSD, XETHZUSD, SOLDUSD, etc.
    kraken_pairs = {
        "BTC": "XXBTZUSD",
        "ETH": "XETHZUSD",
        "SOL": "SOLDUSD",
        "BNB": "BNBUSD",
        "XRP": "XXRPZUSD",
    }
    pair = kraken_pairs.get(symbol, symbol + "USD")
    url = "https://api.kraken.com/0/public/OHLC"
    started = _time.perf_counter()
    print(f"[KRAKEN_DEBUG] {symbol} request started: pair={pair} interval={interval}")

    try:
        with _client() as client:
            print(f"[KRAKEN_DEBUG] {symbol} making HTTP request to {url}")
            r = client.get(url, params={"pair": pair, "interval": interval})
            print(f"[KRAKEN_DEBUG] {symbol} HTTP {r.status_code}")
            r.raise_for_status()
            data = r.json()

        ohlc_data = data.get("result", {}).get(pair, [])
        print(f"[KRAKEN_DEBUG] {symbol} got response: ohlc_data len={len(ohlc_data) if ohlc_data else 0}")
        if not ohlc_data:
            ms = (_time.perf_counter() - started) * 1000
            print(f"[KRAKEN_DEBUG] {symbol} FAIL: empty response after {ms:.1f}ms")
            _log_source_event("FAIL", "kraken", symbol, "ohlcv_5m", ms, "empty response", url=url, rows=0)
            return None

        # Kraken format: [[time, open, high, low, close, vwap, volume, count], ...]
        df = pd.DataFrame(
            ohlc_data,
            columns=["open_time", "Open", "High", "Low", "Close", "vwap", "Volume", "count"],
        )
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Date"] = pd.to_datetime(df["open_time"], unit="s", utc=True)
        df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].dropna()

        ms = (_time.perf_counter() - started) * 1000
        print(f"[KRAKEN_DEBUG] {symbol} SUCCESS: {len(df)} candles in {ms:.1f}ms")
        _log_source_event("OK", "kraken", symbol, "ohlcv_5m", ms, "success", url=url, rows=len(df))
        return df

    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        error_detail = f"{type(exc).__name__}: {str(exc)[:100]}"
        print(f"[KRAKEN_DEBUG] {symbol} EXCEPTION after {ms:.1f}ms: {error_detail}")
        _log_source_event("FAIL", "kraken", symbol, "ohlcv_5m", ms, error_detail, url=url, rows=0)
        return None


def _fetch_okx_candles(symbol: str, bar: str = "5m") -> Optional[pd.DataFrame]:
    """Fetch 5m candles from OKX API (public, no auth)."""
    inst_id = f"{symbol}-USD"
    url = "https://www.okx.com/api/v5/market/candles"
    started = _time.perf_counter()
    print(f"[OKX_DEBUG] {symbol} request started: inst_id={inst_id} bar={bar}")

    try:
        with _client() as client:
            print(f"[OKX_DEBUG] {symbol} making HTTP request to {url}")
            r = client.get(url, params={"instId": inst_id, "bar": bar, "limit": 100})
            print(f"[OKX_DEBUG] {symbol} HTTP {r.status_code}")
            r.raise_for_status()
            data = r.json()
            print(f"[OKX_DEBUG] {symbol} got response: type={type(data)}")

        candles = data.get("data", [])
        print(f"[OKX_DEBUG] {symbol} got response: candles len={len(candles) if candles else 0}")
        if not candles:
            ms = (_time.perf_counter() - started) * 1000
            print(f"[OKX_DEBUG] {symbol} FAIL: empty response after {ms:.1f}ms")
            _log_source_event("FAIL", "okx", symbol, "ohlcv_5m", ms, "empty response", url=url, rows=0)
            return None

        # OKX format: [[timestamp_ms, open, high, low, close, vol, vol_ccy, vol_ccy_quote, confirm], ...]
        df = pd.DataFrame(
            candles,
            columns=["open_time_ms", "Open", "High", "Low", "Close", "Volume", "vol_ccy", "vol_ccy_quote", "confirm"],
        )
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # OKX timestamp is in milliseconds as integer, convert to int first
        df["open_time_ms"] = pd.to_numeric(df["open_time_ms"], errors="coerce").astype("int64")
        df["Date"] = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
        df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].dropna()

        ms = (_time.perf_counter() - started) * 1000
        print(f"[OKX_DEBUG] {symbol} SUCCESS: {len(df)} candles in {ms:.1f}ms")
        _log_source_event("OK", "okx", symbol, "ohlcv_5m", ms, "success", url=url, rows=len(df))
        return df

    except Exception as exc:
        ms = (_time.perf_counter() - started) * 1000
        error_detail = f"{type(exc).__name__}: {str(exc)[:100]}"
        print(f"[OKX_DEBUG] {symbol} EXCEPTION after {ms:.1f}ms: {error_detail}")
        _log_source_event("FAIL", "okx", symbol, "ohlcv_5m", ms, error_detail, url=url, rows=0)
        return None


# Track which provider was used for each symbol (for diagnostics)
_intraday_provider_used: Dict[str, str] = {}


def get_crypto_ohlcv_intraday(symbol: str, interval: str = "5m", allow_download: bool = True) -> Optional[pd.DataFrame]:
    """
    Fetch intraday OHLCV data (1m, 5m, 15m) for scalp analysis.
    Tries Binance 1m, fallback to 5m if 1m unavailable.

    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH")
        interval: "1m", "5m", or "15m"
        allow_download: If False, use cache only

    Returns:
        DataFrame with OHLCV data, or None if unavailable
    """
    global _last_intraday_update_ts
    sym = _normalize_symbol(symbol)
    now = _time.time()

    # Select cache based on interval
    if interval == "1m":
        cache = _ohlcv_1m_cache
        ttl = OHLCV_1M_TTL
    elif interval == "5m":
        cache = _ohlcv_5m_cache
        ttl = OHLCV_5M_TTL
    elif interval == "15m":
        cache = _ohlcv_15m_cache
        ttl = OHLCV_15M_TTL
    else:
        return None

    # Check cache
    entry = cache.get(sym)
    if entry and ((now - entry["ts"]) < ttl or not allow_download):
        return entry["df"]

    if not allow_download:
        return None

    # Try to fetch with provider fallback chain
    df = None
    provider_used = None

    # DEBUG: Log entry point
    print(f"[INTRADAY_DEBUG] {sym} interval={interval} allow_download={allow_download} cache_entry={entry is not None}")

    # 1. Try Binance first (works locally, may fail at Railway with HTTP 451)
    if interval in ("1m", "5m", "15m"):
        pair = _binance_pair(sym)
        print(f"[INTRADAY_DEBUG] {sym} trying BINANCE pair={pair} interval={interval}")
        df = _fetch_binance_klines(pair, interval, 300, sym)
        if df is not None and len(df) >= 20:
            provider_used = "BINANCE"
            print(f"[INTRADAY_DEBUG] {sym} BINANCE SUCCESS: {len(df)} candles")
        else:
            candles = len(df) if df is not None else 0
            print(f"[INTRADAY_DEBUG] {sym} BINANCE FAILED: df={df is not None} candles={candles}")

    # 2. Fallback: if Binance failed and 1m requested, try Binance 5m
    if df is None and interval == "1m":
        pair = _binance_pair(sym)
        print(f"[INTRADAY_DEBUG] {sym} trying BINANCE 5m fallback (1m failed)")
        df = _fetch_binance_klines(pair, "5m", 300, sym)
        if df is not None and len(df) >= 20:
            provider_used = "BINANCE_5M_FALLBACK"
            print(f"[INTRADAY_DEBUG] {sym} BINANCE 5m FALLBACK SUCCESS: {len(df)} candles")
            _log_source_event("OK", "binance", sym, "ohlcv_intraday_fallback", 0, "1m unavailable, using 5m", rows=len(df))
        else:
            candles = len(df) if df is not None else 0
            print(f"[INTRADAY_DEBUG] {sym} BINANCE 5m FALLBACK FAILED: candles={candles}")

    # 3. Provider fallback chain (Binance failed or HTTP 451 at Railway)
    # Only use fallback for 5m interval
    if df is None and interval == "5m":
        print(f"[INTRADAY_DEBUG] {sym} starting provider fallback chain (5m interval)")

        # Try Coinbase
        if df is None:
            print(f"[INTRADAY_DEBUG] {sym} trying COINBASE")
            df = _fetch_coinbase_klines(sym, granularity=300, limit=300)
            if df is not None and len(df) >= 20:
                provider_used = "COINBASE"
                print(f"[INTRADAY_DEBUG] {sym} COINBASE SUCCESS: {len(df)} candles")
            else:
                candles = len(df) if df is not None else 0
                print(f"[INTRADAY_DEBUG] {sym} COINBASE FAILED: df={df is not None} candles={candles}")

        # Try Kraken (skip SOL which is known to fail)
        if df is None and sym != "SOL":
            print(f"[INTRADAY_DEBUG] {sym} trying KRAKEN")
            df = _fetch_kraken_ohlc(sym, interval=5)
            if df is not None and len(df) >= 20:
                provider_used = "KRAKEN"
                print(f"[INTRADAY_DEBUG] {sym} KRAKEN SUCCESS: {len(df)} candles")
            else:
                candles = len(df) if df is not None else 0
                print(f"[INTRADAY_DEBUG] {sym} KRAKEN FAILED: df={df is not None} candles={candles}")
        elif sym == "SOL":
            print(f"[INTRADAY_DEBUG] {sym} SKIPPING KRAKEN (SOL known to fail)")

        # Try OKX
        if df is None:
            print(f"[INTRADAY_DEBUG] {sym} trying OKX")
            df = _fetch_okx_candles(sym, bar="5m")
            if df is not None and len(df) >= 20:
                provider_used = "OKX"
                print(f"[INTRADAY_DEBUG] {sym} OKX SUCCESS: {len(df)} candles")
            else:
                candles = len(df) if df is not None else 0
                print(f"[INTRADAY_DEBUG] {sym} OKX FAILED: df={df is not None} candles={candles}")

    # Store in cache if successful
    if df is not None and len(df) >= 20:
        cache[sym] = {"df": df, "ts": now}
        _last_intraday_update_ts = now
        _intraday_provider_used[sym] = provider_used or "UNKNOWN"
        print(f"[INTRADAY_DEBUG] {sym} CACHED with provider={provider_used}")
        return df

    # Log final failure
    if provider_used is None:
        print(f"[INTRADAY_DEBUG] {sym} ALL PROVIDERS EXHAUSTED - returning None")
        _log_source_event("FAIL", "intraday-fallback", sym, "all_providers", 0, "all providers exhausted")
        _intraday_provider_used[sym] = "NONE"

    return None


def _fetch_binance_klines_paginated(pair: str, interval: str, symbol: str, days: int = 7, timeout_seconds: int = 30) -> Optional[pd.DataFrame]:
    """
    Phase 3B.2a: Fetch Binance klines with pagination for extended period (7 days).
    Uses startTime/endTime parameters to paginate through multiple requests.

    Args:
        pair: Binance pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "5m")
        symbol: Crypto symbol for logging
        days: Number of days to fetch (default 7, only 7 supported in Phase 3B.2a)
        timeout_seconds: Total timeout for all requests (default 30)

    Returns:
        DataFrame with paginated OHLCV data, or None if failed
    """
    if days != 7:
        return None

    url = f"{BINANCE_BASE}/api/v3/klines"
    started = _time.time()
    all_data = []

    try:
        # Calculate end time (now) and start time (days ago)
        end_time = int(_time.time() * 1000)  # Now in milliseconds
        start_time = end_time - (days * 24 * 60 * 60 * 1000)  # days ago in milliseconds

        # Interval in milliseconds: 5m = 5 * 60 * 1000 = 300000
        interval_ms = {
            "1m": 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
        }.get(interval, 300000)

        # Fetch in batches of 300 candles (Binance limit)
        current_start = start_time
        batch_count = 0

        while current_start < end_time:
            # Check total timeout
            elapsed = _time.time() - started
            if elapsed > timeout_seconds:
                print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: Timeout after {elapsed:.1f}s, {batch_count} batches, {len(all_data)} total candles")
                if len(all_data) >= 50:
                    break
                else:
                    return None

            try:
                with _client() as client:
                    batch_end = int(min(current_start + 300 * interval_ms, end_time))
                    params = {
                        "symbol": pair,
                        "interval": interval,
                        "startTime": int(current_start),
                        "endTime": batch_end,
                        "limit": 300
                    }

                    r = client.get(url, params=params, timeout=15.0)
                    r.raise_for_status()
                    raw = r.json()

                    if not raw or len(raw) == 0:
                        break  # No more data

                    all_data.extend(raw)
                    batch_count += 1
                    print(f"[BINANCE_PAGINATED] {symbol} {interval}: Batch {batch_count} fetched {len(raw)} candles (total: {len(all_data)})")

                    # Move start time to just after the last candle
                    last_close_time = int(raw[-1][6])  # close_time is element 6
                    if last_close_time >= end_time:
                        break  # Reached end of requested period
                    current_start = last_close_time + 1

            except Exception as batch_exc:
                print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: Batch {batch_count} error: {type(batch_exc).__name__}")
                if batch_count == 0:
                    # First batch failed, return None
                    raise
                else:
                    # Got some data before error, use what we have
                    break

        if not all_data or len(all_data) < 20:
            print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: Insufficient data {len(all_data)} candles")
            return None

        # Create DataFrame from all batches
        df = pd.DataFrame(
            all_data,
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

        if len(df) < 20:
            print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: After dropna only {len(df)} candles remain")
            return None

        ms = (_time.time() - started) * 1000
        print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: SUCCESS {len(df)} candles in {batch_count} batches ({ms:.1f}ms)")
        _log_source_event("OK", "binance_paginated", symbol, f"ohlcv_extended_{interval}", ms, f"success {batch_count} batches", url=url, rows=len(df))

        return df

    except Exception as exc:
        ms = (_time.time() - started) * 1000
        exc_type = type(exc).__name__
        exc_detail = str(exc)[:200]

        http_status = ""
        if hasattr(exc, "response") and exc.response is not None:
            http_status = f" [HTTP {exc.response.status_code}]"

        error_msg = f"{exc_type}: {exc_detail}{http_status}"
        print(f"[BINANCE_PAGINATED_DEBUG] {symbol} {interval}: FAILED {error_msg} ({ms:.1f}ms)")
        _log_source_event("FAIL", "binance_paginated", symbol, f"ohlcv_extended_{interval}", ms, error_msg, url=url, rows=0)

        return None


def get_crypto_ohlcv_extended(symbol: str, interval: str = "5m", days: int = 7) -> Optional[tuple[Optional[pd.DataFrame], int, float, dict]]:
    """
    Phase 3B.2a: Fetch extended OHLCV data (7 days with pagination).

    Tries Binance paginated first. If blocked (HTTP 451/403) or fails,
    fallback to get_crypto_ohlcv_intraday() which provides fallback provider chain.

    Returns:
        Tuple: (DataFrame, candles_count, effective_period_days, metadata)
        metadata = {"data_source": str, "provider_attempts": list, "provider_errors": dict}
    """
    if days != 7:
        return None, 0, 0, {}

    sym = _normalize_symbol(symbol)
    pair = _binance_pair(sym)

    metadata = {
        "data_source": None,
        "provider_attempts": ["binance_paginated"],
        "provider_errors": {}
    }

    try:
        # Try Binance paginated first (preferred for 7 days)
        df = _fetch_binance_klines_paginated(pair, interval, sym, days=7)

        if df is not None and len(df) >= 50:
            candles_count = len(df)
            effective_period_days = (candles_count * 5) / (24 * 60)
            metadata["data_source"] = "binance_paginated"
            return df, candles_count, effective_period_days, metadata
        else:
            reason = f"{len(df) if df is not None else 0} candles"
            metadata["provider_errors"]["binance_paginated"] = reason

    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)[:100]}"
        metadata["provider_errors"]["binance_paginated"] = error_detail

    # Fallback: Use get_crypto_ohlcv_intraday which has provider fallback chain
    try:
        metadata["provider_attempts"].append("intraday_fallback_chain")
        df = get_crypto_ohlcv_intraday(sym, interval="5m", allow_download=True)

        if df is not None and len(df) >= 50:
            candles_count = len(df)
            effective_period_days = (candles_count * 5) / (24 * 60)
            provider_used = _intraday_provider_used.get(sym, "unknown")
            metadata["data_source"] = f"intraday_fallback ({provider_used})"
            return df, candles_count, effective_period_days, metadata
        else:
            reason = f"{len(df) if df is not None else 0} candles"
            metadata["provider_errors"]["intraday_fallback_chain"] = reason

    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)[:100]}"
        metadata["provider_errors"]["intraday_fallback_chain"] = error_detail

    # All providers exhausted
    return None, 0, 0, metadata


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
    global _last_price_update_ts, _last_daily_update_ts, _last_h4_update_ts, _last_market_update_ts, _last_global_update_ts, _last_intraday_update_ts
    _price_cache.clear()
    _ohlcv_daily_cache.clear()
    _ohlcv_4h_cache.clear()
    _ohlcv_1m_cache.clear()
    _ohlcv_5m_cache.clear()
    _ohlcv_15m_cache.clear()
    _markets_cache.clear()
    _global_cache.clear()
    _last_price_update_ts = 0.0
    _last_daily_update_ts = 0.0
    _last_h4_update_ts = 0.0
    _last_market_update_ts = 0.0
    _last_global_update_ts = 0.0
    _last_intraday_update_ts = 0.0


def available_crypto_symbols() -> List[str]:
    return list(CRYPTO_SYMBOLS)


def crypto_sector(symbol: str) -> str:
    meta = _meta(symbol)
    return meta.get("sector", "Crypto")
