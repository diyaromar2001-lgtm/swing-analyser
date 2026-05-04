"""
Scope: CRYPTO
"""

from __future__ import annotations

import time as _time
from typing import Dict, Optional

from crypto_data import get_crypto_ohlcv
from crypto_strategy_lab import CRYPTO_LAB_STRATEGIES, build_context_maps, evaluate_crypto_strategy_for_symbol

_edge_cache: Dict[str, dict] = {}
_EDGE_TTL = 86_400
_last_edge_update_ts: float = 0.0


def _status_from(result: Dict) -> str:
    if result.get("overfit_warning"):
        return "OVERFITTED"
    trades = result.get("total_trades", 0)
    pf = result.get("profit_factor", 0.0)
    test_pf = result.get("test_pf", 0.0)
    expectancy = result.get("expectancy", 0.0)
    max_dd = result.get("max_drawdown_pct", 0.0)

    # INSUFFICIENT_SAMPLE: Not enough trades to draw conclusions
    if trades < 8:
        return "INSUFFICIENT_SAMPLE"

    # STRONG_EDGE: Robust backtest with good metrics
    if trades >= 18 and pf >= 1.35 and test_pf >= 1.1 and expectancy > 0 and max_dd >= -30:
        return "STRONG_EDGE"
    # VALID_EDGE: Acceptable performance across metrics
    if trades >= 12 and pf >= 1.15 and test_pf >= 1.0 and expectancy >= 0 and max_dd >= -35:
        return "VALID_EDGE"
    # WEAK_EDGE: Some positive metrics but not robust enough
    if trades >= 8 and pf >= 1.0:
        return "WEAK_EDGE"

    # NO_EDGE: Sufficient sample (>= 8 trades) but metrics are poor
    return "NO_EDGE"


def compute_crypto_edge(symbol: str) -> Dict:
    global _last_edge_update_ts
    sym = symbol.upper()
    now = _time.time()
    cached = _edge_cache.get(sym)
    if cached and (now - cached.get("ts", 0)) < _EDGE_TTL:
        return cached["data"]

    df = get_crypto_ohlcv(sym, "1d")
    if df is None or len(df) < 220:
        data = {
            "symbol": sym,
            "ticker_edge_status": "EDGE_NOT_COMPUTED",  # Changed from NO_EDGE
            "best_strategy": None,
            "best_strategy_name": None,
            "best_strategy_color": "#6b7280",
            "best_strategy_emoji": "",
            "edge_score": 0,
            "train_pf": 0.0,
            "test_pf": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "pf": 0.0,
            "expectancy": 0.0,
            "max_dd": 0.0,
            "overfit_warning": False,
            "overfit_reasons": ["Données OHLCV insuffisantes (< 220 bars)"],
            "all_strategies": [],
            "computed_at": now,
        }
        _edge_cache[sym] = {"ts": now, "data": data}
        _last_edge_update_ts = now
        return data

    ctx_maps = build_context_maps(24)
    results = []
    for strategy_def in CRYPTO_LAB_STRATEGIES:
        result = evaluate_crypto_strategy_for_symbol(
            sym,
            strategy_def,
            period_months=24,
            regime="CRYPTO_BULL",
            ctx_maps=ctx_maps,
        )
        status = _status_from(result)
        results.append({**result, "edge_status": status})

    priority = {
        "STRONG_EDGE": 5,
        "VALID_EDGE": 4,
        "WEAK_EDGE": 3,
        "NO_EDGE": 2,
        "INSUFFICIENT_SAMPLE": 1,
        "OVERFITTED": 0,
    }
    ranked = sorted(results, key=lambda row: (priority.get(row["edge_status"], -1), row.get("score", 0.0)), reverse=True)
    best = ranked[0] if ranked else None
    data = {
        "symbol": sym,
        "ticker_edge_status": best["edge_status"] if best else "EDGE_NOT_COMPUTED",
        "best_strategy": best["key"] if best else None,
        "best_strategy_name": best["name"] if best else None,
        "best_strategy_color": best["color"] if best else "#6b7280",
        "best_strategy_emoji": best["emoji"] if best else "",
        "edge_score": int(round(best.get("score", 0))) if best else 0,
        "train_pf": best.get("train_pf", 0.0) if best else 0.0,
        "test_pf": best.get("test_pf", 0.0) if best else 0.0,
        "total_trades": best.get("total_trades", 0) if best else 0,
        "win_rate": best.get("win_rate", 0.0) if best else 0.0,
        "pf": best.get("profit_factor", 0.0) if best else 0.0,
        "expectancy": best.get("expectancy", 0.0) if best else 0.0,
        "max_dd": best.get("max_drawdown_pct", 0.0) if best else 0.0,
        "overfit_warning": best.get("overfit_warning", False) if best else False,
        "overfit_reasons": best.get("overfit_warnings", []) if best else [],
        "all_strategies": ranked,
        "computed_at": now,
    }
    _edge_cache[sym] = {"ts": now, "data": data}
    _last_edge_update_ts = now
    return data


def get_cached_crypto_edge(symbol: str) -> Optional[Dict]:
    cached = _edge_cache.get(symbol.upper())
    return cached["data"] if cached else None


def clear_crypto_edge_cache(symbol: Optional[str] = None) -> None:
    global _last_edge_update_ts
    if symbol:
        _edge_cache.pop(symbol.upper(), None)
    else:
        _edge_cache.clear()
        _last_edge_update_ts = 0.0
