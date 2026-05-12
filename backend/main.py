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
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from concurrent.futures import TimeoutError as FuturesTimeoutError
import threading
from collections import Counter
from datetime import datetime, timezone

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
from ticker_edge import compute_ticker_edge, get_cached_edge, get_cached_edge_with_status, is_edge_cache_populated, invalidate_cache as _invalidate_edge_cache
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
from crypto_scalp_service import (
    analyze_crypto_scalp_symbol,
    crypto_scalp_screener,
    warmup_crypto_scalp_intraday,
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
from edge_v2_research import build_edge_v2_research_rows
from cache_persistence import get_status as get_cache_persistence_status, load_state as load_cache_state, save_state as save_cache_state

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
APP_STARTED_AT = _time.time()
LAST_WARMUP_ACTIONS_STARTED: float | None = None
LAST_WARMUP_ACTIONS_FINISHED: float | None = None
LAST_WARMUP_CRYPTO_STARTED: float | None = None
LAST_WARMUP_CRYPTO_FINISHED: float | None = None
LAST_RESTART_DETECTED: float | None = None


def _iso(ts: float | int | None) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _load_runtime_cache_state() -> None:
    global LAST_RESTART_DETECTED, LAST_WARMUP_ACTIONS_STARTED, LAST_WARMUP_ACTIONS_FINISHED, LAST_WARMUP_CRYPTO_STARTED, LAST_WARMUP_CRYPTO_FINISHED
    state = load_cache_state()
    if not state:
        return
    try:
        LAST_RESTART_DETECTED = state.get("app_started_at")
        actions = state.get("actions", {})
        crypto = state.get("crypto", {})

        if isinstance(actions, dict) and any(actions.get(key) for key in ("_ohlcv_cache", "_price_cache", "_screener_cache", "_market_regime_cache", "_mkt_ctx_cache", "_warmup_progress")):
            if actions.get("_ohlcv_cache"):
                _ohlcv_cache.clear()
                _ohlcv_cache.update(actions.get("_ohlcv_cache", {}))
            if actions.get("_price_cache"):
                _price_cache.clear()
                _price_cache.update(actions.get("_price_cache", {}))
            if actions.get("_screener_cache"):
                _screener_cache.clear()
                _screener_cache.update(actions.get("_screener_cache", {}))
            if actions.get("_market_regime_cache"):
                _market_regime_cache.clear()
                _market_regime_cache.update(actions.get("_market_regime_cache", {}))
            if actions.get("_mkt_ctx_cache"):
                _mkt_ctx_cache.clear()
                _mkt_ctx_cache.update(actions.get("_mkt_ctx_cache", {}))
            if actions.get("_warmup_progress"):
                _warmup_progress.clear()
                _warmup_progress.update(actions.get("_warmup_progress", {}))
        if actions.get("last_actions_started") is not None:
            LAST_WARMUP_ACTIONS_STARTED = actions.get("last_actions_started")
        if actions.get("last_actions_finished") is not None:
            LAST_WARMUP_ACTIONS_FINISHED = actions.get("last_actions_finished")

        if isinstance(crypto, dict) and any(crypto.get(key) for key in ("_price_cache", "_ohlcv_daily_cache", "_ohlcv_4h_cache", "_screener_cache", "_crypto_regime_cache")):
            if crypto.get("_price_cache"):
                _crypto_data_module._price_cache.clear()
                _crypto_data_module._price_cache.update(crypto.get("_price_cache", {}))
            if crypto.get("_ohlcv_daily_cache"):
                _crypto_data_module._ohlcv_daily_cache.clear()
                _crypto_data_module._ohlcv_daily_cache.update(crypto.get("_ohlcv_daily_cache", {}))
            if crypto.get("_ohlcv_4h_cache"):
                _crypto_data_module._ohlcv_4h_cache.clear()
                _crypto_data_module._ohlcv_4h_cache.update(crypto.get("_ohlcv_4h_cache", {}))
            if crypto.get("_screener_cache"):
                _crypto_service_module._screener_cache.clear()
                _crypto_service_module._screener_cache.update(crypto.get("_screener_cache", {}))
            if crypto.get("_crypto_regime_cache"):
                _crypto_regime_cache.clear()
                _crypto_regime_cache.update(crypto.get("_crypto_regime_cache", {}))
        if crypto.get("last_crypto_started") is not None:
            LAST_WARMUP_CRYPTO_STARTED = crypto.get("last_crypto_started")
        if crypto.get("last_crypto_finished") is not None:
            LAST_WARMUP_CRYPTO_FINISHED = crypto.get("last_crypto_finished")
    except Exception:
        return


def _persist_runtime_cache_state() -> None:
    try:
        save_cache_state({
            "app_started_at": APP_STARTED_AT,
            "last_saved_at": _time.time(),
            "actions": {
                "_ohlcv_cache": _ohlcv_cache,
                "_price_cache": _price_cache,
                # Note: _screener_cache NOT persisted (calculated cache, not critical data)
                # Preventing screener cache stale data from persisting after edge compute
                "_market_regime_cache": _market_regime_cache,
                "_mkt_ctx_cache": _mkt_ctx_cache,
                "_warmup_progress": _warmup_progress,
                "last_actions_started": LAST_WARMUP_ACTIONS_STARTED,
                "last_actions_finished": LAST_WARMUP_ACTIONS_FINISHED,
            },
            "crypto": {
                "_price_cache": _crypto_data_module._price_cache,
                "_ohlcv_daily_cache": _crypto_data_module._ohlcv_daily_cache,
                "_ohlcv_4h_cache": _crypto_data_module._ohlcv_4h_cache,
                "_screener_cache": _crypto_service_module._screener_cache,
                "_crypto_regime_cache": _crypto_regime_cache,
                "last_crypto_started": LAST_WARMUP_CRYPTO_STARTED,
                "last_crypto_finished": LAST_WARMUP_CRYPTO_FINISHED,
            },
        })
    except Exception:
        pass


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

_load_runtime_cache_state()

# ── Health check (keep-alive pour Railway) ───────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/admin/ping")
def admin_ping(_: None = Depends(require_admin_key)):
    return {"status": "ok", "admin": True}


@app.get("/api/debug/cache-integrity")
def debug_cache_integrity(_: None = Depends(require_admin_key)):
    """
    Diagnostic endpoint: Cache integrity, persistence status, warmup progress.
    Returns: app uptime, cache counts, persistence status, warnings.
    """
    from datetime import datetime, timezone

    # Uptime
    uptime_seconds = _time.time() - APP_STARTED_AT
    app_started_at_iso = datetime.fromtimestamp(APP_STARTED_AT, tz=timezone.utc).isoformat()

    # Persistence status
    persistence_status = get_cache_persistence_status()

    # Actions caches
    actions_edge_count = len(_ticker_edge_module._edge_cache)
    actions_edge_tickers = list(_ticker_edge_module._edge_cache.keys()) if _ticker_edge_module._edge_cache else []
    actions_ohlcv_count = len(_ohlcv_cache)
    actions_price_count = len(_price_cache)
    actions_screener_count = len(_screener_cache)
    screener_default = _screener_cache.get(_default_screener_cache_key(), {})
    screener_results_count = len(screener_default.get("data", [])) if isinstance(screener_default, dict) else 0

    # Crypto caches
    try:
        crypto_ohlcv_count = len(_crypto_data_module._ohlcv_daily_cache) if hasattr(_crypto_data_module, '_ohlcv_daily_cache') else 0
        crypto_4h_count = len(_crypto_data_module._ohlcv_4h_cache) if hasattr(_crypto_data_module, '_ohlcv_4h_cache') else 0
        crypto_price_count = len(_crypto_data_module._price_cache) if hasattr(_crypto_data_module, '_price_cache') else 0
        crypto_screener_count = len(_crypto_service_module._screener_cache) if hasattr(_crypto_service_module, '_screener_cache') else 0
        crypto_edge_count = len(_crypto_edge_cache) if _crypto_edge_cache else 0
        crypto_edge_tickers = list(_crypto_edge_cache.keys()) if _crypto_edge_cache else []
    except Exception:
        crypto_ohlcv_count = 0
        crypto_4h_count = 0
        crypto_price_count = 0
        crypto_screener_count = 0
        crypto_edge_count = 0
        crypto_edge_tickers = []

    # Warmup progress
    actions_warmup = _warmup_progress.get("actions", {})
    crypto_warmup = _warmup_progress.get("crypto", {})

    # Warnings
    warnings = []

    # Edge cache empty?
    if actions_edge_count == 0:
        warnings.append("WARNING: Actions edge_cache is empty (warmup not done)")

    # Screener cache empty?
    if screener_results_count == 0:
        warnings.append("WARNING: Screener results cache is empty")

    # Persistence issues?
    if not persistence_status.get("persistence_enabled"):
        warnings.append("WARNING: Persistence is disabled")

    if not persistence_status.get("persistence_files_found"):
        warnings.append("WARNING: Persistence file not found on disk")

    if persistence_status.get("persistence_save_errors"):
        warnings.append(f"WARNING: Persistence save error: {persistence_status.get('persistence_save_errors')[0]}")

    if persistence_status.get("persistence_load_errors"):
        warnings.append(f"WARNING: Persistence load error: {persistence_status.get('persistence_load_errors')[0]}")

    # Recent restart?
    if LAST_WARMUP_ACTIONS_FINISHED is None:
        warnings.append("WARNING: Actions warmup not completed since app start")

    if LAST_WARMUP_CRYPTO_FINISHED is None:
        warnings.append("WARNING: Crypto warmup not completed since app start")

    # Cache age checks
    try:
        screener_ts = max((v.get("ts", 0) for v in _screener_cache.values()), default=0)
        if screener_ts:
            screener_age = _time.time() - screener_ts
            if screener_age > 3600:
                warnings.append(f"WARNING: Screener cache is stale ({int(screener_age / 60)} min old)")
    except Exception:
        pass

    try:
        edge_ts = max((v.get("ts", 0) for v in _ticker_edge_module._edge_cache.values()), default=0)
        if edge_ts:
            edge_age = _time.time() - edge_ts
            if edge_age > 86400:
                warnings.append(f"WARNING: Edge cache is very old ({int(edge_age / 3600)} hours)")
    except Exception:
        pass

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_started_at": app_started_at_iso,
        "uptime_seconds": round(uptime_seconds, 1),
        "persistence": {
            "enabled": persistence_status.get("persistence_enabled", False),
            "directory": persistence_status.get("persistence_dir", "unknown"),
            "file": persistence_status.get("persistence_file", "unknown"),
            "file_exists": bool(persistence_status.get("persistence_files_found")),
            "last_save": persistence_status.get("last_persistence_save"),
            "last_load": persistence_status.get("last_persistence_load"),
            "last_save_ok": persistence_status.get("persistence_last_save_ok", False),
            "last_load_ok": persistence_status.get("persistence_last_load_ok", False),
            "save_attempts": persistence_status.get("save_attempts", 0),
            "load_attempts": persistence_status.get("load_attempts", 0),
            "last_save_error": persistence_status.get("persistence_save_errors", [None])[0] if persistence_status.get("persistence_save_errors") else None,
            "last_load_error": persistence_status.get("persistence_load_errors", [None])[0] if persistence_status.get("persistence_load_errors") else None,
        },
        "caches": {
            "actions": {
                "ohlcv_count": actions_ohlcv_count,
                "price_count": actions_price_count,
                "screener_cache_keys": actions_screener_count,
                "screener_results": screener_results_count,
                "edge_cache_count": actions_edge_count,
                "edge_tickers": actions_edge_tickers,
            },
            "crypto": {
                "ohlcv_daily_count": crypto_ohlcv_count,
                "ohlcv_4h_count": crypto_4h_count,
                "price_count": crypto_price_count,
                "screener_cache_count": crypto_screener_count,
                "edge_cache_count": crypto_edge_count,
                "edge_tickers": crypto_edge_tickers,
            },
        },
        "warmup_progress": {
            "actions": {
                "started_at": _iso(LAST_WARMUP_ACTIONS_STARTED),
                "finished_at": _iso(LAST_WARMUP_ACTIONS_FINISHED),
                "total_tickers": actions_warmup.get("total_tickers"),
                "warmed_tickers": actions_warmup.get("warmed_tickers"),
                "missing_tickers": actions_warmup.get("missing_tickers"),
                "errors_count": len(actions_warmup.get("errors", [])),
            },
            "crypto": {
                "started_at": _iso(LAST_WARMUP_CRYPTO_STARTED),
                "finished_at": _iso(LAST_WARMUP_CRYPTO_FINISHED),
                "total_symbols": crypto_warmup.get("total_symbols"),
                "warmed_symbols": crypto_warmup.get("warmed_symbols"),
                "errors_count": len(crypto_warmup.get("errors", [])),
            },
        },
        "warnings": warnings,
    }


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


def _actions_cache_is_ready(snapshot: Optional[Dict[str, Any]] = None) -> bool:
    data = snapshot or _actions_cache_snapshot()
    return (
        data.get("ohlcv_cache_count", 0) > 150
        and data.get("price_cache_count", 0) > 150
        and data.get("screener_results_count", 0) > 0
        and data.get("regime_cache_status") == "warm"
    )


def _record_actions_warmup_issue(
    warnings: List[str],
    errors: List[str],
    *,
    endpoint: str,
    batch_label: str,
    message: str,
    batch_record: Optional[Dict[str, Any]] = None,
) -> None:
    warnings.append(message)
    errors.append(message)
    progress = _warmup_progress.setdefault("actions", {})
    progress["last_failed_endpoint"] = endpoint
    progress["last_failed_batch"] = batch_label
    progress["last_error_message"] = message
    progress["last_error_at"] = _iso(_time.time())
    if batch_record is not None:
        batch_record.setdefault("errors", []).append(message)


def _warmup_actions_chunk(
    tickers: List[str],
    *,
    include_edge: bool,
    limit: Optional[int],
    warnings: List[str],
    errors: List[str],
    audit: Counter,
    audit_lock: threading.Lock,
    batch_record: Dict[str, Any],
    timeout_seconds: int = 15,
) -> tuple[list[object], list[str], int]:
    results: List[object] = []
    warmed_tickers: List[str] = []
    edge_computed = 0
    if not tickers:
        return results, warmed_tickers, edge_computed

    with ThreadPoolExecutor(max_workers=min(4, max(len(tickers), 1))) as executor:
        futures = {
            executor.submit(
                analyze_ticker,
                t,
                "standard",
                False,
                False,
                False,
                False,
                False,
                audit,
                audit_lock,
            ): t
            for t in tickers
        }
        pending = set(futures.keys())
        while pending:
            done, not_done = wait(pending, timeout=timeout_seconds)
            if not done:
                for future in list(not_done):
                    ticker = futures.get(future, "UNKNOWN")
                    future.cancel()
                    msg = f"actions_warmup:{ticker}: timeout after {timeout_seconds}s"
                    _record_actions_warmup_issue(
                        warnings,
                        errors,
                        endpoint="actions",
                        batch_label=batch_record.get("slice", "unknown"),
                        message=msg,
                        batch_record=batch_record,
                    )
                break
            for future in done:
                ticker = futures[future]
                try:
                    res = future.result()
                    if res:
                        results.append(res)
                        warmed_tickers.append(str(getattr(res, "ticker", ticker)).upper())
                except Exception as exc:
                    msg = f"actions_warmup:{ticker}: {type(exc).__name__}: {str(exc)[:160]}"
                    _record_actions_warmup_issue(
                        warnings,
                        errors,
                        endpoint="actions",
                        batch_label=batch_record.get("slice", "unknown"),
                        message=msg,
                        batch_record=batch_record,
                    )
            pending = not_done

    if limit:
        warmed_tickers = warmed_tickers[:limit]
        allowed = {str(getattr(r, "ticker", "")).upper() for r in results}
        warmed_set = set(warmed_tickers)
        results = [r for r in results if str(getattr(r, "ticker", "")).upper() in allowed and str(getattr(r, "ticker", "")).upper() in warmed_set]

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
                msg = f"actions_edge:{ticker}: {type(exc).__name__}: {str(exc)[:160]}"
                _record_actions_warmup_issue(
                    warnings,
                    errors,
                    endpoint="actions",
                    batch_label=batch_record.get("slice", "unknown"),
                    message=msg,
                    batch_record=batch_record,
                )

    return results, warmed_tickers, edge_computed


def _crypto_cache_snapshot() -> Dict[str, Any]:
    crypto_freshness = crypto_data_freshness()
    edge_status = crypto_edge_status()
    daily_cache = getattr(_crypto_data_module, "_ohlcv_daily_cache", {})
    h4_cache = getattr(_crypto_data_module, "_ohlcv_4h_cache", {})
    intraday_1m_cache = getattr(_crypto_data_module, "_ohlcv_1m_cache", {})
    intraday_5m_cache = getattr(_crypto_data_module, "_ohlcv_5m_cache", {})
    intraday_15m_cache = getattr(_crypto_data_module, "_ohlcv_15m_cache", {})
    price_cache = getattr(_crypto_data_module, "_price_cache", {})
    screener_cache = getattr(_crypto_service_module, "_screener_cache", {})
    regime_ts = getattr(_crypto_regime_cache, "get", lambda *_: 0)("ts", 0)
    regime_data = getattr(_crypto_regime_cache, "get", lambda *_: {})("data", {}) if _crypto_regime_cache else {}
    regime_status = _cache_state(regime_ts, 3600)
    if isinstance(regime_data, dict) and regime_data.get("data_status") == "MISSING":
        regime_status = "missing"

    # Get last intraday warmup timestamp
    last_intraday_warmup_ts = getattr(_crypto_data_module, "_last_intraday_update_ts", 0) or 0
    last_intraday_warmup = _ts_to_iso(last_intraday_warmup_ts) if last_intraday_warmup_ts else None

    return {
        "crypto_ohlcv_cache_count": len(daily_cache),
        "crypto_ohlcv_4h_cache_count": len(h4_cache),
        "crypto_intraday_1m_cache_count": len(intraday_1m_cache),
        "crypto_intraday_5m_cache_count": len(intraday_5m_cache),
        "crypto_intraday_15m_cache_count": len(intraday_15m_cache),
        "crypto_price_cache_count": len(price_cache),
        "crypto_screener_cache_count": len(screener_cache),
        "crypto_regime_cache_status": regime_status,
        "crypto_edge_cache_coverage": edge_status.get("coverage_pct", 0.0),
        "last_crypto_screener_update": _ts_to_iso(crypto_freshness["last_screener_update"]),
        "last_crypto_price_update": _ts_to_iso(crypto_freshness["last_price_update"]),
        "last_crypto_regime_update": _ts_to_iso(crypto_freshness["last_regime_update"]),
        "last_crypto_edge_update": _ts_to_iso(crypto_freshness["last_edge_update"]),
        "last_intraday_warmup": last_intraday_warmup,
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


def _yf_history_safe(
    ticker: str,
    period: str = "26mo",
    interval: str = "1d",
    timeout: int = 10,
) -> Optional[pd.DataFrame]:
    """
    Fetches historical data using yf.Ticker().history() instead of yf.download().
    More robust to "Invalid Crumb" errors that can occur after Railway restart.

    Returns None silently on error (no exception raised) to allow batch processing to continue.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        # Note: progress is NOT a valid parameter for history() - it's download() only
        # timeout is supported but optional. auto_adjust=True is default.
        df = ticker_obj.history(period=period, interval=interval, auto_adjust=True)

        if df is None or df.empty:
            return None

        return df
    except Exception:
        # Silently return None - let caller decide how to handle
        return None


def _get_ohlcv(ticker: str, allow_download: bool = True) -> Optional[object]:
    """
    Retourne le DataFrame OHLCV historique (26 mois, daily).
    Cache 4h — les indicateurs ne changent pas en intraday.
    Utilise _yf_history_safe() pour éviter les erreurs "Invalid Crumb".
    """
    now   = _time.time()
    entry = _ohlcv_cache.get(ticker)
    if entry and ((now - entry["ts"]) < _OHLCV_TTL or not allow_download):
        return entry["df"]
    if not allow_download:
        return None
    try:
        def _download():
            return _yf_history_safe(
                ticker,
                period="26mo",
                interval="1d",
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
        # Fallback : dernière bougie intraday 2 min via _yf_history_safe
        try:
            df = _yf_history_safe(ticker, period="1d", interval="2m", timeout=5)
            if df is None or df.empty:
                return None
            close = df["Close"].squeeze()
            price = float(close.iloc[-1])
            # prev_close via 5d daily
            df5 = _yf_history_safe(ticker, period="5d", interval="1d", timeout=5)
            prev = float(df5["Close"].squeeze().iloc[-2]) if df5 is not None and len(df5) >= 2 else price
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
        df = _yf_history_safe("^GSPC", period="8mo", interval="1d", timeout=10)
        if df is not None and not df.empty:
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
        df = _yf_history_safe("SPY", period="14mo", interval="1d", timeout=10)
        if df is None or df.empty or len(df) < 210:
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
    ticker_edge_status:  str         = "NO_EDGE"   # STRONG_EDGE | VALID_EDGE | WEAK_EDGE | OVERFITTED | NO_EDGE | EDGE_NOT_COMPUTED
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
            edge_data, edge_cache_state = get_cached_edge_with_status(ticker)
            if edge_data is None:
                if edge_cache_state == "EMPTY":
                    te_status = "EDGE_NOT_COMPUTED"
                    edge_data = {}
                else:
                    te_status = "NO_EDGE"
                    edge_data = {}
            else:
                edge_data = edge_data or {}
                te_status = edge_data.get("ticker_edge_status", "NO_EDGE")
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
    _persist_runtime_cache_state()


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
    cached = _crypto_regime_cache.get("data") if isinstance(_crypto_regime_cache, dict) else None
    cached_age = _time.time() - _crypto_regime_cache.get("ts", 0) if isinstance(_crypto_regime_cache, dict) and _crypto_regime_cache.get("ts") else None
    if isinstance(cached, dict) and cached_age is not None and cached_age < 3600 and cached.get("data_status") == "OK":
        return cached
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(compute_crypto_regime, False)
            return future.result(timeout=20)
    except Exception:
        if isinstance(cached, dict):
            degraded = dict(cached)
            degraded.setdefault("status", "degraded")
            degraded.setdefault("warnings", [])
            degraded["warnings"] = list(degraded.get("warnings", [])) + ["Crypto regime returned cached fallback"]
            return degraded
        fallback = compute_crypto_regime(fast=True)
        if isinstance(fallback, dict):
            fallback["status"] = "degraded"
            fallback["warnings"] = list(fallback.get("warnings", [])) + ["Crypto regime fallback after timeout"]
        return fallback


# Scope: CRYPTO
@app.get("/api/crypto/screener")
def crypto_screener_endpoint(
    sector: Optional[str] = Query(None),
    min_score: int = Query(0),
    signal: Optional[str] = Query(None),
    fast: bool = Query(False),
):
    return crypto_screener(sector=sector, min_score=min_score, signal=signal, fast=fast)


# Scope: CRYPTO SCALP (Phase 1 — lightweight scanner)
@app.get("/api/crypto/scalp/screener")
def crypto_scalp_screener_endpoint(
    sort_by: str = Query("scalp_score", description="scalp_score, long_score, short_score, tier"),
    reverse: bool = Query(True),
    limit: int = Query(50),
    min_score: int = Query(0),
    tier_filter: Optional[int] = Query(None, description="1, 2, or 3"),
):
    return crypto_scalp_screener(
        sort_by=sort_by,
        reverse=reverse,
        limit=limit,
        min_score=min_score,
        tier_filter=tier_filter,
    )


# Scope: CRYPTO SCALP (Single symbol analysis)
@app.get("/api/crypto/scalp/analyze/{symbol}")
def crypto_scalp_analyze_endpoint(symbol: str):
    return analyze_crypto_scalp_symbol(symbol.upper())


# Scope: CRYPTO SCALP (Phase 3B.1: Backtest Preview)
@app.get("/api/crypto/scalp/backtest-lite")
def crypto_scalp_backtest_lite_endpoint(symbol: str):
    """
    Phase 3B.1: Backtest Preview Ultra-Léger.

    Simulation only, 7 days, no real execution.

    IMPORTANT: Historical simulation, not a prediction.
    """
    from crypto_scalp_service import crypto_scalp_backtest_lite_endpoint
    try:
        return crypto_scalp_backtest_lite_endpoint(symbol)
    except Exception as e:
        return {
            "error": f"Backtest error: {str(e)}",
            "simulation_only": True,
            "no_execution": True
        }


# Scope: CRYPTO SCALP (Phase 3B.2a: Extended Backtest Preview)
@app.get("/api/crypto/scalp/backtest-extended")
def crypto_scalp_backtest_extended_endpoint(symbol: str, days: int = 7):
    """
    Phase 3B.2a: Extended Backtest Preview (7 days with trade-by-trade details).

    Simulation only, 7 days maximum (Phase 3B.2a), no real execution.
    Returns trade-by-trade details, summary stats, and metadata.

    Parameters:
      symbol: Crypto symbol (BTC, ETH, SOL, ARB, INJ, etc.)
      days: Number of days (7 only in Phase 3B.2a; 14/30 rejected with "not implemented yet")

    Response:
      - trades: Array of latest 20 trades with entry/exit, side, R value, PnL %
      - win_rate, loss_rate, avg_r, best_trade_r, worst_trade_r
      - effective_period_days: Actual coverage (may be < 7 if data unavailable)
      - incomplete: true if timeout/partial data, false if complete
      - simulation_only: true, no_execution: true (always)

    IMPORTANT: Historical simulation, not a prediction. No real execution.
    """
    try:
        from crypto_backtest_lite import backtest_crypto_scalp_extended
        import time

        # Force redeploy trigger (timestamp marker)
        _redeploy_marker = f"2026-05-13-{int(time.time())}"

        # Validate days parameter
        if days not in [7]:
            return {
                "error": f"Phase 3B.2a supports only days=7. Got days={days}. (14/30 days coming in Phase 3B.2b)",
                "simulation_only": True,
                "no_execution": True,
                "disclaimer": "Historical simulation only. Not a prediction. No real execution."
            }

        result = backtest_crypto_scalp_extended(symbol.upper(), days=days)
        return result

    except Exception as e:
        return {
            "error": f"Extended backtest error: {str(e)}",
            "symbol": symbol,
            "simulation_only": True,
            "no_execution": True,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution."
        }


# Scope: CRYPTO SCALP (Create journal entry)
@app.post("/api/crypto/scalp/journal")
def crypto_scalp_journal_endpoint(payload: dict):
    """Create a SCALP trade entry in the journal."""
    from trade_journal import create_scalp_trade
    try:
        symbol = payload.get("symbol", "").upper()
        scalp_result = payload.get("scalp_result", {})
        status = payload.get("status", "SCALP_WATCHLIST")
        if not symbol:
            return {"error": "symbol required"}
        trade = create_scalp_trade(symbol, scalp_result, status)
        return {"ok": True, "trade_id": trade.get("id"), "status": trade.get("status")}
    except Exception as e:
        return {"error": str(e)}


# Scope: CRYPTO SCALP (List all paper trades)
@app.get("/api/crypto/scalp/journal/trades")
def crypto_scalp_trades_endpoint():
    """List all SCALP paper trades (PLANNED, CLOSED, WATCHLIST)."""
    from trade_journal import _connect
    try:
        conn = _connect()
        cursor = conn.execute("""
            SELECT
                id, symbol, direction, entry_price, exit_price,
                stop_loss, tp1, tp2, status, created_at, closed_at,
                entry_fee_pct, exit_fee_pct, slippage_pct, spread_bps,
                pnl_pct, actual_pnl_pct_net, r_multiple, closure_reason
            FROM trades
            WHERE signal_type = 'SCALP'
            ORDER BY created_at DESC
            LIMIT 100
        """)
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"trades": trades, "count": len(trades)}
    except Exception as e:
        return {"error": str(e), "trades": []}


# Scope: CRYPTO SCALP (Close a paper trade)
@app.post("/api/crypto/scalp/journal/close/{trade_id}")
def crypto_scalp_close_endpoint(trade_id: str, payload: dict):
    """Close a SCALP_PAPER_PLANNED trade and compute net PnL."""
    from trade_journal import close_scalp_trade
    try:
        exit_price = payload.get("exit_price")
        closure_reason = payload.get("closure_reason", "MANUAL_EXIT")
        if not exit_price:
            return {"error": "exit_price required"}
        result = close_scalp_trade(trade_id, exit_price, closure_reason)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Scope: CRYPTO SCALP (Portfolio performance)
@app.get("/api/crypto/scalp/journal/performance")
def crypto_scalp_performance_endpoint(symbol: str = None):
    """Get portfolio performance stats for closed SCALP_PAPER trades."""
    from crypto_paper_metrics import compute_paper_portfolio_stats, get_symbol_performance
    try:
        if symbol:
            stats = get_symbol_performance(symbol.upper())
        else:
            stats = compute_paper_portfolio_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


# Scope: CRYPTO SCALP (Health check)
@app.get("/api/crypto/scalp/journal/health")
def crypto_scalp_health_endpoint():
    """Lightweight health check for scalp journal."""
    from trade_journal import _connect
    try:
        conn = _connect()
        cursor = conn.execute("SELECT COUNT(*) as total FROM trades WHERE signal_type = 'SCALP'")
        row = cursor.fetchone()
        total_trades = row["total"] if row else 0

        cursor2 = conn.execute("SELECT COUNT(*) as planned FROM trades WHERE signal_type = 'SCALP' AND status = 'SCALP_PAPER_PLANNED'")
        row2 = cursor2.fetchone()
        planned_trades = row2["planned"] if row2 else 0

        cursor3 = conn.execute("SELECT COUNT(*) as closed FROM trades WHERE signal_type = 'SCALP' AND status = 'SCALP_PAPER_CLOSED'")
        row3 = cursor3.fetchone()
        closed_trades = row3["closed"] if row3 else 0

        conn.close()
        return {
            "status": "ok",
            "total_scalp_trades": total_trades,
            "planned_trades": planned_trades,
            "closed_trades": closed_trades,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/crypto/scalp/warmup-intraday")
def crypto_scalp_warmup_intraday_endpoint(tier: str = Query("all")):
    """
    Manually warm Crypto Scalp intraday 5m cache.

    Query params:
    - tier: "1" (5 symbols: BTC,ETH,SOL,BNB,XRP), "2" (27 symbols), "all" (37 symbols, default)

    Returns:
        {
            "tier": str,
            "total_symbols": int,
            "success_count": int,
            "failed_count": int,
            "failed_symbols": {symbol: error_reason},
            "duration_ms": float,
            "timestamp": str (ISO)
        }
    """
    if tier not in ("1", "2", "all"):
        tier = "all"

    result = warmup_crypto_scalp_intraday(tier=tier, max_workers=6, timeout_seconds=120)
    return result


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


# ── DIAGNOSTIC: Network & API Tests (Temporary) ───────────────────────────────
@app.get("/api/debug/network-test")
def debug_network_test():
    """
    Test network connectivity to various APIs from Railway.
    DIAGNOSTIC ONLY - for troubleshooting warmup failures.
    """
    import httpx
    import json

    tests = {
        "binance_time": "https://api.binance.com/api/v3/time",
        "binance_klines": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1",
        "coingecko_ping": "https://api.coingecko.com/api/v3/ping",
        "yahoo_basic": "https://query1.finance.yahoo.com",
        "httpbin": "https://httpbin.org/get",
    }

    results = {}

    for test_name, url in tests.items():
        started = _time.perf_counter()
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(url)
                elapsed_ms = (_time.perf_counter() - started) * 1000

                result = {
                    "status": r.status_code,
                    "reason": r.reason_phrase if hasattr(r, 'reason_phrase') else "OK" if r.status_code == 200 else "ERROR",
                    "elapsed_ms": round(elapsed_ms, 1),
                    "content_length": len(r.content),
                    "success": r.status_code < 400,
                }

                # Try to parse response if JSON
                if r.status_code == 200 and test_name == "binance_klines":
                    try:
                        data = r.json()
                        result["rows"] = len(data) if isinstance(data, list) else "not a list"
                    except:
                        result["parse"] = "not JSON"

                results[test_name] = result

        except httpx.ConnectError as e:
            elapsed_ms = (_time.perf_counter() - started) * 1000
            results[test_name] = {
                "error": "ConnectError",
                "detail": str(e)[:100],
                "elapsed_ms": round(elapsed_ms, 1),
                "success": False,
            }
        except httpx.TimeoutException as e:
            elapsed_ms = (_time.perf_counter() - started) * 1000
            results[test_name] = {
                "error": "TimeoutException",
                "detail": str(e)[:100],
                "elapsed_ms": round(elapsed_ms, 1),
                "success": False,
            }
        except Exception as e:
            elapsed_ms = (_time.perf_counter() - started) * 1000
            results[test_name] = {
                "error": type(e).__name__,
                "detail": str(e)[:100],
                "elapsed_ms": round(elapsed_ms, 1),
                "success": False,
            }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "production" if "railway" in _os.getenv("ENVIRONMENT", "").lower() else "unknown",
        "tests": results,
        "summary": {
            "total": len(results),
            "success": sum(1 for r in results.values() if r.get("success", False)),
            "failed": sum(1 for r in results.values() if not r.get("success", True)),
        }
    }


@app.get("/api/debug/binance-test/{symbol}")
def debug_binance_test(symbol: str):
    """
    Test direct Binance API call for a symbol.
    Returns exact error details.
    """
    import httpx

    sym = symbol.upper()
    pair = sym + "USDT"
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": pair,
        "interval": "5m",
        "limit": 5,
    }

    started = _time.perf_counter()
    try:
        with httpx.Client(timeout=15, headers={"User-Agent": "swing-analyser-crypto/1.0"}) as client:
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - started) * 1000

            result = {
                "symbol": sym,
                "pair": pair,
                "url": url,
                "params": params,
                "status_code": r.status_code,
                "reason": r.reason_phrase if hasattr(r, 'reason_phrase') else "OK",
                "elapsed_ms": round(elapsed_ms, 1),
                "headers_received": dict(r.headers),
                "content_length": len(r.content),
                "success": r.status_code == 200,
            }

            # Try to read response
            if r.status_code == 200:
                try:
                    data = r.json()
                    result["response"] = {
                        "type": "list" if isinstance(data, list) else type(data).__name__,
                        "length": len(data) if isinstance(data, list) else "N/A",
                        "first_item_sample": str(data[0])[:100] if isinstance(data, list) and data else None,
                    }
                except Exception as e:
                    result["response"] = f"Parse error: {type(e).__name__}"
            else:
                # Get text response for debugging
                result["response_text"] = r.text[:500]

            return result

    except Exception as e:
        elapsed_ms = (_time.perf_counter() - started) * 1000
        return {
            "symbol": sym,
            "pair": pair,
            "url": url,
            "error": type(e).__name__,
            "error_detail": str(e),
            "elapsed_ms": round(elapsed_ms, 1),
            "success": False,
        }


@app.get("/api/debug/intraday-providers/{symbol}")
def debug_intraday_providers(symbol: str):
    """
    Test multiple intraday data providers from Railway.
    Diagnostic endpoint - tests Coinbase, Kraken, CryptoCompare, etc.
    """
    import httpx

    sym = symbol.upper()
    results = {}

    # Test 1: Coinbase Pro API (public, no auth required for basic data)
    try:
        start = _time.perf_counter()
        with httpx.Client(timeout=10) as client:
            # Coinbase product ID: BTC-USD, ETH-USD, etc.
            product_id = f"{sym}-USD"
            url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
            params = {
                "granularity": 300,  # 300 seconds = 5 minutes
                "limit": 300,
            }
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - start) * 1000

            result = {
                "status": r.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "content_length": len(r.content),
                "url": url,
            }

            if r.status_code == 200:
                try:
                    data = r.json()
                    result["data_points"] = len(data) if isinstance(data, list) else 0
                    result["sample"] = data[0][:5] if isinstance(data, list) and data else None  # [time, low, high, open, close, volume]
                    result["success"] = True
                except Exception as e:
                    result["parse_error"] = str(e)[:50]
                    result["success"] = False
            else:
                result["response"] = r.text[:200]
                result["success"] = False

            results["coinbase"] = result
    except Exception as e:
        results["coinbase"] = {
            "error": type(e).__name__,
            "detail": str(e)[:100],
            "success": False,
        }

    # Test 2: Kraken API (public, no auth for OHLC)
    try:
        start = _time.perf_counter()
        with httpx.Client(timeout=10) as client:
            # Kraken pair format: XXBTUSDT, XETHUSDT, etc.
            kraken_pair_map = {
                "BTC": "XXBTZUSD",
                "ETH": "XETHZUSD",
                "SOL": "SOLDUSD",
                "BNB": "BNBUSD",
                "XRP": "XXRPZUSD",
            }
            kraken_pair = kraken_pair_map.get(sym, sym + "USD")

            url = "https://api.kraken.com/0/public/OHLC"
            params = {
                "pair": kraken_pair,
                "interval": 5,  # 5 minutes
            }
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - start) * 1000

            result = {
                "status": r.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "content_length": len(r.content),
                "url": url,
                "pair": kraken_pair,
            }

            if r.status_code == 200:
                try:
                    data = r.json()
                    # Kraken returns: {"result": {pair: [[time, open, high, low, close, vwap, volume, count], ...]}}
                    ohlc_data = data.get("result", {}).get(kraken_pair, [])
                    result["data_points"] = len(ohlc_data)
                    result["sample"] = ohlc_data[0] if ohlc_data else None
                    result["success"] = len(ohlc_data) > 0
                except Exception as e:
                    result["parse_error"] = str(e)[:50]
                    result["success"] = False
            else:
                result["response"] = r.text[:200]
                result["success"] = False

            results["kraken"] = result
    except Exception as e:
        results["kraken"] = {
            "error": type(e).__name__,
            "detail": str(e)[:100],
            "success": False,
        }

    # Test 3: CryptoCompare API (public, free tier available)
    try:
        start = _time.perf_counter()
        with httpx.Client(timeout=10) as client:
            url = "https://min-api.cryptocompare.com/data/v2/histominute"
            params = {
                "fsym": sym,
                "tsym": "USD",
                "limit": 60,  # Get 60 minutes of 1m candles (can aggregate to 5m)
                "aggregate": 1,
            }
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - start) * 1000

            result = {
                "status": r.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "content_length": len(r.content),
                "url": url,
            }

            if r.status_code == 200:
                try:
                    data = r.json()
                    candles = data.get("Data", {}).get("Data", [])
                    result["data_points"] = len(candles)
                    result["sample"] = candles[0] if candles else None
                    result["success"] = len(candles) > 0
                    result["note"] = "1m data (can aggregate to 5m)"
                except Exception as e:
                    result["parse_error"] = str(e)[:50]
                    result["success"] = False
            else:
                result["response"] = r.text[:200]
                result["success"] = False

            results["cryptocompare"] = result
    except Exception as e:
        results["cryptocompare"] = {
            "error": type(e).__name__,
            "detail": str(e)[:100],
            "success": False,
        }

    # Test 4: ByBit API (public OHLC)
    try:
        start = _time.perf_counter()
        with httpx.Client(timeout=10) as client:
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": f"{sym}USDT",
                "interval": "5",  # 5 minutes
                "limit": 200,
            }
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - start) * 1000

            result = {
                "status": r.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "content_length": len(r.content),
                "url": url,
            }

            if r.status_code == 200:
                try:
                    data = r.json()
                    candles = data.get("result", {}).get("list", [])
                    result["data_points"] = len(candles)
                    result["sample"] = candles[0] if candles else None
                    result["success"] = len(candles) > 0
                except Exception as e:
                    result["parse_error"] = str(e)[:50]
                    result["success"] = False
            else:
                result["response"] = r.text[:200]
                result["success"] = False

            results["bybit"] = result
    except Exception as e:
        results["bybit"] = {
            "error": type(e).__name__,
            "detail": str(e)[:100],
            "success": False,
        }

    # Test 5: OKX (OKCoin) Public API
    try:
        start = _time.perf_counter()
        with httpx.Client(timeout=10) as client:
            url = "https://www.okx.com/api/v5/market/candles"
            params = {
                "instId": f"{sym}-USD",
                "bar": "5m",
                "limit": 100,
            }
            r = client.get(url, params=params)
            elapsed_ms = (_time.perf_counter() - start) * 1000

            result = {
                "status": r.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "content_length": len(r.content),
                "url": url,
            }

            if r.status_code == 200:
                try:
                    data = r.json()
                    candles = data.get("data", [])
                    result["data_points"] = len(candles)
                    result["sample"] = candles[0] if candles else None
                    result["success"] = len(candles) > 0
                except Exception as e:
                    result["parse_error"] = str(e)[:50]
                    result["success"] = False
            else:
                result["response"] = r.text[:200]
                result["success"] = False

            results["okx"] = result
    except Exception as e:
        results["okx"] = {
            "error": type(e).__name__,
            "detail": str(e)[:100],
            "success": False,
        }

    # Summary
    successful = [k for k, v in results.items() if v.get("success", False)]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": sym,
        "providers_tested": list(results.keys()),
        "successful_providers": successful,
        "details": results,
        "summary": {
            "total": len(results),
            "working": len(successful),
            "failed": len(results) - len(successful),
        }
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
            df = _yf_history_safe(ticker, period=yf_period, interval="1d", timeout=10)
            if df is not None and not df.empty and len(df) >= min_bars:
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
        df = _yf_history_safe(t, period=yf_period, interval="1d", timeout=10)
        if df is None or df.empty or len(df) < min_bars:
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
                df = _yf_history_safe(ticker, period=yf_period, interval="1d", timeout=10)
                if df is not None and not df.empty and len(df) >= min_bars:
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


@app.get("/api/research/edge-v2")
def research_edge_v2(
    strategy: Optional[str] = Query(None, description="Stratégie recherchée (optionnel)"),
    period: int = Query(36, ge=12, le=60, description="Horizon de recherche en mois"),
    tickers: Optional[str] = Query(None, description="Sous-ensemble tickers séparés par virgule"),
    fast: bool = Query(True, description="Mode rapide avec cache mémoire"),
):
    """
    Recherche Edge v2 multi-couches.
    Endpoint purement informatif: n'autorise aucun trade et ne modifie pas Edge v1.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] if tickers else []

    setup_quality_by_ticker: Dict[str, float] = {}
    ticker_edge_by_ticker: Dict[str, Dict[str, Any]] = {}

    if ticker_list:
        def _hydrate_one(ticker: str):
            try:
                row = analyze_ticker(
                    ticker,
                    strategy=strategy or "standard",
                    exclude_earnings=False,
                    fetch_news=False,
                    use_live_price=False,
                    fetch_earnings=False,
                    fast=True,
                )
                if row is not None:
                    setup_quality_by_ticker[ticker] = float(getattr(row, "quality_score", None) or getattr(row, "score", 0) or 0)
            except Exception:
                pass

            edge = get_cached_edge(ticker, period_months=period)
            if edge is None and not fast:
                df = _get_ohlcv(ticker)
                if df is not None:
                    try:
                        edge = compute_ticker_edge(ticker, df, period_months=period)
                    except Exception:
                        edge = None
            if edge is not None:
                ticker_edge_by_ticker[ticker] = edge

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_hydrate_one, ticker_list))

    payload = build_edge_v2_research_rows(
        strategy=strategy,
        period=period,
        tickers=ticker_list or None,
        setup_quality_by_ticker=setup_quality_by_ticker or None,
        ticker_edge_by_ticker=ticker_edge_by_ticker or None,
    )
    payload["mode"] = "research"
    payload["fast"] = fast
    return payload


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


@app.get("/api/warmup/status")
def warmup_status(scope: str = Query("all")):
    normalized = (scope or "all").strip().lower()
    if normalized not in {"actions", "crypto", "all"}:
        normalized = "all"

    runtime = {
        "app_started_at": _iso(APP_STARTED_AT),
        "uptime_seconds": round(_time.time() - APP_STARTED_AT, 1),
        "last_warmup_actions_started": _iso(LAST_WARMUP_ACTIONS_STARTED),
        "last_warmup_actions_finished": _iso(LAST_WARMUP_ACTIONS_FINISHED),
        "last_warmup_crypto_started": _iso(LAST_WARMUP_CRYPTO_STARTED),
        "last_warmup_crypto_finished": _iso(LAST_WARMUP_CRYPTO_FINISHED),
        "last_restart_detected": _iso(load_cache_state().get("app_started_at") if load_cache_state() else None),
    }
    payload: Dict[str, Any] = {"status": "ok", "scope": normalized, "runtime": runtime}
    payload["persistence"] = get_cache_persistence_status()
    if normalized in {"actions", "all"}:
        payload["actions"] = _actions_cache_snapshot()
        payload["actions_diagnostic"] = _warmup_progress.get("actions", {})
    if normalized in {"crypto", "all"}:
        payload["crypto"] = _crypto_cache_snapshot()
    if normalized in {"actions", "all"}:
        payload["actions_missing"] = _warmup_progress.get("actions", {})
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
    skip_existing: bool = True,
) -> Dict[str, Any]:
    global LAST_WARMUP_ACTIONS_STARTED, LAST_WARMUP_ACTIONS_FINISHED
    LAST_WARMUP_ACTIONS_STARTED = _time.time()
    warmed_tickers: List[str] = []
    edge_computed = 0
    total_tickers = len(ALL_TICKERS)
    batch_size = max(1, min(int(batch_size or 50), 100))
    batch = max(1, int(batch or 1))
    skip_existing = bool(skip_existing)

    current_snapshot = _actions_cache_snapshot()
    current_state = _warmup_progress.get("actions", {})
    if skip_existing and _actions_cache_is_ready(current_snapshot):
        LAST_WARMUP_ACTIONS_FINISHED = _time.time()
        _warmup_progress["actions"] = {
            **current_state,
            "total_tickers": total_tickers,
            "warmed_tickers": current_snapshot.get("screener_results_count", 0),
            "missing_tickers": 0,
            "estimated_batches_remaining": 0,
            "last_batch": "skip_existing",
            "last_slice": "ready",
            "errors": current_state.get("errors", []),
            "batch_history": current_state.get("batch_history", {}),
            "last_failed_endpoint": current_state.get("last_failed_endpoint"),
            "last_failed_batch": current_state.get("last_failed_batch"),
            "last_error_message": current_state.get("last_error_message"),
        }
        _persist_runtime_cache_state()
        return {
            "actions_count": 0,
            "actions_edge_computed": 0,
            "actions_cache": current_snapshot,
            "warmup_batch": {
                "batch": batch,
                "batch_size": batch_size,
                "start_index": 0,
                "end_index": 0,
                "total_batches": max((total_tickers + batch_size - 1) // batch_size, 1),
                "slice_count": 0,
                "skipped_existing": True,
            },
        }

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
    batch_record = {
        "batch": batch,
        "batch_size": batch_size,
        "slice": batch_label,
        "start_index": start,
        "end_index": stop,
        "requested": len(slice_tickers),
        "warmed": 0,
        "errors": [],
        "started_at": _iso(_time.time()),
    }

    # Batch size interne plus petite pour éviter les 502 Railway.
    chunk_size = max(5, min(10, batch_size if batch_size else 10))
    chunk_timeout_seconds = 15
    for chunk_index, chunk_start in enumerate(range(0, len(slice_tickers), chunk_size), start=1):
        chunk = slice_tickers[chunk_start: chunk_start + chunk_size]
        chunk_results, chunk_warmed, chunk_edge = _warmup_actions_chunk(
            chunk,
            include_edge=include_edge,
            limit=limit,
            warnings=warnings,
            errors=errors,
            audit=audit,
            audit_lock=audit_lock,
            batch_record=batch_record,
            timeout_seconds=chunk_timeout_seconds,
        )
        if chunk_results:
            results.extend(chunk_results)
        if chunk_warmed:
            warmed_tickers.extend(chunk_warmed)
        edge_computed += chunk_edge
        batch_record["chunk_count"] = chunk_index
        batch_record["last_chunk_size"] = len(chunk)
        batch_record["last_chunk_warmed"] = len(chunk_warmed)
        batch_record["last_chunk_finished_at"] = _iso(_time.time())
        if chunk_warmed:
            _run_with_timeout(
                "actions_prices_chunk",
                lambda: get_prices(",".join(chunk[: min(len(chunk), 20)])),
                20,
                warnings,
                errors,
            )
        _warmup_progress["actions"] = {
            **_warmup_progress.get("actions", {}),
            "total_tickers": total_tickers,
            "warmed_tickers": len({str(getattr(r, "ticker", "")).upper() for r in results}) or len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])),
            "missing_tickers": max(total_tickers - len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])), 0),
            "estimated_batches_remaining": None,
            "last_batch": batch,
            "last_slice": batch_label,
            "errors": errors[-10:],
            "batch_history": {**_warmup_progress.get("actions", {}).get("batch_history", {}), str(batch): batch_record},
        }
        _persist_runtime_cache_state()

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
                msg = f"actions_edge:{ticker}: {type(exc).__name__}: {str(exc)[:160]}"
                _record_actions_warmup_issue(
                    warnings,
                    errors,
                    endpoint="actions",
                    batch_label=batch_label,
                    message=msg,
                    batch_record=batch_record,
                )

    merged_results = _screener_cache.get(_default_screener_cache_key(), {}).get("data", [])
    missing_tickers = max(total_tickers - len(merged_results), 0)
    estimated_remaining = max((missing_tickers + chunk_size - 1) // chunk_size, 0)
    batch_record["warmed"] = len(warmed_tickers)
    batch_record["finished_at"] = _iso(_time.time())
    batch_record["missing_tickers_after"] = missing_tickers
    batch_record["edge_computed"] = edge_computed
    batch_record["status"] = "ok" if not batch_record.get("errors") else "partial"
    _warmup_progress["actions"] = {
        "total_tickers": total_tickers,
        "warmed_tickers": len(merged_results),
        "missing_tickers": missing_tickers,
        "estimated_batches_remaining": estimated_remaining,
        "last_batch": batch,
        "last_slice": batch_label,
        "errors": errors[-10:],
        "last_failed_endpoint": _warmup_progress.get("actions", {}).get("last_failed_endpoint"),
        "last_failed_batch": _warmup_progress.get("actions", {}).get("last_failed_batch"),
        "last_error_message": _warmup_progress.get("actions", {}).get("last_error_message"),
        "batch_history": {**_warmup_progress.get("actions", {}).get("batch_history", {}), str(batch): batch_record},
    }
    LAST_WARMUP_ACTIONS_FINISHED = _time.time()
    _persist_runtime_cache_state()

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
            "chunk_size": chunk_size,
            "chunk_timeout_seconds": chunk_timeout_seconds,
        },
    }


def _warmup_missing_actions(
    include_edge: bool,
    limit: Optional[int],
    warnings: List[str],
    errors: List[str],
) -> Dict[str, Any]:
    default_results = _screener_cache.get(_default_screener_cache_key(), {}).get("data", [])
    cached_tickers = {
        str(getattr(row, "ticker", row.get("ticker"))).upper()
        for row in default_results
        if getattr(row, "ticker", None) or isinstance(row, dict) and row.get("ticker")
    }
    missing = [t for t in ALL_TICKERS if t not in cached_tickers]
    global LAST_WARMUP_ACTIONS_STARTED, LAST_WARMUP_ACTIONS_FINISHED
    LAST_WARMUP_ACTIONS_STARTED = LAST_WARMUP_ACTIONS_STARTED or _time.time()
    if not missing:
        return {
            "actions_missing_count": 0,
            "actions_missing_tickers": [],
            "actions_missing_errors": [],
            "actions_missing_warmed": 0,
            "actions_cache": _actions_cache_snapshot(),
        }

    batch_limit = min(limit or 20, len(missing))
    batch_tickers = missing[:batch_limit]
    warmed: List[str] = []
    batch_errors: List[str] = []
    audit = Counter()
    audit_lock = threading.Lock()
    batch_record = {
        "batch": "missing",
        "requested": len(batch_tickers),
        "warmed": 0,
        "errors": [],
        "started_at": _iso(_time.time()),
        "tickers": batch_tickers,
        "chunk_size": max(5, min(10, len(batch_tickers) or 10)),
    }

    chunk_size = batch_record["chunk_size"]
    for chunk_index, chunk_start in enumerate(range(0, len(batch_tickers), chunk_size), start=1):
        chunk = batch_tickers[chunk_start: chunk_start + chunk_size]
        chunk_results, chunk_warmed, _ = _warmup_actions_chunk(
            chunk,
            include_edge=include_edge,
            limit=limit,
            warnings=warnings,
            errors=errors,
            audit=audit,
            audit_lock=audit_lock,
            batch_record=batch_record,
            timeout_seconds=15,
        )
        if chunk_results:
            for res in chunk_results:
                warmed.append(str(getattr(res, "ticker", "")).upper())
            _merge_screener_cache_results(
                _default_screener_cache_key(),
                chunk_results,
                meta={"source": "warmup-missing", "chunk": chunk_index},
            )
        if chunk_warmed:
            _run_with_timeout(
                "actions_prices_missing_chunk",
                lambda: get_prices(",".join(chunk[: min(len(chunk), 20)])),
                20,
                warnings,
                errors,
            )
        batch_record["chunk_count"] = chunk_index
        batch_record["last_chunk_size"] = len(chunk)
        batch_record["last_chunk_warmed"] = len(chunk_warmed)
        batch_record["last_chunk_finished_at"] = _iso(_time.time())
        _warmup_progress["actions"] = {
            **_warmup_progress.get("actions", {}),
            "total_tickers": len(ALL_TICKERS),
            "warmed_tickers": len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])),
            "missing_tickers": max(len(ALL_TICKERS) - len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])), 0),
            "estimated_batches_remaining": None,
            "last_batch": "missing",
            "last_slice": ",".join(batch_tickers[:5]),
            "errors": batch_errors[-10:],
            "last_failed_endpoint": _warmup_progress.get("actions", {}).get("last_failed_endpoint"),
            "last_failed_batch": _warmup_progress.get("actions", {}).get("last_failed_batch"),
            "last_error_message": _warmup_progress.get("actions", {}).get("last_error_message"),
            "batch_history": {**_warmup_progress.get("actions", {}).get("batch_history", {}), "missing": batch_record | {"warmed": len(warmed), "finished_at": _iso(_time.time())}},
        }
        _persist_runtime_cache_state()

    if include_edge and warmed:
        for ticker in warmed:
            df = _get_ohlcv(ticker, allow_download=True)
            if df is None:
                continue
            try:
                compute_ticker_edge(ticker, df, period_months=24)
            except Exception as exc:
                msg = f"actions_missing_edge:{ticker}: {type(exc).__name__}: {str(exc)[:160]}"
                batch_errors.append(msg)
                batch_record["errors"].append(msg)

    _warmup_progress["actions"] = {
        "total_tickers": len(ALL_TICKERS),
        "warmed_tickers": len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])),
        "missing_tickers": max(len(ALL_TICKERS) - len(_screener_cache.get(_default_screener_cache_key(), {}).get("data", [])), 0),
        "estimated_batches_remaining": None,
        "last_batch": "missing",
        "last_slice": ",".join(batch_tickers[:5]),
        "errors": batch_errors[-10:],
        "last_failed_endpoint": _warmup_progress.get("actions", {}).get("last_failed_endpoint"),
        "last_failed_batch": _warmup_progress.get("actions", {}).get("last_failed_batch"),
        "last_error_message": _warmup_progress.get("actions", {}).get("last_error_message"),
        "batch_history": {**_warmup_progress.get("actions", {}).get("batch_history", {}), "missing": batch_record | {"warmed": len(warmed), "finished_at": _iso(_time.time())}},
    }
    LAST_WARMUP_ACTIONS_FINISHED = _time.time()
    _persist_runtime_cache_state()

    return {
        "actions_missing_count": len(missing),
        "actions_missing_tickers": missing,
        "actions_missing_batch_count": len(batch_tickers),
        "actions_missing_warmed": len(warmed),
        "actions_missing_failed": len(batch_errors),
        "actions_missing_remaining": max(len(missing) - len(warmed), 0),
        "actions_missing_errors": batch_errors,
        "actions_cache": _actions_cache_snapshot(),
    }


def _warmup_crypto_intraday(symbols: List[str], interval: str = "5m", timeout_seconds: int = 60) -> Dict[str, Any]:
    """
    Warmup intraday OHLCV cache for specified symbols.

    Returns:
        {
            "warmed": int,
            "failed": int,
            "symbols_ok": List[str],
            "symbols_failed": Dict[str, str],  # {symbol: error_reason}
        }
    """
    from crypto_data import get_crypto_ohlcv_intraday

    warmed = []
    failed = {}

    def _warmup_one(symbol: str):
        try:
            df = get_crypto_ohlcv_intraday(symbol, interval=interval, allow_download=True)
            if df is not None and len(df) >= 20:
                return {"ok": True, "symbol": symbol, "rows": len(df)}
            else:
                return {"ok": False, "symbol": symbol, "error": f"< 20 candles ({len(df) if df is not None else 0})"}
        except Exception as exc:
            return {"ok": False, "symbol": symbol, "error": f"{type(exc).__name__}: {str(exc)[:80]}"}

    started = _time.perf_counter()

    # Parallel warmup with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_warmup_one, sym): sym for sym in symbols}

        try:
            for future in as_completed(futures, timeout=timeout_seconds):
                result = future.result(timeout=1)
                if result["ok"]:
                    warmed.append(result["symbol"])
                else:
                    failed[result["symbol"]] = result["error"]
        except FuturesTimeoutError:
            # Timeout reached
            for sym in symbols:
                if sym not in warmed and sym not in failed:
                    failed[sym] = "timeout"

    elapsed_ms = round((_time.perf_counter() - started) * 1000)

    return {
        "warmed": len(warmed),
        "failed": len(failed),
        "symbols_ok": warmed,
        "symbols_failed": failed,
        "elapsed_ms": elapsed_ms,
        "interval": interval,
    }


def _warmup_crypto(include_edge: bool, limit: Optional[int], warnings: List[str], errors: List[str]) -> Dict[str, Any]:
    global LAST_WARMUP_CRYPTO_STARTED, LAST_WARMUP_CRYPTO_FINISHED
    LAST_WARMUP_CRYPTO_STARTED = _time.time()
    warmed_symbols: List[str] = []
    edge_computed = 0
    previous_regime_cache = dict(_crypto_regime_cache) if isinstance(_crypto_regime_cache, dict) else {}
    previous_regime = previous_regime_cache.get("data") if isinstance(previous_regime_cache, dict) else None
    previous_regime_valid = isinstance(previous_regime, dict) and previous_regime.get("data_status") != "MISSING"

    _run_with_timeout("crypto_prices", lambda: crypto_prices(["BTC", "ETH"]), 20, warnings, errors)

    screener_fast = bool(getattr(_crypto_service_module, "_screener_cache", {}))
    screener_run = _run_with_timeout(
        "crypto_screener",
        lambda: crypto_screener(fast=screener_fast),
        45,
        warnings,
        errors,
    )
    screener_results = screener_run["value"] if screener_run["ok"] and isinstance(screener_run["value"], list) else []

    # Warm Crypto Scalp intraday cache (Tier 1 only at startup)
    intraday_result = _run_with_timeout(
        "crypto_scalp_intraday_tier1",
        lambda: warmup_crypto_scalp_intraday(tier="1", max_workers=6, timeout_seconds=60),
        65,  # 65s timeout for _run_with_timeout wrapper
        warnings,
        errors,
    )
    if intraday_result["ok"]:
        intraday_data = intraday_result["value"]
        print(f"[warmup] Crypto Scalp Tier 1 intraday warmed: {intraday_data['success_count']}/{intraday_data['total_symbols']} success")
    else:
        warnings.append("crypto_scalp_intraday_tier1: failed to warm, will fall back to on-demand")

    regime_run = None
    if previous_regime_valid:
        regime_run = {"ok": True, "value": previous_regime, "duration_ms": 0}
    else:
        regime_run = _run_with_timeout("crypto_regime", lambda: compute_crypto_regime(fast=False), 45, warnings, errors)
        if not regime_run["ok"] and regime_run.get("value") is None:
            warnings.append("crypto_regime: timeout ou indisponible")
        regime_value = regime_run.get("value")
        regime_status = regime_value.get("data_status") if isinstance(regime_value, dict) else None
        if regime_status == "MISSING" and previous_regime_valid:
            _crypto_regime_cache.clear()
            _crypto_regime_cache.update(previous_regime_cache)
            regime_run = {"ok": True, "value": previous_regime, "duration_ms": regime_run.get("duration_ms", 0)}

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

    LAST_WARMUP_CRYPTO_FINISHED = _time.time()
    _persist_runtime_cache_state()

    return {
        "crypto_count": len(warmed_symbols),
        "crypto_edge_computed": edge_computed,
        "crypto_cache": _crypto_cache_snapshot(),
        "crypto_regime_status": (regime_run.get("value") or {}).get("data_status") if isinstance(regime_run, dict) and isinstance(regime_run.get("value"), dict) else None,
        "crypto_regime_reused": previous_regime_valid and regime_run and regime_run.get("value") is previous_regime,
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
    skip_existing: bool = Query(True),
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
        "skip_existing": skip_existing,
    }

    if normalized in {"actions", "all"}:
        try:
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
                    skip_existing=skip_existing,
                )
            )
        except Exception as exc:
            errors.append(f"actions_warmup: {type(exc).__name__}: {str(exc)[:180]}")
            payload["status"] = "partial"
    if normalized == "actions" and batch_size == 50 and batch == 1 and start_index is None and end_index is None and not skip_existing:
        try:
            payload["actions_missing"] = _warmup_missing_actions(
                include_edge=include_edge,
                limit=limit,
                warnings=warnings,
                errors=errors,
            )
        except Exception as exc:
            errors.append(f"actions_missing: {type(exc).__name__}: {str(exc)[:180]}")
            payload["actions_missing"] = {
                "actions_missing_count": 0,
                "actions_missing_tickers": [],
                "actions_missing_batch_count": 0,
                "actions_missing_warmed": 0,
                "actions_missing_failed": 0,
                "actions_missing_remaining": 0,
                "actions_missing_errors": [errors[-1]],
                "actions_cache": _actions_cache_snapshot(),
            }
    if normalized in {"crypto", "all"}:
        try:
            payload.update(_warmup_crypto(include_edge=include_edge, limit=limit, warnings=warnings, errors=errors))
        except Exception as exc:
            errors.append(f"crypto_warmup: {type(exc).__name__}: {str(exc)[:180]}")
            payload["status"] = "partial"

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
    _persist_runtime_cache_state()
    return payload


@app.post("/api/warmup/actions-missing")
def warmup_actions_missing(
    include_edge: bool = Query(False),
    limit: Optional[int] = Query(20, ge=1, le=100),
    skip_existing: bool = Query(True),
    _: None = Depends(require_admin_key),
):
    warnings: List[str] = []
    errors: List[str] = []
    started = _time.perf_counter()
    if skip_existing and _actions_cache_is_ready():
        payload = {
            "actions_missing_count": 0,
            "actions_missing_tickers": [],
            "actions_missing_batch_count": 0,
            "actions_missing_warmed": 0,
            "actions_missing_failed": 0,
            "actions_missing_remaining": 0,
            "actions_missing_errors": [],
            "actions_cache": _actions_cache_snapshot(),
            "status": "ok",
            "warnings": warnings,
            "errors": errors,
            "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
            "updated": _actions_cache_snapshot(),
        }
        return payload
    try:
        payload = _warmup_missing_actions(include_edge=include_edge, limit=limit, warnings=warnings, errors=errors)
    except Exception as exc:
        payload = {
            "actions_missing_count": 0,
            "actions_missing_tickers": [],
            "actions_missing_batch_count": 0,
            "actions_missing_warmed": 0,
            "actions_missing_failed": 1,
            "actions_missing_remaining": 0,
            "actions_missing_errors": [f"actions_missing: {type(exc).__name__}: {str(exc)[:180]}"],
            "actions_cache": _actions_cache_snapshot(),
        }
    payload["status"] = "ok" if not errors else "partial"
    payload["warnings"] = warnings
    payload["errors"] = errors
    payload["duration_ms"] = round((_time.perf_counter() - started) * 1000, 1)
    payload["updated"] = _actions_cache_snapshot()
    _persist_runtime_cache_state()
    return payload


@app.post("/api/warmup/edge-actions")
def warmup_edge_actions(
    grades: Optional[str] = Query("A+,A,B"),
    limit: Optional[int] = Query(None, ge=1, le=100),
    _: None = Depends(require_admin_key),
):
    """
    Compute edge v1 for filtered Actions tickers (by grade).
    Targets: A+, A, B grades only (no REJECT).
    Uses existing screener cache to filter tickers.
    Progressive computation in batches.
    """
    started = _time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []
    edge_computed = 0

    # Parse grades filter
    target_grades = [g.strip().upper() for g in (grades or "A+,A,B").split(",")]
    valid_grades = {"A+", "A", "B"}
    target_grades = [g for g in target_grades if g in valid_grades]
    if not target_grades:
        target_grades = ["A+", "A", "B"]

    try:
        # Get current screener cache (contains all evaluated tickers)
        # Try multiple cache keys to find screener results (user may have filtered by sector/score/signal)
        current_cache = []
        default_key = _default_screener_cache_key()

        # First try default cache
        if default_key in _screener_cache:
            cache_entry = _screener_cache[default_key]
            if isinstance(cache_entry, dict) and "data" in cache_entry:
                current_cache = cache_entry.get("data", [])

        # If default cache empty, try other cache keys
        if not current_cache:
            for cache_key, cache_entry in _screener_cache.items():
                if isinstance(cache_entry, dict) and "data" in cache_entry:
                    data = cache_entry.get("data", [])
                    if isinstance(data, list) and data:
                        current_cache = data
                        warnings.append(f"Using cache key: {cache_key[:50]}")
                        break

        # If still empty, try to run a quick screener pass to populate
        if not current_cache:
            try:
                screener_results = _run_with_timeout(
                    "warmup_edge_screener",
                    lambda: screener(strategy="standard", exclude_earnings=False, sector=None, min_score=0, signal=None, fast=True),
                    45,
                    warnings,
                    errors,
                )
                if screener_results:
                    current_cache = screener_results
            except Exception as e:
                warnings.append(f"Could not pre-warm screener: {type(e).__name__}: {str(e)[:100]}")

        # Filter for target grades
        filtered_tickers = []
        for result in (current_cache or []):
            if hasattr(result, "setup_grade"):
                grade = result.setup_grade
            elif isinstance(result, dict):
                grade = result.get("setup_grade")
            else:
                continue
            if grade in target_grades:
                ticker = result.ticker if hasattr(result, "ticker") else result.get("ticker")
                if ticker:
                    filtered_tickers.append(ticker)

        # Apply limit if specified
        if limit:
            filtered_tickers = filtered_tickers[:limit]

        if not filtered_tickers:
            return {
                "status": "ok",
                "edge_actions_count": 0,
                "edge_actions_computed": 0,
                "edge_actions_tickers": [],
                "edge_actions_failed": 0,
                "results": [],
                "warnings": warnings,
                "errors": errors,
                "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
            }

        # Compute edge for each ticker in batches
        batch_size = 5
        for batch_start in range(0, len(filtered_tickers), batch_size):
            batch = filtered_tickers[batch_start:batch_start + batch_size]
            for ticker in batch:
                try:
                    df = _get_ohlcv(ticker, allow_download=True)
                    if df is None:
                        warnings.append(f"edge_actions:{ticker}: OHLCV unavailable")
                        continue
                    compute_ticker_edge(ticker, df, period_months=24)
                    edge_computed += 1
                except Exception as exc:
                    msg = f"edge_actions:{ticker}: {type(exc).__name__}: {str(exc)[:160]}"
                    errors.append(msg)

        _persist_runtime_cache_state()

        # BUGFIX: Invalidate screener cache so next fetch reflects new edge statuses
        _screener_cache.clear()

        # Build results with edge details for each computed ticker
        results = []
        for ticker in filtered_tickers:
            edge_data, edge_state = get_cached_edge_with_status(ticker)
            if edge_data:
                results.append({
                    "ticker": ticker,
                    "edge_status": edge_data.get("ticker_edge_status", "NO_EDGE"),
                    "train_pf": float(edge_data.get("train_pf", 0.0)),
                    "test_pf": float(edge_data.get("test_pf", 0.0)),
                    "expectancy": float(edge_data.get("expectancy", 0.0)),
                    "trades": int(edge_data.get("total_trades", 0)),
                    "overfit_warning": bool(edge_data.get("overfit_warning", False)),
                    "sample_status": edge_data.get("sample_status", "UNKNOWN"),
                })

        return {
            "status": "ok" if not errors else "partial",
            "edge_actions_count": len(filtered_tickers),
            "edge_actions_computed": edge_computed,
            "edge_actions_tickers": filtered_tickers,
            "edge_actions_failed": len([e for e in errors if "edge_actions:" in e]),
            "results": results,
            "warnings": warnings[-10:],  # Last 10
            "errors": errors[-10:],      # Last 10
            "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
        }

    except Exception as exc:
        return {
            "status": "error",
            "edge_actions_count": 0,
            "edge_actions_computed": 0,
            "edge_actions_tickers": [],
            "edge_actions_failed": 0,
            "results": [],
            "warnings": warnings,
            "errors": [f"warmup_edge_actions: {type(exc).__name__}: {str(exc)[:180]}"],
            "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
        }


@app.post("/api/strategy-edge/compute")
def compute_strategy_edge_single(
    ticker: str = Query(...),
    _: None = Depends(require_admin_key),
):
    """
    Compute edge v1 for a single ticker (targeted from Trade Plan).
    No grade filtering — works for any ticker.
    Used as CTA in Trade Plan when EDGE_NOT_COMPUTED.
    """
    started = _time.perf_counter()
    warnings: List[str] = []
    errors: List[str] = []
    edge_status = "EDGE_NOT_COMPUTED"
    edge_data = {}

    ticker_upper = ticker.upper()

    try:
        # Fetch OHLCV data for ticker
        df = _get_ohlcv(ticker_upper, allow_download=True)
        if df is None:
            msg = f"OHLCV data unavailable for {ticker_upper}"
            warnings.append(msg)
            return {
                "status": "unavailable",
                "ticker": ticker_upper,
                "edge_status": "EDGE_NOT_COMPUTED",
                "message": msg,
                "trades": 0,
                "pf": 0.0,
                "test_pf": 0.0,
                "expectancy": 0.0,
                "overfit": False,
                "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
            }

        # Compute edge
        try:
            result = compute_ticker_edge(ticker_upper, df, period_months=24)
            edge_data = result if isinstance(result, dict) else {}
            edge_status = edge_data.get("ticker_edge_status", "NO_EDGE")

            # BUGFIX: Persist the edge cache after computing
            _persist_runtime_cache_state()

            # BUGFIX: Invalidate screener cache so next fetch reflects new edge status
            _screener_cache.clear()

            return {
                "status": "ok",
                "ticker": ticker_upper,
                "edge_status": edge_status,
                "message": f"Edge calculé pour {ticker_upper}",
                # Edge metrics (detailed)
                "trades": int(edge_data.get("total_trades", 0)),
                "occurrences": int(edge_data.get("total_trades", 0)),  # Same as trades
                "train_pf": float(edge_data.get("pf", 0.0)),
                "test_pf": float(edge_data.get("test_pf", 0.0)),
                "expectancy": float(edge_data.get("expectancy", 0.0)),
                "overfit_warning": bool(edge_data.get("overfit_warning", False)),
                "sample_status": edge_data.get("sample_status", "UNKNOWN"),
                # Metadata
                "period_months": 24,
                "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
            }

        except Exception as exc:
            msg = f"{type(exc).__name__}: {str(exc)[:160]}"
            errors.append(msg)
            return {
                "status": "error",
                "ticker": ticker_upper,
                "edge_status": "EDGE_NOT_COMPUTED",
                "message": f"Calcul échoué: {msg}",
                "trades": 0,
                "pf": 0.0,
                "test_pf": 0.0,
                "expectancy": 0.0,
                "overfit": False,
                "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
            }

    except Exception as exc:
        msg = f"compute_strategy_edge_single: {type(exc).__name__}: {str(exc)[:180]}"
        return {
            "status": "error",
            "ticker": ticker_upper,
            "edge_status": "EDGE_NOT_COMPUTED",
            "message": msg,
            "trades": 0,
            "pf": 0.0,
            "test_pf": 0.0,
            "expectancy": 0.0,
            "overfit": False,
            "duration_ms": round((_time.perf_counter() - started) * 1000, 1),
        }


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
    from fastapi import HTTPException
    try:
        trade = trade_journal_open(trade_id, payload.model_dump(exclude_none=True))
        return {"trade": trade}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


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
