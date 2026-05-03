from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import time as _time

# Chargement .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd
import numpy as np
from typing import Any, List, Optional, Dict
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
import threading
from collections import Counter

from indicators import (
    sma, rsi, macd, atr, perf_pct,
    new_high_30d, volume_above_avg, atr_stable,
    avg_volume_30d, high_52w as _high_52w, support_level,
)
from backtest import run_backtest, BacktestResult
from strategy import (
    hard_filter, compute_dynamic_levels, compute_professional_score,
    classify_setup, compute_confidence, detect_signal_type,
    compute_quality_score, compute_final_decision,
    grade_to_category, grade_to_position,
    # rétrocompat
    classify_standard, classify_conservative,
    detect_buy_signal_standard, detect_buy_signal_conservative,
)
from fundamental_filters import compute_fundamental_risk
from tickers import ALL_TICKERS, TICKER_SECTOR, TICKERS
from strategy_lab import LAB_STRATEGIES, backtest_ticker_lab, aggregate_lab_result
from sentiment import get_sentiment
from optimizer import run_optimizer
from signal_tracker import (
    log_signal, update_outcomes, update_outcomes_ohlc,
    get_signals, get_signal_stats,
)
from portfolio_backtest import run_portfolio_backtest
from market_context import compute_market_context, _fetch_vix, _fetch_sector_strength
from earnings import get_earnings_date
from setup_validator import validate_setup
from market_regime_engine import compute_regime_engine
from ticker_edge import compute_ticker_edge, get_cached_edge, invalidate_cache as _invalidate_edge_cache
import market_regime_engine as _regime_engine_module
import market_context as _market_context_module
import ticker_edge as _ticker_edge_module
import crypto_data as _crypto_data_module
import crypto_service as _crypto_service_module
from crypto_data import clear_crypto_caches, crypto_sector, debug_crypto_sources
from crypto_edge import _edge_cache as _crypto_edge_cache
from crypto_edge import clear_crypto_edge_cache, compute_crypto_edge, get_cached_crypto_edge
from crypto_regime_engine import _cache as _crypto_regime_cache
from crypto_regime_engine import compute_crypto_regime, invalidate_cache as _invalidate_crypto_regime_cache
from crypto_service import (
    analyze_crypto_symbol,
    clear_crypto_screener_cache,
    crypto_data_freshness,
    crypto_prices,
    crypto_screener,
)
from crypto_strategy_lab import compute_crypto_strategy_lab, evaluate_crypto_strategy_for_symbol
from crypto_universe import CRYPTO_SECTORS, CRYPTO_SYMBOLS
from trade_journal import (
    add_event as trade_journal_add_event,
    cancel_trade as trade_journal_cancel,
    close_trade as trade_journal_close,
    create_trade as trade_journal_create,
    delete_trade as trade_journal_delete,
    get_trade as trade_journal_get,
    init_db as trade_journal_init_db,
    list_events as trade_journal_list_events,
    list_trades as trade_journal_list,
    open_trade as trade_journal_open,
    stats as trade_journal_stats,
    update_trade as trade_journal_update,
)

app = FastAPI(title="Swing Trading Screener Pro")
trade_journal_init_db()

import os as _os
_FRONTEND_URL = _os.environ.get("FRONTEND_URL", "http://localhost:3000")
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    _FRONTEND_URL,
    # Vercel preview URLs
    "https://*.vercel.app",
]

_ADMIN_API_KEY = _os.environ.get("ADMIN_API_KEY")
_ADMIN_WARNING_EMITTED = False


def require_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    global _ADMIN_WARNING_EMITTED
    if not _ADMIN_API_KEY:
        if not _ADMIN_WARNING_EMITTED:
            print("[security] ADMIN_API_KEY absent - endpoints admin non bloqués (mode local/dev).")
            _ADMIN_WARNING_EMITTED = True
        return
    if x_admin_key != _ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Action admin protégée")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check (keep-alive pour Railway) ───────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/admin/ping")
def admin_ping(_: None = Depends(require_admin_key)):
    return {"status": "ok", "admin": True}


# ── Market Status (ouvert / fermé) ────────────────────────────────────────────
@app.get("/api/market-status")
def market_status():
    """
    Retourne si le marché US est actuellement ouvert.
    Les setups swing sont basés sur OHLC daily → disponibles 24/7.
    Le statut marché sert uniquement à l'UI (mode Exécution vs Préparation).
    """
    from datetime import datetime, timezone, timedelta
    import pytz
    try:
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)
        weekday = now_et.weekday()  # 0=lundi, 6=dimanche
        hour    = now_et.hour
        minute  = now_et.minute
        # Marché ouvert lun-ven 9h30-16h00 ET
        is_open = (
            weekday < 5 and
            (hour > 9 or (hour == 9 and minute >= 30)) and
            hour < 16
        )
        return {
            "is_open":      is_open,
            "mode":         "EXECUTION" if is_open else "PREPARATION",
            "time_et":      now_et.strftime("%H:%M ET"),
            "day":          now_et.strftime("%A"),
            "message":      "Market Open — Execution Mode" if is_open else "Market Closed — Trade Plan Ready",
        }
    except Exception:
        return {"is_open": False, "mode": "PREPARATION", "time_et": "--:--", "day": "--",
                "message": "Market Closed — Trade Plan Ready"}

# ── Cache globals ─────────────────────────────────────────────────────────────
_cache: Dict[str, dict] = {}
_sp500_perf_3m: float = 0.0
_sp500_perf_6m: float = 0.0
_market_regime_cache: dict = {}
_opt_data_cache: Dict[str, object] = {}
_screener_cache: Dict[str, dict] = {}
_SCREENER_TTL = 60
_screener_warm_lock = threading.Lock()
_screener_warming = False
_warmup_progress: Dict[str, dict] = {}

# ── Cache OHLCV historique (4h) — indicateurs stables sur la journée ─────────
# SMA200, RSI, MACD, ATR… ne bougent pas significativement en intraday.
_ohlcv_cache: Dict[str, dict] = {}
_OHLCV_TTL = 14_400   # 4h
_OHLCV_FETCH_TIMEOUT = 8

# ── Cache prix actuel (60 s) — fetch léger 5 jours ───────────────────────────
# Seul le "last price" change minute par minute.
_price_cache: Dict[str, dict] = {}
_PRICE_TTL = 60   # 1 minute

# ── Market context cache ───────────────────────────────────────────────────────
_mkt_ctx_cache: dict = {}
_MKT_CTX_TTL = 300   # 5 min
_mkt_ctx_lock = threading.Lock()


def _ts_to_iso(ts: float | int | None) -> Optional[str]:
    if not ts:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _cache_state(ts: float | int | None, ttl_seconds: int) -> str:
    if not ts:
        return "empty"
    try:
        age = _time.time() - float(ts)
    except Exception:
        return "unknown"
    return "warm" if age < ttl_seconds else "stale"


def _actions_cache_snapshot() -> Dict[str, Any]:
    screener_ts = max((v.get("ts", 0) for v in _screener_cache.values()), default=0)
    price_ts = max((v.get("ts", 0) for v in _price_cache.values()), default=0)
    edge_ts = max((v.get("ts", 0) for v in _ticker_edge_module._edge_cache.values()), default=0)
    regime_ts = _regime_engine_module._cache.get("ts", 0) or _market_regime_cache.get("ts", 0)
    market_context_ts = _mkt_ctx_cache.get("ts", 0) or _market_context_module._context_cache.get("ts", 0)
    edge_status = strategy_edge_status()
    default_cache = _screener_cache.get(_default_screener_cache_key(), {})
    default_results = default_cache.get("data", []) if isinstance(default_cache, dict) else []
    warmup_state = _warmup_progress.get("actions", {})
    return {
        "ohlcv_cache_count": len(_ohlcv_cache),
        "price_cache_count": len(_price_cache),
        "screener_cache_count": len(_screener_cache),
        "screener_results_count": len(default_results),
        "regime_cache_status": _cache_state(regime_ts, 3600),
        "market_context_cache_status": _cache_state(market_context_ts, _MKT_CTX_TTL),
        "edge_cache_coverage": edge_status.get("coverage_pct", 0.0),
        "last_screener_update": _ts_to_iso(screener_ts),
        "last_price_update": _ts_to_iso(price_ts),
        "last_regime_update": _ts_to_iso(regime_ts),
        "last_market_context_update": _ts_to_iso(market_context_ts),
        "last_edge_update": _ts_to_iso(edge_ts),
        "warmup_progress": {
            "total_tickers": warmup_state.get("total_tickers", len(ALL_TICKERS)),
            "warmed_tickers": warmup_state.get("warmed_tickers", 0),
            "missing_tickers": warmup_state.get("missing_tickers", max(len(ALL_TICKERS) - len(default_results), 0)),
            "estimated_batches_remaining": warmup_state.get("estimated_batches_remaining"),
        },
        "warmup_errors": warmup_state.get("errors", []),
    }


def _crypto_cache_snapshot() -> Dict[str, Any]:
    crypto_freshness = crypto_data_freshness()
    edge_status = crypto_edge_status()
    daily_cache = getattr(_crypto_data_module, "_ohlcv_daily_cache", {})
    h4_cache = getattr(_crypto_data_module, "_ohlcv_4h_cache", {})
    price_cache = getattr(_crypto_data_module, "_price_cache", {})
    screener_cache = getattr(_crypto_service_module, "_screener_cache", {})
    regime_ts = getattr(_crypto_regime_cache, "get", lambda *_: 0)("ts", 0)
    regime_data = getattr(_crypto_regime_cache, "get", lambda *_: {})("data", {}) if _crypto_regime_cache else {}
    regime_status = _cache_state(regime_ts, 3600)
    if isinstance(regime_data, dict) and regime_data.get("data_status") == "MISSING":
        regime_status = "missing"
    return {
        "crypto_ohlcv_cache_count": len(daily_cache),
        "crypto_ohlcv_4h_cache_count": len(h4_cache),
        "crypto_price_cache_count": len(price_cache),
        "crypto_screener_cache_count": len(screener_cache),
        "crypto_regime_cache_status": regime_status,
        "crypto_edge_cache_coverage": edge_status.get("coverage_pct", 0.0),
        "last_crypto_screener_update": _ts_to_iso(crypto_freshness["last_screener_update"]),
        "last_crypto_price_update": _ts_to_iso(crypto_freshness["last_price_update"]),
        "last_crypto_regime_update": _ts_to_iso(crypto_freshness["last_regime_update"]),
        "last_crypto_edge_update": _ts_to_iso(crypto_freshness["last_edge_update"]),
    }


def _run_with_timeout(label: str, fn, timeout_seconds: int, warnings: List[str], errors: List[str]):
    started = _time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            value = future.result(timeout=timeout_seconds)
            duration_ms = round((_time.perf_counter() - started) * 1000, 1)
            return {"ok": True, "value": value, "duration_ms": duration_ms}
        except FuturesTimeoutError:
            future.cancel()
            warnings.append(f"{label}: timeout after {timeout_seconds}s")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:200]}")
    duration_ms = round((_time.perf_counter() - started) * 1000, 1)
    return {"ok": False, "value": None, "duration_ms": duration_ms}


class TradeJournalCreateRequest(BaseModel):
    id: Optional[str] = None
    universe: Optional[str] = None
    symbol: Optional[str] = None
    sector: Optional[str] = None
    setup_grade: Optional[str] = None
    signal_type: Optional[str] = None
    strategy_name: Optional[str] = None
    edge_status: Optional[str] = None
    final_decision: Optional[str] = None
    execution_authorized: bool = False
    status: str = "WATCHLIST"
    direction: str = "LONG"
    entry_plan: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    trailing_stop: Optional[float] = None
    position_size: Optional[str] = None
    risk_amount: Optional[float] = None
    risk_pct: Optional[float] = None
    quantity: Optional[float] = None
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_amount: Optional[float] = None
    pnl_pct: Optional[float] = None
    r_multiple: Optional[float] = None
    notes: Optional[str] = None
    source_snapshot: Optional[Dict[str, Any]] = None


class TradeJournalUpdateRequest(BaseModel):
    status: Optional[str] = None
    universe: Optional[str] = None
    symbol: Optional[str] = None
    sector: Optional[str] = None
    setup_grade: Optional[str] = None
    signal_type: Optional[str] = None
    strategy_name: Optional[str] = None
    edge_status: Optional[str] = None
    final_decision: Optional[str] = None
    execution_authorized: Optional[bool] = None
    direction: Optional[str] = None
    entry_plan: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    trailing_stop: Optional[float] = None
    position_size: Optional[str] = None
    risk_amount: Optional[float] = None
    risk_pct: Optional[float] = None
    quantity: Optional[float] = None
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_amount: Optional[float] = None
    pnl_pct: Optional[float] = None
    r_multiple: Optional[float] = None
    notes: Optional[str] = None
    source_snapshot: Optional[Dict[str, Any]] = None


class TradeJournalCloseRequest(BaseModel):
    closed_at: Optional[str] = None
    exit_price: float
    exit_reason: str = "MANUAL"
    notes: Optional[str] = None


class TradeJournalOpenRequest(BaseModel):
    opened_at: Optional[str] = None
    entry_price: Optional[float] = None
    quantity: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_pct: Optional[float] = None
    notes: Optional[str] = None


class TradeJournalPatchRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    trailing_stop: Optional[float] = None
    entry_plan: Optional[float] = None
    entry_price: Optional[float] = None
    quantity: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_pct: Optional[float] = None
    source_snapshot: Optional[Dict[str, Any]] = None


def _get_ohlcv(ticker: str, allow_download: bool = True) -> Optional[object]:
    """
    Retourne le DataFrame OHLCV historique (26 mois, daily).
    Cache 4h — les indicateurs ne changent pas en intraday.
    """
    now   = _time.time()
    entry = _ohlcv_cache.get(ticker)
    if entry and ((now - entry["ts"]) < _OHLCV_TTL or not allow_download):
        return entry["df"]
    if not allow_download:
        return None
    try:
        def _download():
            return yf.download(
                ticker,
                period="26mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                timeout=_OHLCV_FETCH_TIMEOUT,
            )

        ex = ThreadPoolExecutor(max_workers=1)
        future = ex.submit(_download)
        try:
            df = future.result(timeout=_OHLCV_FETCH_TIMEOUT)
        except FuturesTimeoutError:
            future.cancel()
            ex.shutdown(wait=False, cancel_futures=True)
            return None
        except Exception:
            ex.shutdown(wait=False, cancel_futures=True)
            return None
        else:
            ex.shutdown(wait=False, cancel_futures=True)

        if df is None or df.empty or len(df) < 210:
            return None
        _ohlcv_cache[ticker] = {"df": df, "ts": now}
        return df
    except Exception:
        return None


def _fetch_price_info(ticker: str) -> Optional[dict]:
    """
    Retourne {price, prev_close, change_abs, change_pct} avec cache 60s.
    Utilise fast_info (prix quasi temps réel, 15 min delay) pour le prix actuel,
    et prev_close pour calculer la variation du jour.
    """
    now   = _time.time()
    entry = _price_cache.get(ticker)
    if entry and (now - entry["ts"]) < _PRICE_TTL:
        return entry
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price      = float(fi.last_price)
        prev_close = float(fi.previous_close) if fi.previous_close else price
        if not price or price <= 0:
            return None
        info = {
            "price":      round(price, 2),
            "prev_close": round(prev_close, 2),
            "change_abs": round(price - prev_close, 2),
            "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0.0,
            "ts":         now,
        }
        _price_cache[ticker] = info
        return info
    except Exception:
        # Fallback : dernière bougie intraday 2 min
        try:
            df = yf.download(ticker, period="1d", interval="2m",
                             progress=False, auto_adjust=True)
            if df.empty:
                return None
            close = df["Close"].squeeze()
            price = float(close.iloc[-1])
            # prev_close via 5d daily
            df5   = yf.download(ticker, period="5d", interval="1d",
                                progress=False, auto_adjust=True)
            prev  = float(df5["Close"].squeeze().iloc[-2]) if len(df5) >= 2 else price
            if price <= 0:
                return None
            info = {
                "price":      round(price, 2),
                "prev_close": round(prev, 2),
                "change_abs": round(price - prev, 2),
                "change_pct": round((price - prev) / prev * 100, 2) if prev > 0 else 0.0,
                "ts":         now,
            }
            _price_cache[ticker] = info
            return info
        except Exception:
            return None


def _get_current_price(ticker: str) -> Optional[float]:
    """Prix seul (utilisé par analyze_ticker)."""
    info = _fetch_price_info(ticker)
    return info["price"] if info else None


def _get_market_ctx(allow_download: bool = True) -> dict:
    """
    Retourne {vix, sector_strength} depuis le cache (TTL 1h).
    Utilisé par analyze_ticker pour les filtres fondamentaux.
    """
    now = _time.time()
    if _mkt_ctx_cache and ((now - _mkt_ctx_cache.get("ts", 0)) < _MKT_CTX_TTL or not allow_download):
        return _mkt_ctx_cache

    with _mkt_ctx_lock:
        now = _time.time()
        if _mkt_ctx_cache and ((now - _mkt_ctx_cache.get("ts", 0)) < _MKT_CTX_TTL or not allow_download):
            return _mkt_ctx_cache

        if not allow_download:
            return {
                "vix": _mkt_ctx_cache.get("vix", 20.0) if _mkt_ctx_cache else 20.0,
                "sector_strength": _mkt_ctx_cache.get("sector_strength", {}) if _mkt_ctx_cache else {},
                "ts": _mkt_ctx_cache.get("ts", now) if _mkt_ctx_cache else now,
            }

        try:
            # Fast path for screener: only fetch the fields actually used by
            # analyze_ticker (VIX + sector strength). Full market breadth is
            # reserved for the dedicated /api/market-context endpoint.
            _mkt_ctx_cache.update({
                "vix":              _fetch_vix(),
                "sector_strength":  _fetch_sector_strength(),
                "ts":               now,
            })
        except Exception:
            _mkt_ctx_cache.setdefault("vix", 20.0)
            _mkt_ctx_cache.setdefault("sector_strength", {})
            _mkt_ctx_cache["ts"] = now

    return _mkt_ctx_cache


# ── S&P500 perf ──────────────────────────────────────────────────────────────

def fetch_sp500_perf():
    global _sp500_perf_3m, _sp500_perf_6m
    try:
        df = yf.download("^GSPC", period="8mo", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            close = df["Close"].squeeze()
            _sp500_perf_3m = perf_pct(close, 63)
            _sp500_perf_6m = perf_pct(close, 126)
    except Exception:
        pass


def build_screener_cache_key(
    strategy: str,
    exclude_earnings: bool,
    sector: Optional[str],
    min_score: int,
    signal: Optional[str],
) -> str:
    return f"{strategy}|{exclude_earnings}|{sector or ''}|{min_score}|{signal or ''}"


def _default_screener_cache_key() -> str:
    return build_screener_cache_key("standard", False, None, 0, None)


def _merge_screener_cache_results(base_key: str, results: List[object], *, ts: Optional[float] = None, meta: Optional[dict] = None) -> List[object]:
    now = ts or _time.time()
    existing = _screener_cache.get(base_key, {})
    existing_data = existing.get("data", []) if isinstance(existing, dict) else []
    merged: List[object] = []
    seen = set()

    for item in list(existing_data) + list(results):
        ticker = getattr(item, "ticker", None)
        if ticker is None and isinstance(item, dict):
            ticker = item.get("ticker")
        ticker_key = str(ticker).upper() if ticker else None
        if ticker_key and ticker_key in seen:
            continue
        if ticker_key:
            seen.add(ticker_key)
        merged.append(item)

    if merged:
        _screener_cache[base_key] = {
            "ts": now,
            "data": merged,
            "meta": meta or {},
        }
    return merged


def _warm_default_screener_cache_async():
    global _screener_warming

    with _screener_warm_lock:
        if _screener_warming:
            return
        cached = _screener_cache.get(_default_screener_cache_key())
        if cached and (_time.time() - cached.get("ts", 0)) < _SCREENER_TTL:
            return
        _screener_warming = True

    def _runner():
        global _screener_warming
        try:
            screener(sector=None, min_score=0, signal=None, strategy="standard", exclude_earnings=False)
        except Exception as exc:
            print(f"[screener-warm] {type(exc).__name__}: {str(exc)[:200]}")
        finally:
            with _screener_warm_lock:
                _screener_warming = False

    threading.Thread(target=_runner, daemon=True).start()


# ── Market Regime ─────────────────────────────────────────────────────────────

_REGIME_EMPTY = {
    "regime": "UNKNOWN", "spy_price": 0.0, "spy_sma50": 0.0,
    "spy_sma200": 0.0, "spy_rsi": 0.0, "spy_perf_1m": 0.0,
    "data_ok": False, "data_warning": "Données marché indisponibles",
}


def _compute_market_regime() -> dict:
    try:
        df = yf.download("SPY", period="14mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 210:
            return {**_REGIME_EMPTY, "data_warning": "SPY : historique insuffisant (< 210 barres)"}

        close     = df["Close"].squeeze()
        spy_price = float(close.iloc[-1])
        spy_sma50 = float(sma(close, 50).iloc[-1])
        spy_sma200= float(sma(close, 200).iloc[-1])
        spy_rsi_v = float(rsi(close, 14).iloc[-1])
        spy_p1m   = perf_pct(close, 21)

        # Validation des valeurs (jamais afficher des zéros silencieux)
        if spy_price <= 0 or spy_sma50 <= 0 or spy_sma200 <= 0:
            return {**_REGIME_EMPTY, "data_warning": "SPY : valeurs calculées invalides"}

        if spy_price > spy_sma200 and spy_price > spy_sma50 and spy_rsi_v > 50:
            regime = "BULL"
        elif spy_price < spy_sma200:
            regime = "BEAR"
        else:
            regime = "RANGE"

        return {
            "regime":       regime,
            "spy_price":    round(spy_price, 2),
            "spy_sma50":    round(spy_sma50, 2),
            "spy_sma200":   round(spy_sma200, 2),
            "spy_rsi":      round(spy_rsi_v, 1),
            "spy_perf_1m":  round(spy_p1m, 2),
            "data_ok":      True,
            "data_warning": None,
        }
    except Exception as e:
        return {**_REGIME_EMPTY, "data_warning": f"SPY fetch failed: {str(e)[:80]}"}


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScoreDetail(BaseModel):
    trend:             int   # /30
    momentum:          int   # /25
    risk_reward:       int   # /20
    relative_strength: int   # /15
    volume_quality:    int   # /10
    details:           Dict[str, bool]


class TickerResult(BaseModel):
    ticker:        str
    sector:        str
    price:         float
    score:         int
    # ── Système de grades ─────────────────────────────────────────────────
    setup_grade:   str      # "A+" | "A" | "B" | "REJECT"
    setup_reason:  str
    confidence:    int      # 0–100
    quality_score: int      # 0–100 — timing quality (distinct du score global)
    # ── Rétrocompat ───────────────────────────────────────────────────────
    category:      str
    signal_type:   str
    position_size: str
    # ── Niveaux dynamiques ─────────────────────────────────────────────────
    entry:         float
    stop_loss:     float
    sl_type:       str      # "ATR" | "Structure"
    tp1:           float
    tp2:           float
    take_profit:   float
    trailing_stop: float
    resistance:    float
    support:       float
    high_52w:      float
    rr_ratio:      float
    # ── Métriques ─────────────────────────────────────────────────────────
    risk_now_pct:   float
    dist_entry_pct: float
    trend_status:   str
    sma50:          float
    sma200:         float
    rsi_val:        float
    macd_val:       float
    atr_val:        float
    perf_3m:        float
    perf_6m:        float
    score_detail:   ScoreDetail
    # ── Earnings ──────────────────────────────────────────────────────────
    earnings_date:    Optional[str]  = None
    earnings_days:    Optional[int]  = None
    earnings_warning: bool           = False
    # ── Setup status (indépendant du marché ouvert/fermé) ─────────────────
    setup_status:     str            = "READY"   # READY | WAIT | INVALID
    # ── Strategy fit ──────────────────────────────────────────────────────
    strategy_fit:     str            = "PULLBACK" # BREAKOUT | PULLBACK | MEAN_REVERSION
    # ── Filtres fondamentaux ──────────────────────────────────────────────
    risk_filters_status: str         = "OK"      # OK | CAUTION | BLOCKED
    risk_filter_reasons: List[str]   = []
    fundamental_risk:    str         = "LOW"     # LOW | MEDIUM | HIGH
    news_risk:           str         = "LOW"     # LOW | MEDIUM | HIGH
    sector_rank:         str         = "NEUTRAL" # STRONG | NEUTRAL | WEAK
    vix_risk:            str         = "LOW"     # LOW | MEDIUM | HIGH
    final_decision:      str         = "WAIT"    # BUY | WAIT | SKIP
    # ── Tradabilité (qualité > quantité) ─────────────────────────────────
    tradable:            bool        = True
    rejection_reason:    str         = ""
    # ── Strategy Edge per Ticker ──────────────────────────────────────────
    ticker_edge_status:  str         = "NO_EDGE"   # STRONG_EDGE | VALID_EDGE | WEAK_EDGE | OVERFITTED | NO_EDGE
    best_strategy_for_ticker: Optional[str] = None  # clé de la meilleure stratégie
    best_strategy_name:  Optional[str] = None
    best_strategy_color: str         = "#6b7280"
    best_strategy_emoji: str         = ""
    edge_score:          int         = 0            # 0–100
    edge_train_pf:       float       = 0.0
    edge_test_pf:        float       = 0.0
    edge_trades:         int         = 0
    edge_win_rate:       float       = 0.0
    edge_pf:             float       = 0.0
    edge_expectancy:     float       = 0.0
    edge_max_dd:         float       = 0.0
    overfit_warning:     bool        = False
    overfit_reasons:     List[str]   = []
    # ── Final Score composite (edge + setup + RR + regime + execution) ────
    final_score:         int         = 0            # 0–100
    execution_quality:   int         = 0            # 0–100 (proximité entrée)
    error:            Optional[str]  = None


# ── Analyse d'un ticker ───────────────────────────────────────────────────────

def analyze_ticker(
    ticker: str,
    strategy: str = "standard",
    exclude_earnings: bool = False,
    fetch_news: bool = True,
    use_live_price: bool = True,
    fetch_earnings: bool = True,
    fast: bool = False,
    audit: Optional[Counter] = None,
    audit_lock: Optional[threading.Lock] = None,
) -> Optional[TickerResult]:
    def _audit_inc(key: str):
        if audit is not None and audit_lock is not None:
            with audit_lock:
                audit[key] += 1

    try:
        # Utiliser le cache OHLCV (évite re-téléchargement à chaque scan)
        df = _get_ohlcv(ticker, allow_download=not fast)
        if df is None:
            _audit_inc("ohlcv_none")
            return None
        _audit_inc("ohlcv_ok")

        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        # Prix frais (cache 60s) — override le dernier close historique
        fresh_price = _get_current_price(ticker) if use_live_price else None
        price       = fresh_price if fresh_price and fresh_price > 0 else float(close.iloc[-1])
        sma200_val  = float(sma(close, 200).iloc[-1])
        sma50_val   = float(sma(close, 50).iloc[-1])
        rsi_val     = float(rsi(close, 14).iloc[-1])
        macd_line, _, macd_hist_s = macd(close)
        macd_val    = float(macd_line.iloc[-1])
        macd_hist_v = float(macd_hist_s.iloc[-1])
        atr_series  = atr(high, low, close, 14)
        atr_val     = float(atr_series.iloc[-1])
        p3m         = perf_pct(close, 63)
        p6m         = perf_pct(close, 126)
        avg_vol     = avg_volume_30d(volume)

        # ── 1. Filtres éliminatoires ─────────────────────────────────────
        filtered, filter_reason = hard_filter(price, sma200_val, rsi_val, avg_vol, atr_val)
        if filtered:
            _audit_inc("hard_filter")
            return None
        _audit_inc("post_hard")

        # ── 1b. Filtre earnings (configurable) ───────────────────────────
        # Récupérer les earnings en avance (best-effort, non bloquant)
        earnings_date    = None
        earnings_days    = None
        earnings_warning = False
        if fetch_earnings or exclude_earnings:
            try:
                earn = get_earnings_date(ticker)
                earnings_date    = earn.get("date")
                earnings_days    = earn.get("days_until")
                earnings_warning = earn.get("warning", False)
                # Si filtre actif : exclure si earnings dans ≤ 5 jours
                if exclude_earnings and earnings_days is not None and 0 <= earnings_days <= 5:
                    _audit_inc("earnings_block")
                    return None
            except Exception:
                pass

        # ── 2. Niveaux dynamiques ─────────────────────────────────────────
        levels        = compute_dynamic_levels(price, high, low, sma50_val, atr_val)
        entry         = levels["entry"]
        stop_loss     = levels["stop_loss"]
        tp1           = levels["tp1"]
        tp2           = levels["tp2"]
        trailing      = levels["trailing_stop"]
        sl_type       = levels["sl_type"]
        resistance    = levels["resistance"]
        rr_ratio      = levels["rr_ratio"]
        dist_entry    = levels["dist_entry_pct"]
        risk_now      = levels["risk_now_pct"]

        # ── 3. Score professionnel ────────────────────────────────────────
        score, breakdown, details = compute_professional_score(
            price, close, high, low, volume,
            sma50_val, sma200_val, rsi_val, macd_hist_v,
            p3m, p6m,
            entry, stop_loss, resistance,
            _sp500_perf_3m, _sp500_perf_6m,
        )

        # ── 4. Grade & confiance ─────────────────────────────────────────
        setup_grade, setup_reason = classify_setup(score, dist_entry, rr_ratio, rsi_val)

        # Exclure les REJECT du résultat (score < 50)
        if setup_grade == "REJECT":
            _audit_inc("grade_reject")
        elif setup_grade == "B":
            _audit_inc("grade_b")
        elif setup_grade == "A":
            _audit_inc("grade_a")
        elif setup_grade == "A+":
            _audit_inc("grade_a_plus")

        confidence    = compute_confidence(score, rr_ratio, rsi_val)
        quality_score = compute_quality_score(dist_entry, rsi_val, close, atr_val, price)
        signal_type, breakout_valid, breakout_issues = detect_signal_type(
            price, sma50_val, rsi_val, macd_hist_v, high, close, atr_val
        )

        # Support & 52w high
        h52 = _high_52w(high)
        sup = support_level(low, 20)

        # Rétrocompat
        category      = grade_to_category(setup_grade)
        position_size = grade_to_position(setup_grade)
        trend_status  = "En tendance" if price > sma200_val else "Hors tendance"

        score_detail = ScoreDetail(
            trend=breakdown["trend"],
            momentum=breakdown["momentum"],
            risk_reward=breakdown["risk_reward"],
            relative_strength=breakdown["relative_strength"],
            volume_quality=breakdown["volume_quality"],
            details=details,
        )

        # ── Setup status (basé sur qualité du setup, pas marché ouvert) ──────
        # READY   : prix proche de l'entrée (< 2%), bon R/R, grade A/A+
        # WAIT    : prix trop loin de l'entrée ou grade B
        # INVALID : R/R insuffisant ou conditions dégradées
        if setup_grade == "REJECT":
            setup_status = "INVALID"
        elif rr_ratio < 1.5 or dist_entry > 8:
            setup_status = "INVALID"
        elif setup_grade in ("A+", "A") and dist_entry <= 2:
            setup_status = "READY"
        elif dist_entry <= 5:
            setup_status = "WAIT"
        else:
            setup_status = "WAIT"

        # ── 5. Strategy fit ───────────────────────────────────────────────
        _STRATEGY_FIT_MAP = {
            "Breakout":  "BREAKOUT",
            "Momentum":  "BREAKOUT",
            "Pullback":  "PULLBACK",
            "Neutral":   "MEAN_REVERSION",
        }
        strategy_fit = _STRATEGY_FIT_MAP.get(signal_type, "PULLBACK")

        # ── 6. Filtres fondamentaux ────────────────────────────────────────
        mkt_ctx         = _get_market_ctx(allow_download=not fast)
        vix_val         = mkt_ctx.get("vix", 20.0)
        sector_strength = mkt_ctx.get("sector_strength", {})
        regime_str      = _market_regime_cache.get("regime", "UNKNOWN")
        ticker_sector   = TICKER_SECTOR.get(ticker, "Other")

        fund = compute_fundamental_risk(
            ticker           = ticker,
            sector           = ticker_sector,
            earnings_days    = earnings_days,
            earnings_warning = earnings_warning,
            sector_strength  = sector_strength,
            vix_val          = vix_val,
            regime           = regime_str,
            fetch_news       = fetch_news,
        )

        final_decision = compute_final_decision(
            setup_grade  = setup_grade,
            setup_status = setup_status,
            risk_status  = fund["risk_filters_status"],
            rr_ratio     = rr_ratio,
            regime       = regime_str,
            vix_val      = vix_val,
        )

        # ── Tradability (qualité > quantité) ──────────────────────────────
        # Un setup est tradable uniquement si TOUTES les conditions strictes
        # sont réunies. Sinon il reste visible avec sa rejection_reason.
        tradable = True
        rejection_reason = ""

        # 1. Régime de marché — hard filter : BULL_TREND only
        engine_result = compute_regime_engine(fast=fast)
        engine_regime = engine_result.get("regime", "UNKNOWN")
        if strategy_fit != engine_result.get("active_strategy"):
            _audit_inc("strategy_fit_mismatch")
        if engine_regime != "BULL_TREND":
            tradable = False
            _audit_inc("tradability_block_regime")
            rejection_reason = f"Régime {engine_result.get('regime_label', engine_regime)} — seulement BULL_TREND"
        # Pénalité scoring si mauvais régime (déjà appliquée côté scoring si volume faible)
        elif score < 90:
            tradable = False
            _audit_inc("tradability_block_score")
            rejection_reason = f"Score {score}/100 insuffisant (min 90 requis)"
        elif not (55 <= rsi_val <= 70):
            tradable = False
            _audit_inc("tradability_block_rsi")
            rejection_reason = f"RSI {rsi_val:.0f} hors zone optimale (55–70)"
        elif dist_entry > 2.0:
            tradable = False
            _audit_inc("tradability_block_dist")
            rejection_reason = f"Prix {dist_entry:+.1f}% au-dessus de l'entrée (max +2%)"
        elif rr_ratio < 1.5:
            tradable = False
            _audit_inc("tradability_block_rr")
            rejection_reason = f"R/R {rr_ratio:.1f} insuffisant (min 1.5)"
        elif avg_vol < 1_000_000:
            tradable = False
            _audit_inc("tradability_block_vol")
            rejection_reason = f"Liquidité insuffisante ({avg_vol/1_000:.0f}k < 1M)"
        elif signal_type == "Breakout" and not breakout_valid:
            tradable = False
            _audit_inc("tradability_block_breakout")
            main_issue = breakout_issues[0] if breakout_issues else "Breakout invalide"
            rejection_reason = f"Breakout non qualifié : {main_issue}"
        # Relative strength : outperformer S&P500 d'au moins 5% sur 3 mois
        elif p3m < _sp500_perf_3m + 5.0:
            tradable = False
            _audit_inc("tradability_block_rs")
            rejection_reason = (
                f"Force relative insuffisante : perf 3m {p3m:+.1f}% vs "
                f"S&P500 {_sp500_perf_3m:+.1f}% (besoin de +5% d'avance)"
            )

        if tradable:
            _audit_inc("tradable_yes")
        else:
            _audit_inc("tradable_no")

        # ── 7. Strategy Edge (cache uniquement — non bloquant) ──────────────
        try:
            edge_data    = get_cached_edge(ticker) or {}
            te_status    = edge_data.get("ticker_edge_status",  "NO_EDGE")
            best_strat   = edge_data.get("best_strategy",       None)
            best_s_name  = edge_data.get("best_strategy_name",  None)
            best_s_color = edge_data.get("best_strategy_color", "#6b7280")
            best_s_emoji = edge_data.get("best_strategy_emoji", "")
            edge_sc      = int(edge_data.get("edge_score",      0))
            edge_train_p = float(edge_data.get("train_pf",      0.0))
            edge_test_p  = float(edge_data.get("test_pf",       0.0))
            edge_trades_ = int(edge_data.get("total_trades",    0))
            edge_wr      = float(edge_data.get("win_rate",      0.0))
            edge_pf_     = float(edge_data.get("pf",            0.0))
            edge_exp     = float(edge_data.get("expectancy",    0.0))
            edge_dd      = float(edge_data.get("max_dd",        0.0))
            overfit_warn = bool(edge_data.get("overfit_warning", False))
            overfit_r    = list(edge_data.get("overfit_reasons", []))
        except Exception:
            te_status = "NO_EDGE"; best_strat = None; best_s_name = None
            best_s_color = "#6b7280"; best_s_emoji = ""; edge_sc = 0
            edge_train_p = 0.0; edge_test_p = 0.0; edge_trades_ = 0
            edge_wr = 0.0; edge_pf_ = 0.0; edge_exp = 0.0; edge_dd = 0.0
            overfit_warn = False; overfit_r = []
        _audit_inc(f"edge_{te_status.lower()}")

        # ── 8. Final Score composite ─────────────────────────────────────────
        final_decision = compute_final_decision(
            setup_grade=setup_grade,
            setup_status=setup_status,
            risk_status=fund["risk_filters_status"],
            rr_ratio=rr_ratio,
            regime=regime_str,
            vix_val=vix_val,
            ticker_edge_status=te_status,
            overfit_warning=overfit_warn,
        )

        _regime_fit  = 1.0 if engine_regime == "BULL_TREND" else \
                       0.6 if engine_regime in ("PULLBACK_TREND", "RANGE") else 0.2
        exec_quality = max(0, int(100 - abs(dist_entry) * 12))
        rr_norm      = min(rr_ratio / 3.0, 1.0)
        final_score  = int(
            0.30 * edge_sc +
            0.25 * score +
            0.20 * (rr_norm * 100) +
            0.15 * (_regime_fit * 100) +
            0.10 * exec_quality
        )

        return TickerResult(
            ticker=ticker,
            sector=TICKER_SECTOR.get(ticker, "Other"),
            price=round(price, 2),
            score=score,
            setup_grade=setup_grade,
            setup_reason=setup_reason,
            confidence=confidence,
            quality_score=quality_score,
            category=category,
            signal_type=signal_type,
            position_size=position_size,
            entry=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            sl_type=sl_type,
            tp1=tp1,
            tp2=tp2,
            take_profit=tp2,
            trailing_stop=trailing,
            resistance=round(resistance, 2),
            support=round(sup, 2),
            high_52w=round(h52, 2),
            rr_ratio=rr_ratio,
            risk_now_pct=round(risk_now, 2),
            dist_entry_pct=round(dist_entry, 2),
            trend_status=trend_status,
            sma50=round(sma50_val, 2),
            sma200=round(sma200_val, 2),
            rsi_val=round(rsi_val, 1),
            macd_val=round(macd_val, 4),
            atr_val=round(atr_val, 2),
            perf_3m=round(p3m, 2),
            perf_6m=round(p6m, 2),
            score_detail=score_detail,
            earnings_date=earnings_date,
            earnings_days=earnings_days,
            earnings_warning=earnings_warning,
            setup_status=setup_status,
            strategy_fit=strategy_fit,
            risk_filters_status=fund["risk_filters_status"],
            risk_filter_reasons=fund["risk_filter_reasons"],
            fundamental_risk=fund["fundamental_risk"],
            news_risk=fund["news_risk"],
            sector_rank=fund["sector_rank"],
            vix_risk=fund["vix_risk"],
            final_decision=final_decision,
            tradable=tradable,
            rejection_reason=rejection_reason,
            # Edge
            ticker_edge_status=te_status,
            best_strategy_for_ticker=best_strat,
            best_strategy_name=best_s_name,
            best_strategy_color=best_s_color,
            best_strategy_emoji=best_s_emoji,
            edge_score=edge_sc,
            edge_train_pf=edge_train_p,
            edge_test_pf=edge_test_p,
            edge_trades=edge_trades_,
            edge_win_rate=edge_wr,
            edge_pf=edge_pf_,
            edge_expectancy=edge_exp,
            edge_max_dd=edge_dd,
            overfit_warning=overfit_warn,
            overfit_reasons=overfit_r,
            # Final score
            final_score=final_score,
            execution_quality=exec_quality,
        )
    except Exception:
        return None


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    fetch_sp500_perf()
    _warm_default_screener_cache_async()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/screener", response_model=List[TickerResult])
def screener(
    sector:           Optional[str] = Query(None),
    min_score:        int           = Query(0),
    signal:           Optional[str] = Query(None),
    strategy:         str           = Query("standard"),
    exclude_earnings: bool          = Query(False),
    fast:             bool          = Query(False),
):
    cache_key = build_screener_cache_key(strategy, exclude_earnings, sector, min_score, signal)
    now = _time.time()
    cached = _screener_cache.get(cache_key)
    if cached and ((now - cached.get("ts", 0)) < _SCREENER_TTL or fast):
        return cached["data"]

    if not fast:
        fetch_sp500_perf()
        # Warm shared caches once to avoid N threads recomputing the same
        # expensive market context during the bulk screener scan.
        try:
            _ = _get_market_ctx()
        except Exception:
            pass
        try:
            _ = compute_regime_engine()
        except Exception:
            pass
    results = []
    audit = Counter()
    audit_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(analyze_ticker, t, strategy, exclude_earnings, False, False, False, fast, audit, audit_lock): t
            for t in ALL_TICKERS
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as exc:
                with audit_lock:
                    audit["errors"] += 1
                print(f"[screener] {ticker}: {type(exc).__name__}: {str(exc)[:200]}")
                continue

    if sector:
        results = [r for r in results if r.sector == sector]
    if min_score > 0:
        results = [r for r in results if r.score >= min_score]
    if signal:
        results = [r for r in results if r.signal_type == signal]

    print(
        f"[screener] total={len(ALL_TICKERS)} "
        f"ohlcv_ok={audit['ohlcv_ok']} ohlcv_none={audit['ohlcv_none']} "
        f"post_hard={audit['post_hard']} hard_filter={audit['hard_filter']} earnings_block={audit['earnings_block']} "
        f"strategy_fit_mismatch={audit['strategy_fit_mismatch']} "
        f"edge_no_edge={audit['edge_no_edge']} edge_valid_edge={audit['edge_valid_edge']} edge_strong_edge={audit['edge_strong_edge']} "
        f"tradable_yes={audit['tradable_yes']} tradable_no={audit['tradable_no']} "
        f"tradability_block_regime={audit['tradability_block_regime']} tradability_block_score={audit['tradability_block_score']} "
        f"tradability_block_rsi={audit['tradability_block_rsi']} tradability_block_dist={audit['tradability_block_dist']} "
        f"grade_reject={audit['grade_reject']} grade_b={audit['grade_b']} grade_a={audit['grade_a']} grade_a_plus={audit['grade_a_plus']} "
        f"errors={audit['errors']} returned={len(results)}"
    )

    results.sort(key=lambda x: (x.score, x.confidence), reverse=True)
    if fast and results:
        _screener_cache[cache_key] = {"ts": _time.time(), "data": results}
        return results

    # ── Logging automatique des signaux ───────────────────────────────────────
    try:
        # Mise à jour des outcomes via OHLC (barre par barre, même logique que
        # le Portfolio Backtest Engine — pas de snapshot instantané)
        ohlc_map = {
            t: entry["df"]
            for t, entry in _ohlcv_cache.items()
            if entry.get("df") is not None
        }
        if ohlc_map:
            update_outcomes_ohlc(ohlc_map)
        else:
            # Fallback snapshot si le cache n'est pas encore rempli
            update_outcomes({r.ticker: r.price for r in results})

        for r in results:
            log_signal(
                ticker=r.ticker,
                price=r.price,
                entry=r.entry,
                stop_loss=r.stop_loss,
                tp1=r.tp1,
                tp2=r.tp2,
                grade=r.setup_grade,
                score=r.score,
                confidence=r.confidence,
                rr=r.rr_ratio,
                signal_type=r.signal_type,
                strategy=strategy,
            )
    except Exception:
        pass

    if results:
        _screener_cache[cache_key] = {"ts": _time.time(), "data": results}
    return results


@app.get("/api/screener/{ticker}", response_model=TickerResult)
def screener_single(ticker: str, strategy: str = Query("standard")):
    fetch_sp500_perf()
    res = analyze_ticker(ticker.upper(), strategy)
    if res is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ticker non trouvé ou filtré")
    return res


@app.get("/api/sectors")
def get_sectors():
    return {"sectors": list(TICKERS.keys())}


@app.get("/api/tickers")
def get_tickers():
    return {"tickers": ALL_TICKERS, "by_sector": TICKERS}


# ── Market Regime ─────────────────────────────────────────────────────────────

@app.get("/api/market-regime")
def market_regime():
    global _market_regime_cache
    now = _time.time()
    if _market_regime_cache and (now - _market_regime_cache.get("ts", 0)) < 3600:
        return _market_regime_cache["data"]
    data = _compute_market_regime()
    _market_regime_cache = {"ts": now, "data": data}
    return data


@app.get("/api/data-freshness")
def data_freshness(scope: str = Query("actions")):
    if scope.lower() == "crypto":
        crypto = crypto_data_freshness()
        return {
            "price_label": crypto["price_label"],
            "screener_label": crypto["screener_label"],
            "regime_label": crypto["regime_label"],
            "market_context_label": crypto["market_context_label"],
            "edge_label": crypto["edge_label"],
            "price_ttl_seconds": crypto["price_ttl_seconds"],
            "screener_ttl_seconds": crypto["screener_ttl_seconds"],
            "regime_ttl_seconds": crypto["regime_ttl_seconds"],
            "market_context_ttl_seconds": crypto["market_context_ttl_seconds"],
            "edge_ttl_seconds": crypto["edge_ttl_seconds"],
            "last_price_update": _ts_to_iso(crypto["last_price_update"]),
            "last_screener_update": _ts_to_iso(crypto["last_screener_update"]),
            "last_regime_update": _ts_to_iso(crypto["last_regime_update"]),
            "last_market_context_update": _ts_to_iso(crypto["last_market_context_update"]),
            "last_edge_update": _ts_to_iso(crypto["last_edge_update"]),
        }

    screener_ts = max((v.get("ts", 0) for v in _screener_cache.values()), default=0)
    price_ts = max((v.get("ts", 0) for v in _price_cache.values()), default=0)
    edge_ts = max((v.get("ts", 0) for v in _ticker_edge_module._edge_cache.values()), default=0)
    regime_ts = _regime_engine_module._cache.get("ts", 0) or _market_regime_cache.get("ts", 0)
    market_context_ts = _mkt_ctx_cache.get("ts", 0) or _market_context_module._context_cache.get("ts", 0)

    return {
        "price_label": "Prix live approximatif / différé (rafraîchi 30–60s)",
        "screener_label": "Analyse daily (cache 4h ou recalcul manuel)",
        "regime_label": "Market regime (cache 1h)",
        "market_context_label": "Market context (cache 5min)",
        "edge_label": "Strategy Edge (cache 24h)",
        "price_ttl_seconds": _PRICE_TTL,
        "screener_ttl_seconds": _OHLCV_TTL,
        "regime_ttl_seconds": 3600,
        "market_context_ttl_seconds": _MKT_CTX_TTL,
        "edge_ttl_seconds": getattr(_ticker_edge_module, "_EDGE_TTL", 86_400),
        "last_price_update": _ts_to_iso(price_ts),
        "last_screener_update": _ts_to_iso(screener_ts),
        "last_regime_update": _ts_to_iso(regime_ts),
        "last_market_context_update": _ts_to_iso(market_context_ts),
        "last_edge_update": _ts_to_iso(edge_ts),
    }



# ── Clear cache (force refresh immédiat de tous les prix) ────────────────────

@app.post("/api/clear-cache")
def clear_cache(
    scope: str = Query("all"),
    _: None = Depends(require_admin_key),
):
    """
    Vide le cache OHLCV + contexte marché.
    Le prochain appel au screener récupère les prix frais depuis yfinance.
    """
    normalized = (scope or "all").strip().lower()
    if normalized not in {"actions", "crypto", "all"}:
        normalized = "all"

    if normalized in {"actions", "all"}:
        _price_cache.clear()   # prix actuels → prochaine lecture sera fraîche
        _mkt_ctx_cache.clear()
        _cache.clear()
        _screener_cache.clear()
        _market_regime_cache.clear()
        _regime_engine_module._cache.clear()
        _market_context_module._context_cache.clear()
        _warmup_progress.pop("actions", None)

    if normalized in {"crypto", "all"}:
        _crypto_regime_cache.clear()
        clear_crypto_screener_cache()
        clear_crypto_caches()
        clear_crypto_edge_cache()
    # NE PAS vider _ohlcv_cache : les indicateurs (SMA/RSI) sont stables 4h
    return {"cleared": True, "scope": normalized, "message": "Cache vidé — les prochains prix seront frais"}


# ── Prix en temps réel ────────────────────────────────────────────────────────

@app.get("/api/prices")
def get_prices(tickers: str = Query(..., description="Tickers séparés par virgule, ex: AAPL,MSFT")):
    """
    Retourne le prix actuel + variation journalière pour une liste de tickers.
    Cache 60s par ticker — fetch léger (5 jours) indépendant du screener lourd.
    Conçu pour être appelé toutes les 15s depuis le frontend.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()][:60]
    if not ticker_list:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_fetch_price_info, t): t for t in ticker_list}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                info = future.result()
                if info:
                    results.append({
                        "ticker":     ticker,
                        "price":      info["price"],
                        "change_abs": info["change_abs"],
                        "change_pct": info["change_pct"],
                    })
            except Exception:
                pass

    return results


# ── Regime Engine (5 états + stratégie active) ────────────────────────────────

@app.get("/api/regime-engine")
def regime_engine():
    """
    Retourne le régime de marché avancé (5 états) + la stratégie active unique.
    Cache 1h côté serveur.
    """
    return compute_regime_engine()


# Scope: CRYPTO
@app.get("/api/crypto/universe")
def crypto_universe():
    return {"symbols": CRYPTO_SYMBOLS, "sectors": CRYPTO_SECTORS}


# Scope: CRYPTO
@app.get("/api/crypto/debug-data")
def crypto_debug_data(_: None = Depends(require_admin_key)):
    return debug_crypto_sources()


# Scope: CRYPTO
@app.get("/api/crypto/regime")
def crypto_regime():
    return compute_crypto_regime()


# Scope: CRYPTO
@app.get("/api/crypto/screener")
def crypto_screener_endpoint(
    sector: Optional[str] = Query(None),
    min_score: int = Query(0),
    signal: Optional[str] = Query(None),
    fast: bool = Query(False),
):
    return crypto_screener(sector=sector, min_score=min_score, signal=signal, fast=fast)


# Scope: CRYPTO
@app.get("/api/crypto/prices")
def crypto_prices_endpoint(symbols: str = Query(..., description="BTC,ETH,SOL")):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:50]
    return crypto_prices(symbol_list)


# Scope: CRYPTO
@app.get("/api/crypto/edge/{symbol}")
def crypto_edge_endpoint(symbol: str):
    if symbol.upper() == "STATUS":
        return crypto_edge_status()
    return compute_crypto_edge(symbol.upper())


# Scope: CRYPTO
@app.post("/api/crypto/edge/compute")
def compute_crypto_edge_endpoint(
    symbols: Optional[str] = Query(None),
    _: None = Depends(require_admin_key),
):
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols else CRYPTO_SYMBOLS
    )
    computed = 0
    errors = 0
    for symbol in symbol_list:
        try:
            compute_crypto_edge(symbol)
            computed += 1
        except Exception:
            errors += 1
    return {
        "status": "ok",
        "computed": computed,
        "errors": errors,
        "total": len(symbol_list),
        "message": f"Crypto edge calculé pour {computed}/{len(symbol_list)} symboles",
    }


# Scope: CRYPTO
@app.get("/api/crypto/edge/status")
def crypto_edge_status():
    now = _time.time()
    valid = sum(1 for v in _crypto_edge_cache.values() if (now - v.get("ts", 0)) < 86_400)
    by_status: Dict[str, int] = {}
    for v in _crypto_edge_cache.values():
        status = v.get("data", {}).get("ticker_edge_status", "NO_EDGE")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "cached_symbols": len(_crypto_edge_cache),
        "valid_symbols": valid,
        "total_symbols": len(CRYPTO_SYMBOLS),
        "coverage_pct": round(valid / max(len(CRYPTO_SYMBOLS), 1) * 100, 1),
        "by_status": by_status,
    }


# ── Backtest ──────────────────────────────────────────────────────────────────

class BacktestResultModel(BaseModel):
    ticker:          str
    total_trades:    int
    wins:            int
    losses:          int
    win_rate:        float
    avg_gain_pct:    float
    avg_loss_pct:    float
    expectancy:      float
    max_drawdown_pct:float
    best_trade_pct:  float
    worst_trade_pct: float
    total_return_pct:float
    avg_duration_days:float
    reliable:        bool
    trades:          List[dict]
    error:           Optional[str] = None


class BacktestSummary(BaseModel):
    results:               List[BacktestResultModel]
    global_win_rate:       float
    global_expectancy:     float
    global_total_trades:   int
    global_reliable_count: int
    best_ticker:           str
    worst_ticker:          str
    # Simulation portfolio réaliste (même moteur que Strategy Lab)
    portfolio:             Optional[dict] = None


def _run_one_backtest(ticker: str, df, strategy: str = "standard") -> BacktestResultModel:
    """Lance run_backtest sur un DataFrame pré-téléchargé."""
    try:
        if df is None or df.empty or len(df) < 210:
            return BacktestResultModel(
                ticker=ticker, total_trades=0, wins=0, losses=0,
                win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
                expectancy=0, max_drawdown_pct=0,
                best_trade_pct=0, worst_trade_pct=0,
                total_return_pct=0, avg_duration_days=0,
                reliable=False, trades=[], error="Données insuffisantes",
            )
        res = run_backtest(ticker, df, strategy)
        return BacktestResultModel(
            ticker=res.ticker, total_trades=res.total_trades,
            wins=res.wins, losses=res.losses, win_rate=res.win_rate,
            avg_gain_pct=res.avg_gain_pct, avg_loss_pct=res.avg_loss_pct,
            expectancy=res.expectancy, max_drawdown_pct=res.max_drawdown_pct,
            best_trade_pct=res.best_trade_pct, worst_trade_pct=res.worst_trade_pct,
            total_return_pct=res.total_return_pct, avg_duration_days=res.avg_duration_days,
            reliable=res.reliable, trades=res.trades, error=res.error,
        )
    except Exception as e:
        return BacktestResultModel(
            ticker=ticker, total_trades=0, wins=0, losses=0,
            win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
            expectancy=0, max_drawdown_pct=0,
            best_trade_pct=0, worst_trade_pct=0,
            total_return_pct=0, avg_duration_days=0,
            reliable=False, trades=[], error=str(e),
        )


@app.get("/api/backtest", response_model=BacktestSummary)
def backtest_all(
    strategy: str = Query("standard"),
    period: int = Query(12),
    _: None = Depends(require_admin_key),
):
    """
    Backtest sur tous les tickers.
    Utilise le cache OHLCV (2h) — relance un téléchargement si expiré.
    Les résultats passent dans run_portfolio_backtest pour des métriques réalistes.
    """
    # ── Téléchargement / cache ────────────────────────────────────────────────
    yf_period  = "26mo" if period >= 24 else "14mo"
    min_bars   = 420   if period >= 24 else 210

    data_map: Dict[str, object] = {}

    def _fetch(ticker: str):
        df = _get_ohlcv(ticker)
        # _get_ohlcv utilise period="26mo" ; pour le backtest 12 mois c'est suffisant
        return ticker, df

    with ThreadPoolExecutor(max_workers=16) as ex:
        for ticker, df in ex.map(_fetch, ALL_TICKERS):
            if df is not None and len(df) >= min_bars:
                data_map[ticker] = df

    # ── Backtest par ticker ───────────────────────────────────────────────────
    all_portfolio_trades: list = []
    results: List[BacktestResultModel] = []

    def _run(ticker: str):
        r = _run_one_backtest(ticker, data_map.get(ticker), strategy)
        # Enrichir les trade dicts avec le ticker pour le portfolio engine
        enriched = [
            {**t, "ticker": ticker}
            for t in (r.trades or [])
            if t.get("exit_reason") != "OPEN"   # exclure les trades encore ouverts
        ]
        return r, enriched

    with ThreadPoolExecutor(max_workers=16) as ex:
        for r, trades in ex.map(_run, list(data_map.keys())):
            results.append(r)
            all_portfolio_trades.extend(trades)

    results.sort(key=lambda x: x.total_return_pct, reverse=True)

    valid           = [r for r in results if r.total_trades > 0 and not r.error]
    global_trades   = sum(r.total_trades for r in valid)
    global_wins     = sum(r.wins for r in valid)
    global_win_rate = round(global_wins / global_trades * 100, 1) if global_trades else 0.0
    global_exp      = round(float(np.mean([r.expectancy for r in valid])), 2) if valid else 0.0
    reliable_count  = sum(1 for r in valid if r.reliable)

    # ── Simulation portfolio réaliste ─────────────────────────────────────────
    portfolio = run_portfolio_backtest(all_portfolio_trades, period_months=period)

    return BacktestSummary(
        results=results,
        global_win_rate=global_win_rate,
        global_expectancy=global_exp,
        global_total_trades=global_trades,
        global_reliable_count=reliable_count,
        best_ticker=results[0].ticker if results else "—",
        worst_ticker=results[-1].ticker if results else "—",
        portfolio=portfolio,
    )


@app.get("/api/backtest/{ticker}", response_model=BacktestResultModel)
def backtest_single(ticker: str, strategy: str = Query("standard")):
    df = _get_ohlcv(ticker.upper())
    return _run_one_backtest(ticker.upper(), df, strategy)


# Scope: CRYPTO
@app.get("/api/crypto/backtest")
def crypto_backtest_all(
    strategy: str = Query("pullback_uptrend"),
    period: int = Query(12),
    _: None = Depends(require_admin_key),
):
    summary = compute_crypto_strategy_lab(period_months=period)
    strategy_row = next((row for row in summary["strategies"] if row["key"] == strategy), None)
    if strategy_row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Stratégie crypto inconnue: {strategy}")
    return {
        "strategy": strategy,
        "period_months": period,
        "summary": strategy_row,
        "results": strategy_row.get("per_symbol", []),
    }


# Scope: CRYPTO
@app.get("/api/crypto/backtest/{symbol}")
def crypto_backtest_single(
    symbol: str,
    strategy: str = Query("pullback_uptrend"),
    period: int = Query(12),
):
    strategy_map = {row["key"]: row for row in CRYPTO_LAB_STRATEGIES}
    strategy_def = strategy_map.get(strategy)
    if not strategy_def:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Stratégie crypto inconnue: {strategy}")
    return evaluate_crypto_strategy_for_symbol(
        symbol.upper(),
        strategy_def,
        period_months=period,
        regime="CRYPTO_BULL",
    )


# ── API Status ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    import os
    from sentiment import _cache as sent_cache, CACHE_TTL

    r_id     = os.getenv("REDDIT_CLIENT_ID", "")
    r_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    r_agent  = os.getenv("REDDIT_USER_AGENT", "")
    x_token  = os.getenv("X_BEARER_TOKEN", "")

    reddit_missing  = [v for v, val in [
        ("REDDIT_CLIENT_ID", r_id), ("REDDIT_CLIENT_SECRET", r_secret), ("REDDIT_USER_AGENT", r_agent),
    ] if not val]
    twitter_missing = ["X_BEARER_TOKEN"] if not x_token else []

    now = _time.time()
    cache_info = [
        {"ticker": t, "age_minutes": round((now - v["ts"]) / 60, 1), "expires_in": round((CACHE_TTL - (now - v["ts"])) / 60, 1)}
        for t, v in sent_cache.items()
    ]

    return {
        "reddit":  {"configured": not reddit_missing,  "missing_vars": reddit_missing},
        "twitter": {"configured": not twitter_missing, "missing_vars": twitter_missing},
        "all_configured": not reddit_missing and not twitter_missing,
        "sentiment_cache": {"entries": len(sent_cache), "ttl_minutes": CACHE_TTL // 60, "tickers": cache_info},
    }


# ── Social Sentiment ──────────────────────────────────────────────────────────

@app.get("/api/social-sentiment")
def social_sentiment(ticker: str = Query(...)):
    return get_sentiment(ticker.upper())


# ── Strategy Lab ──────────────────────────────────────────────────────────────

@app.get("/api/strategy-lab")
def strategy_lab_endpoint(
    period: int = Query(12),
    _: None = Depends(require_admin_key),
):
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    data_cache: Dict[str, object] = {}

    def _download(ticker: str):
        try:
            df = yf.download(ticker, period=yf_period, interval="1d", progress=False, auto_adjust=True)
            if not df.empty and len(df) >= min_bars:
                return ticker, df
        except Exception:
            pass
        return ticker, None

    with ThreadPoolExecutor(max_workers=12) as ex:
        for ticker, df in ex.map(_download, ALL_TICKERS):
            if df is not None:
                data_cache[ticker] = df

    valid_tickers = list(data_cache.keys())
    lab_results = []

    for strat_def in LAB_STRATEGIES:
        all_trades = []

        def _run_ticker(ticker, _strat=strat_def):
            return backtest_ticker_lab(ticker, data_cache[ticker], _strat, period)

        with ThreadPoolExecutor(max_workers=12) as ex:
            for trades in ex.map(_run_ticker, valid_tickers):
                all_trades.extend(trades)

        result = aggregate_lab_result(strat_def, all_trades, period)
        lab_results.append(result)

    lab_results.sort(key=lambda r: r["score"], reverse=True)

    # ── Classement par critère ────────────────────────────────────────────────
    tradable  = [r for r in lab_results if r.get("tradable_status") == "TRADABLE"]
    confirmed = [r for r in lab_results if r.get("tradable_status") == "À CONFIRMER"]
    eligible  = [r for r in lab_results if r.get("eligible")]

    robust_pool  = tradable or confirmed or eligible or lab_results
    quality_pool = [r for r in robust_pool if not r.get("overfitting_risk", False)] or robust_pool

    def _best(lst, fn, default="—"):
        valid = [r for r in lst if r.get("total_trades", 0) > 0]
        return fn(valid)["key"] if valid else default

    return {
        "strategies":          lab_results,
        "best_overall":        _best(robust_pool,  lambda l: max(l, key=lambda r: r["score"])),
        "best_win_rate":       _best(quality_pool, lambda l: max(l, key=lambda r: r["win_rate"])),
        "best_expectancy":     _best(quality_pool, lambda l: max(l, key=lambda r: r["expectancy"])),
        "best_pf":             _best(quality_pool, lambda l: max(l, key=lambda r: r["profit_factor"])),
        "best_low_dd":         _best(quality_pool, lambda l: min(l, key=lambda r: r["max_drawdown_pct"])),
        "has_robust_strategy": len(tradable) > 0,
        "tradable_count":      len(tradable),
        "confirmed_count":     len(confirmed),
        "period_months":       period,
    }


# Scope: CRYPTO
@app.get("/api/crypto/strategy-lab")
def crypto_strategy_lab_endpoint(
    period: int = Query(12),
    _: None = Depends(require_admin_key),
):
    return compute_crypto_strategy_lab(period_months=period)


# ── Market Context ────────────────────────────────────────────────────────────

@app.get("/api/market-context")
def market_context_endpoint():
    return compute_market_context()


# ── Signal Tracker ────────────────────────────────────────────────────────────

@app.get("/api/signals")
def signals_endpoint(limit: int = Query(200)):
    return {
        "signals": get_signals(limit),
        "stats":   get_signal_stats(),
    }


# ── Setup Stats (validation historique) ──────────────────────────────────────

@app.get("/api/setup-stats/{ticker}")
def setup_stats(
    ticker:  str,
    grade:   str = Query("A+"),
    period:  int = Query(24),
):
    """
    Valide historiquement le setup d'un ticker avec les EXACTES mêmes règles
    que le screener live.
    Télécharge les données si nécessaire (réponse peut prendre 3-5s).
    """
    t = ticker.upper()
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    try:
        df = yf.download(t, period=yf_period, interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < min_bars:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Données insuffisantes")

        return validate_setup(
            ticker=t,
            df=df,
            grade_filter=grade,
            sp500_perf_3m=_sp500_perf_3m,
            sp500_perf_6m=_sp500_perf_6m,
            period_months=period,
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# ── Earnings ──────────────────────────────────────────────────────────────────

@app.get("/api/earnings/{ticker}")
def earnings_endpoint(ticker: str):
    return get_earnings_date(ticker.upper())


# ── Parameter Optimizer ───────────────────────────────────────────────────────

@app.get("/api/optimizer")
def optimizer_endpoint(
    period: int = Query(12),
    _: None = Depends(require_admin_key),
):
    global _opt_data_cache
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    if not _opt_data_cache:
        def _dl(ticker: str):
            try:
                df = yf.download(ticker, period=yf_period, interval="1d", progress=False, auto_adjust=True)
                if not df.empty and len(df) >= min_bars:
                    return ticker, df
            except Exception:
                pass
            return ticker, None

        with ThreadPoolExecutor(max_workers=12) as ex:
            for ticker, df in ex.map(_dl, ALL_TICKERS):
                if df is not None:
                    _opt_data_cache[ticker] = df

    return run_optimizer(_opt_data_cache, period_months=period)


# ── Strategy Edge per Ticker ──────────────────────────────────────────────────

@app.get("/api/ticker-edge/{ticker}")
def ticker_edge_endpoint(
    ticker: str,
    period: int = Query(24, ge=12, le=60, description="Horizon backtest en mois"),
):
    """
    Calcule (ou retourne depuis le cache 24h) l'edge historique par stratégie pour un ticker.
    Teste les 5 stratégies du Strategy Lab sur 24 mois, split train/test.
    """
    t = ticker.upper()
    df = _get_ohlcv(t)
    if df is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"{t} : données insuffisantes")
    return compute_ticker_edge(t, df, period_months=period)


@app.post("/api/strategy-edge/compute")
def compute_strategy_edge(
    tickers: Optional[str] = Query(None, description="Sous-ensemble tickers séparés par virgule (défaut : tous)"),
    period: int = Query(24, ge=12, le=60, description="Horizon backtest en mois"),
    _: None = Depends(require_admin_key),
):
    """
    Calcule l'edge pour une liste de tickers (ou tous) en parallèle.
    Résultats mis en cache 24h — à appeler manuellement via bouton 'Recalculate Edge'.
    Peut prendre 2-5 minutes pour tous les tickers.
    """
    ticker_list = (
        [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if tickers else ALL_TICKERS
    )

    computed = 0
    errors   = 0

    def _compute_one(t: str):
        nonlocal computed, errors
        df = _get_ohlcv(t)
        if df is None:
            errors += 1
            return
        try:
            compute_ticker_edge(t, df, period_months=period)
            computed += 1
        except Exception:
            errors += 1

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(_compute_one, ticker_list))

    return {
        "status":   "ok",
        "computed": computed,
        "errors":   errors,
        "total":    len(ticker_list),
        "period_months": period,
        "message":  f"Edge calculé pour {computed}/{len(ticker_list)} tickers sur {period} mois (cache 24h)",
    }


@app.get("/api/strategy-edge/results")
def strategy_edge_results(
    tickers: str = Query(..., description="Sous-ensemble tickers séparés par virgule"),
    period: int = Query(24, ge=12, le=60, description="Horizon backtest en mois"),
    compute_missing: bool = Query(False, description="Calcule les edges manquants si absents du cache"),
):
    """
    Retourne les résultats edge pour un sous-ensemble de tickers.
    Utilisé par l'Advanced View pour comparer 24m vs 36m sans changer
    les décisions officielles du screener.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    results: List[Dict[str, Any]] = []

    for t in ticker_list:
        edge = get_cached_edge(t, period_months=period)
        if edge is None and compute_missing:
            df = _get_ohlcv(t)
            if df is None:
                continue
            try:
                edge = compute_ticker_edge(t, df, period_months=period)
            except Exception:
                continue
        if edge is not None:
            results.append(edge)

    return {
        "period_months": period,
        "count": len(results),
        "results": results,
    }


@app.get("/api/strategy-edge/status")
def strategy_edge_status():
    """Retourne l'état du cache edge (combien de tickers ont un edge calculé)."""
    from ticker_edge import _edge_cache, _EDGE_TTL
    now   = _time.time()
    default_cache = {
        k: v for k, v in _edge_cache.items()
        if ":" not in str(k)
    }
    valid = sum(1 for v in default_cache.values() if (now - v.get("ts", 0)) < _EDGE_TTL)
    by_status: Dict[str, int] = {}
    for v in default_cache.values():
        s = v.get("data", {}).get("ticker_edge_status", "NO_EDGE")
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "cached_tickers": len(default_cache),
        "valid_tickers":  valid,
        "cached_period_variants": len(_edge_cache) - len(default_cache),
        "total_tickers":  len(ALL_TICKERS),
        "coverage_pct":   round(valid / max(len(ALL_TICKERS), 1) * 100, 1),
        "by_status":      by_status,
    }


@app.delete("/api/strategy-edge/cache")
def clear_edge_cache(
    ticker: Optional[str] = Query(None),
    _: None = Depends(require_admin_key),
):
    """Vide le cache edge (tout ou un ticker spécifique)."""
    _invalidate_edge_cache(ticker.upper() if ticker else None)
    return {"cleared": True, "ticker": ticker}


@app.get("/api/cache-status")
def cache_status(scope: str = Query("all")):
    normalized = (scope or "all").strip().lower()
    if normalized not in {"actions", "crypto", "all"}:
        normalized = "all"

    payload: Dict[str, Any] = {"scope": normalized}
    if normalized in {"actions", "all"}:
        payload["actions"] = _actions_cache_snapshot()
    if normalized in {"crypto", "all"}:
        payload["crypto"] = _crypto_cache_snapshot()
    return payload


def _warmup_actions(
    include_edge: bool,
    limit: Optional[int],
    warnings: List[str],
    errors: List[str],
    batch_size: int = 50,
    batch: int = 1,
    start_index: Optional[int] = None,
    end_index: Optional[int] = None,
) -> Dict[str, Any]:
    warmed_tickers: List[str] = []
    edge_computed = 0
    total_tickers = len(ALL_TICKERS)
    batch_size = max(1, min(int(batch_size or 50), 100))
    batch = max(1, int(batch or 1))

    if start_index is not None or end_index is not None:
        start = max(0, int(start_index or 0))
        stop = min(total_tickers, int(end_index) if end_index is not None else total_tickers)
    else:
        start = (batch - 1) * batch_size
        stop = min(total_tickers, start + batch_size)
    if start >= total_tickers:
        start = total_tickers
    if stop < start:
        stop = start
    slice_tickers = ALL_TICKERS[start:stop]
    batch_label = f"{start}:{stop}"

    fetch_sp500_perf()
    _run_with_timeout("actions_market_context", lambda: _get_market_ctx(allow_download=True), 45, warnings, errors)
    _run_with_timeout("actions_regime_engine", lambda: compute_regime_engine(fast=False), 45, warnings, errors)
    _run_with_timeout("actions_market_regime", lambda: market_regime(), 45, warnings, errors)

    results: List[object] = []
    audit = Counter()
    audit_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(analyze_ticker, t, "standard", False, True, True, True, False, audit, audit_lock): t
            for t in slice_tickers
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
                    warmed_tickers.append(str(getattr(res, "ticker", ticker)).upper())
            except Exception as exc:
                errors.append(f"actions_warmup:{ticker}: {type(exc).__name__}: {str(exc)[:160]}")

    if limit:
        warmed_tickers = warmed_tickers[:limit]
        results = [r for r in results if str(getattr(r, "ticker", "")).upper() in set(warmed_tickers)]

    if results:
        _merge_screener_cache_results(
            _default_screener_cache_key(),
            results,
            meta={"source": "warmup", "batch": batch, "batch_size": batch_size, "slice": batch_label},
        )
        _screener_cache[f"warmup|batch={batch}|size={batch_size}|slice={batch_label}"] = {
            "ts": _time.time(),
            "data": results,
            "meta": {"source": "warmup", "batch": batch, "batch_size": batch_size, "slice": batch_label},
        }
        if warmed_tickers:
            _run_with_timeout(
                "actions_prices",
                lambda: get_prices(",".join(warmed_tickers[: min(len(warmed_tickers), 40)])),
                45,
                warnings,
                errors,
            )

    if include_edge and warmed_tickers:
        edge_targets = warmed_tickers[:limit] if limit else warmed_tickers
        for ticker in edge_targets:
            df = _get_ohlcv(ticker, allow_download=True)
            if df is None:
                warnings.append(f"actions_edge:{ticker}: OHLCV indisponible")
                continue
            try:
                compute_ticker_edge(ticker, df, period_months=24)
                edge_computed += 1
            except Exception as exc:
                errors.append(f"actions_edge:{ticker}: {type(exc).__name__}: {str(exc)[:160]}")

    merged_results = _screener_cache.get(_default_screener_cache_key(), {}).get("data", [])
    missing_tickers = max(total_tickers - len(merged_results), 0)
    estimated_remaining = max((missing_tickers + batch_size - 1) // batch_size, 0)
    _warmup_progress["actions"] = {
        "total_tickers": total_tickers,
        "warmed_tickers": len(merged_results),
        "missing_tickers": missing_tickers,
        "estimated_batches_remaining": estimated_remaining,
        "last_batch": batch,
        "last_slice": batch_label,
        "errors": errors[-10:],
    }

    return {
        "actions_count": len(warmed_tickers),
        "actions_edge_computed": edge_computed,
        "actions_cache": _actions_cache_snapshot(),
        "warmup_batch": {
            "batch": batch,
            "batch_size": batch_size,
            "start_index": start,
            "end_index": stop,
            "total_batches": max((total_tickers + batch_size - 1) // batch_size, 1),
            "slice_count": len(slice_tickers),
        },
    }


def _warmup_crypto(include_edge: bool, limit: Optional[int], warnings: List[str], errors: List[str]) -> Dict[str, Any]:
    warmed_symbols: List[str] = []
    edge_computed = 0

    _invalidate_crypto_regime_cache()
    _run_with_timeout("crypto_regime", lambda: compute_crypto_regime(fast=False), 90, warnings, errors)
    _run_with_timeout("crypto_prices", lambda: crypto_prices(["BTC", "ETH", "SOL"]), 45, warnings, errors)
    screener_run = _run_with_timeout(
        "crypto_screener",
        lambda: crypto_screener(fast=False),
        120,
        warnings,
        errors,
    )
    screener_results = screener_run["value"] if screener_run["ok"] and isinstance(screener_run["value"], list) else []

    if screener_results:
        warmed_symbols = []
        for row in screener_results:
            symbol = row.get("ticker") if isinstance(row, dict) else getattr(row, "ticker", None)
            if symbol:
                warmed_symbols.append(str(symbol).upper())
        if limit:
            warmed_symbols = warmed_symbols[:limit]

    if include_edge and warmed_symbols:
        edge_targets = warmed_symbols[:limit] if limit else warmed_symbols
        for symbol in edge_targets:
            try:
                compute_crypto_edge(symbol)
                edge_computed += 1
            except Exception as exc:
                errors.append(f"crypto_edge:{symbol}: {type(exc).__name__}: {str(exc)[:160]}")

    return {
        "crypto_count": len(warmed_symbols),
        "crypto_edge_computed": edge_computed,
        "crypto_cache": _crypto_cache_snapshot(),
    }


@app.post("/api/warmup")
def warmup(
    scope: str = Query("all"),
    include_edge: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1, le=100),
    batch_size: int = Query(50, ge=1, le=200),
    batch: int = Query(1, ge=1),
    start_index: Optional[int] = Query(None, ge=0),
    end_index: Optional[int] = Query(None, ge=0),
    _: None = Depends(require_admin_key),
):
    normalized = (scope or "all").strip().lower()
    if normalized not in {"actions", "crypto", "all"}:
        normalized = "all"

    started = _time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []
    payload: Dict[str, Any] = {
        "status": "ok",
        "scope": normalized,
        "include_edge": include_edge,
        "limit": limit,
    }

    if normalized in {"actions", "all"}:
        payload.update(
            _warmup_actions(
                include_edge=include_edge,
                limit=limit,
                warnings=warnings,
                errors=errors,
                batch_size=batch_size,
                batch=batch,
                start_index=start_index,
                end_index=end_index,
            )
        )
    if normalized in {"crypto", "all"}:
        payload.update(_warmup_crypto(include_edge=include_edge, limit=limit, warnings=warnings, errors=errors))

    payload["warnings"] = warnings
    payload["errors"] = errors
    payload["duration_ms"] = round((_time.perf_counter() - started) * 1000, 1)
    payload["updated"] = {
        "actions": _actions_cache_snapshot() if normalized in {"actions", "all"} else None,
        "crypto": _crypto_cache_snapshot() if normalized in {"crypto", "all"} else None,
    }
    payload["warmup_progress"] = _warmup_progress.get("actions") if normalized in {"actions", "all"} else None
    if errors:
        payload["status"] = "partial" if any(payload.get(k, 0) for k in ("actions_count", "crypto_count")) else "error"
    return payload


# ── Trade Journal persisté ─────────────────────────────────────────────────

@app.get("/api/trade-journal")
def get_trade_journal(
    universe: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    _: None = Depends(require_admin_key),
):
    trades = trade_journal_list(universe=universe, status=status, symbol=symbol)
    return {"trades": trades}


@app.get("/api/trade-journal/{trade_id}")
def get_trade_journal_item(
    trade_id: str,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_get(trade_id)
    if not trade:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trade not found")
    trade["events"] = trade_journal_list_events(trade_id)
    return trade


@app.post("/api/trade-journal")
def create_trade_journal(
    payload: TradeJournalCreateRequest,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_create(payload.model_dump(exclude_none=True))
    return {"trade": trade}


@app.patch("/api/trade-journal/{trade_id}")
def patch_trade_journal(
    trade_id: str,
    payload: TradeJournalUpdateRequest,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_update(trade_id, payload.model_dump(exclude_none=True))
    return {"trade": trade}


@app.post("/api/trade-journal/{trade_id}/open")
def open_trade_journal(
    trade_id: str,
    payload: TradeJournalOpenRequest,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_open(trade_id, payload.model_dump(exclude_none=True))
    return {"trade": trade}


@app.post("/api/trade-journal/{trade_id}/close")
def close_trade_journal(
    trade_id: str,
    payload: TradeJournalCloseRequest,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_close(trade_id, payload.model_dump(exclude_none=True))
    return {"trade": trade}


@app.delete("/api/trade-journal/{trade_id}")
def delete_trade_journal(
    trade_id: str,
    _: None = Depends(require_admin_key),
):
    trade = trade_journal_delete(trade_id)
    return {"trade": trade}


@app.get("/api/trade-journal/stats")
def trade_journal_statistics(
    _: None = Depends(require_admin_key),
):
    return trade_journal_stats()
