"""
Edge v2 research helpers.

This module only assembles research-time scores from already audited strategy
results plus light ticker/setup signals passed in from the API layer.
It does not alter the production Edge v1 engine.
"""

from __future__ import annotations

import json
import math
import time
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from tickers import TICKER_SECTOR

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 24 * 3600


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        return json.load(fh)


def _safe_pf(gains: float, losses: float) -> float:
    if losses <= 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def _win_rate(trades: List[dict]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if float(t.get("pnl_dollars", 0) or 0) > 0)
    return wins / len(trades)


def _expectancy(trades: List[dict]) -> float:
    if not trades:
        return 0.0
    return sum(float(t.get("pnl_pct", 0) or 0) for t in trades) / len(trades)


def _max_drawdown_pct(trades: List[dict]) -> float:
    if not trades:
        return 0.0
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        eq += float(t.get("pnl_dollars", 0) or 0)
        peak = max(peak, eq)
        if peak > 0:
            dd = (eq - peak) / max(abs(peak), 1e-9) * 100
        else:
            dd = 0.0
        max_dd = min(max_dd, dd)
    return max_dd


def _normalize_score(value: float, *, center: float, spread: float, cap: float = 100.0) -> float:
    return max(0.0, min(cap, 50.0 + (value - center) * spread))


def _portfolio_score(portfolio: Dict[str, Any]) -> float:
    pf = float(portfolio.get("profit_factor", 0.0) or 0.0)
    test_pf = float(portfolio.get("test_pf", portfolio.get("profit_factor", 0.0)) or 0.0)
    exp = float(portfolio.get("expectancy", 0.0) or 0.0)
    dd = float(portfolio.get("max_drawdown_pct", 0.0) or 0.0)
    win = float(portfolio.get("win_rate", 0.0) or 0.0)
    score = 22.0
    score += max(0.0, min(28.0, (pf - 1.0) * 42.0))
    score += max(0.0, min(18.0, (test_pf - 1.0) * 30.0))
    score += max(-12.0, min(18.0, exp * 9.0))
    score += max(-8.0, min(10.0, (win - 0.45) * 45.0))
    score += max(-12.0, min(12.0, 8.0 + dd * 0.6))
    return max(0.0, min(100.0, score))


def _sector_score(stats: Dict[str, Any]) -> float:
    trades = int(stats.get("trades", 0) or 0)
    pf = float(stats.get("pf", 0.0) or 0.0)
    exp = float(stats.get("expectancy", 0.0) or 0.0)
    score = 20.0
    score += max(-15.0, min(35.0, (pf - 1.0) * 45.0))
    score += max(-10.0, min(25.0, exp * 10.0))
    score += max(0.0, min(10.0, math.log(max(trades, 1), 2) * 2.0))
    return max(0.0, min(100.0, score))


def _regime_score(stats: Dict[str, Any]) -> float:
    trades = int(stats.get("trades", 0) or 0)
    pf = float(stats.get("pf", 0.0) or 0.0)
    exp = float(stats.get("expectancy", 0.0) or 0.0)
    score = 18.0
    score += max(-15.0, min(32.0, (pf - 1.0) * 48.0))
    score += max(-10.0, min(22.0, exp * 11.0))
    score += max(0.0, min(8.0, math.log(max(trades, 1), 2) * 1.5))
    return max(0.0, min(100.0, score))


def _ticker_component(status: Optional[str], ticker_stats: Dict[str, Any]) -> float:
    if status == "STRONG_EDGE":
        return 100.0
    if status == "VALID_EDGE":
        return 82.0
    if status == "WEAK_EDGE":
        return 60.0
    if status == "OVERFITTED":
        return 28.0
    if status == "NO_EDGE":
        n = int(ticker_stats.get("n", 0) or 0)
        if n < 5:
            return 48.0 if ticker_stats.get("pf", 0.0) > 1 and ticker_stats.get("expectancy", 0.0) > 0 else 18.0
        return 16.0
    return 24.0


def _setup_score(setup_quality: Optional[float], row_score: Optional[float]) -> float:
    base = setup_quality if setup_quality is not None else row_score
    if base is None:
        return 50.0
    return max(0.0, min(100.0, float(base)))


def _status_from_score(score: float, *, sample_status: str, sector_status: str, regime_status: str, overfit: bool) -> str:
    if sector_status == "V2_BLOCKED_SECTOR":
        return "V2_BLOCKED_SECTOR"
    if regime_status == "V2_BLOCKED_REGIME":
        return "V2_BLOCKED_REGIME"
    if overfit:
        return "V2_OVERFIT_RISK"
    if sample_status == "INSUFFICIENT_SAMPLE":
        return "INSUFFICIENT_SAMPLE"
    if score >= 78:
        return "V2_STRONG_RESEARCH"
    if score >= 62:
        return "V2_VALID_RESEARCH"
    if score >= 50:
        return "V2_WATCHLIST"
    return "NO_EDGE_CONFIRMED"


def _allowed_from_status(status: str) -> bool:
    return status in {"V2_STRONG_RESEARCH", "V2_VALID_RESEARCH", "V2_WATCHLIST", "INSUFFICIENT_SAMPLE"}


def _load_model_catalog() -> Dict[str, Dict[str, Any]]:
    strategy_results = _read_json(_ROOT / "audit_strategy_results.json") or {}
    catalog: Dict[str, Dict[str, Any]] = {}

    actions = strategy_results.get("actions", []) if isinstance(strategy_results, dict) else []
    for item in actions:
        key = str(item.get("key", "")).strip()
        period = int(item.get("period_months", 24) or 24)
        trades = item.get("trades", []) or []
        by_ticker: Dict[str, List[dict]] = defaultdict(list)
        by_sector: Dict[str, List[dict]] = defaultdict(list)
        for t in trades:
            ticker = str(t.get("ticker", "")).upper()
            sector = str(t.get("sector", "Unknown"))
            by_ticker[ticker].append(t)
            by_sector[sector].append(t)
        sector_stats = {
            sector: {
                "trades": len(rows),
                "pf": _safe_pf(
                    sum(max(float(x.get("pnl_dollars", 0) or 0), 0) for x in rows),
                    -sum(min(float(x.get("pnl_dollars", 0) or 0), 0) for x in rows),
                ),
                "expectancy": _expectancy(rows),
            }
            for sector, rows in by_sector.items()
        }
        regime_stats = {}
        # stored strategy audit file doesn't include regimes; leave empty and let caller fall back
        catalog[f"{key}|{period}"] = {
            "key": key,
            "name": item.get("name", key),
            "period": period,
            "portfolio": {
                "profit_factor": float(item.get("profit_factor", 0.0) or 0.0),
                "expectancy": float(item.get("expectancy", 0.0) or 0.0),
                "win_rate": float(item.get("win_rate", 0.0) or 0.0),
                "max_drawdown_pct": float(item.get("max_drawdown_pct", 0.0) or 0.0),
                "test_pf": float(item.get("walk_forward", {}).get("test_pf", item.get("profit_factor", 0.0)) or 0.0),
            },
            "trades": trades,
            "by_ticker": by_ticker,
            "sector_stats": sector_stats,
            "regime_stats": regime_stats,
            "best_ticker_counts": item.get("ticker_returns", {}),
        }

    rsp = _read_json(_ROOT / "audit_relative_strength_pullback.json") or {}
    if "B" in rsp:
        model = rsp["B"].get("36", {})
        trades = (model.get("portfolio", {}) or {}).get("trades", []) or []
        by_ticker = defaultdict(list)
        for t in trades:
            by_ticker[str(t.get("ticker", "")).upper()].append(t)
        catalog["relative_strength_pullback_b|36"] = {
            "key": "relative_strength_pullback_b",
            "name": "Relative Strength Pullback B",
            "period": 36,
            "portfolio": model.get("portfolio", {}),
            "trades": trades,
            "overall": model.get("overall", {}),
            "train": model.get("train", {}),
            "test": model.get("test", {}),
            "statuses": model.get("statuses", {}),
            "sector_stats": model.get("sector_stats", {}),
            "regime_stats": model.get("regime_stats", {}),
            "median_trades_per_ticker": model.get("median_trades_per_ticker", 0),
            "by_ticker": by_ticker,
        }

    slp = _read_json(_ROOT / "audit_sector_leader_pullback.json") or {}
    if "A" in slp:
        model = slp["A"].get("36", {})
        trades = (model.get("portfolio", {}) or {}).get("trades", []) or []
        by_ticker = defaultdict(list)
        for t in trades:
            by_ticker[str(t.get("ticker", "")).upper()].append(t)
        catalog["sector_leader_pullback_a|36"] = {
            "key": "sector_leader_pullback_a",
            "name": "Sector Leader Pullback A",
            "period": 36,
            "portfolio": model.get("portfolio", {}),
            "trades": trades,
            "overall": model.get("overall", {}),
            "train": model.get("train", {}),
            "test": model.get("test", {}),
            "statuses": model.get("statuses", {}),
            "sector_stats": model.get("sector_stats", {}),
            "regime_stats": model.get("regime_stats", {}),
            "median_trades_per_ticker": model.get("median_trades_per_ticker", 0),
            "by_ticker": by_ticker,
        }

    return catalog


_MODEL_CATALOG = _load_model_catalog()


def _model_keys_for_strategy(strategy: Optional[str], period: int) -> List[str]:
    if strategy:
        norm = strategy.strip().lower().replace(" ", "_")
        matches = []
        for key in _MODEL_CATALOG:
            if key.startswith(f"{norm}|") or key.startswith(f"{strategy}|"):
                matches.append(key)
        if matches:
            return matches
    # default research shortlist
    return [
        "relative_strength_pullback_b|36",
        "sector_leader_pullback_a|36",
        "relative_strength|36",
        "pullback_confirmed|36",
        "pullback_trend|36",
        "mean_reversion|36",
        "breakout_quality|36",
    ]


def _model_display_name(model: Dict[str, Any]) -> str:
    return model.get("name") or model.get("key") or "Unknown"


def _dominant(items: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    best_key = ""
    best_val = {"trades": 0, "pf": 0.0, "expectancy": 0.0}
    for key, val in items.items():
        if not isinstance(val, dict):
            continue
        if (
            float(val.get("pf", 0.0) or 0.0) > float(best_val.get("pf", 0.0) or 0.0)
            or (
                float(val.get("pf", 0.0) or 0.0) == float(best_val.get("pf", 0.0) or 0.0)
                and float(val.get("expectancy", 0.0) or 0.0) > float(best_val.get("expectancy", 0.0) or 0.0)
            )
        ):
            best_key = key
            best_val = val
    return best_key, best_val


def build_edge_v2_research_rows(
    *,
    strategy: Optional[str],
    period: int,
    tickers: Optional[Iterable[str]] = None,
    setup_quality_by_ticker: Optional[Dict[str, float]] = None,
    ticker_edge_by_ticker: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    requested = [str(t).upper() for t in tickers] if tickers else []
    cache_key = json.dumps(
        {
            "strategy": strategy or "research",
            "period": period,
            "tickers": requested,
            "setup": bool(setup_quality_by_ticker),
            "edge": bool(ticker_edge_by_ticker),
        },
        sort_keys=True,
    )
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and (now - cached.get("ts", 0)) < _CACHE_TTL:
        return cached["data"]

    model_keys = _model_keys_for_strategy(strategy, period)
    models = [m for k in model_keys if (m := _MODEL_CATALOG.get(k))]
    if not models:
        data = {
            "strategy": strategy,
            "period_months": period,
            "count": 0,
            "results": [],
            "summary": {},
            "status": "degraded",
            "warnings": ["Aucun modèle Edge v2 disponible pour la stratégie demandée"],
            "errors": [],
        }
        safe = _json_safe(data)
        _CACHE[cache_key] = {"ts": now, "data": safe}
        return safe

    all_tickers = requested
    if not all_tickers:
        union = []
        seen = set()
        for model in models:
            for ticker in model.get("by_ticker", {}):
                if ticker not in seen:
                    seen.add(ticker)
                    union.append(ticker)
        all_tickers = union

    rows: List[Dict[str, Any]] = []
    for ticker in all_tickers:
        best_row: Optional[Dict[str, Any]] = None
        for model in models:
            ticker_stats = model.get("by_ticker", {}).get(ticker, [])
            n = len(ticker_stats)
            gains = sum(max(float(t.get("pnl_dollars", 0) or 0), 0) for t in ticker_stats)
            losses = -sum(min(float(t.get("pnl_dollars", 0) or 0), 0) for t in ticker_stats)
            pf = _safe_pf(gains, losses)
            expectancy = _expectancy(ticker_stats)
            sample_status = "INSUFFICIENT_SAMPLE" if n < 5 else ("NO_EDGE_CONFIRMED" if pf <= 1.0 or expectancy <= 0 else "SAMPLED_OK")
            sector = str(TICKER_SECTOR.get(ticker, ticker_stats[0].get("sector", "Unknown") if ticker_stats else "Unknown"))
            sector_stats = model.get("sector_stats", {}).get(sector, {})
            regime_stats = model.get("regime_stats", {})
            # choose dominant regime in the model if available, else BULL as a neutral default
            regime_key, regime_stat = _dominant(regime_stats) if regime_stats else ("BULL_TREND", {"trades": 0, "pf": 1.05, "expectancy": 0.1})
            if not regime_key:
                regime_key = "BULL_TREND"
            sector_status = (
                "V2_BLOCKED_SECTOR"
                if float(sector_stats.get("pf", 0.0) or 0.0) <= 1.0 or float(sector_stats.get("expectancy", 0.0) or 0.0) <= 0
                else ("SECTOR_EDGE_CONFIRMED" if int(sector_stats.get("trades", 0) or 0) >= 20 else "SECTOR_EDGE_PROMISING")
            )
            regime_status = (
                "V2_BLOCKED_REGIME"
                if regime_key in {"BEAR", "BEAR_TREND", "HIGH_VOLATILITY"} or float(regime_stat.get("pf", 0.0) or 0.0) <= 1.0 or float(regime_stat.get("expectancy", 0.0) or 0.0) <= 0
                else ("REGIME_EDGE_CONFIRMED" if int(regime_stat.get("trades", 0) or 0) >= 20 else "REGIME_EDGE_PROMISING")
            )

            setup_quality = None
            if setup_quality_by_ticker:
                setup_quality = setup_quality_by_ticker.get(ticker)
            ticker_edge_info = (ticker_edge_by_ticker or {}).get(ticker, {})
            ticker_edge_status = ticker_edge_info.get("ticker_edge_status")
            overfit = bool(ticker_edge_info.get("overfit_warning"))
            ticker_score = _ticker_component(ticker_edge_status, {"n": n, "pf": pf, "expectancy": expectancy})

            portfolio_score = _portfolio_score(model.get("portfolio", {}))
            sector_score = _sector_score(sector_stats)
            regime_score = _regime_score(regime_stat)
            setup_score = _setup_score(setup_quality, None)

            combined = (
                0.35 * portfolio_score
                + 0.25 * sector_score
                + 0.20 * regime_score
                + 0.10 * ticker_score
                + 0.10 * setup_score
            )

            reasons: List[str] = []
            warnings: List[str] = []
            if sample_status == "INSUFFICIENT_SAMPLE":
                reasons.append("Échantillon ticker trop faible")
                if sector_status == "V2_BLOCKED_SECTOR":
                    reasons.append(f"Secteur {sector} trop faible")
            if regime_status == "V2_BLOCKED_REGIME":
                reasons.append(f"Régime {regime_key} bloqué")
            if ticker_edge_status in {"NO_EDGE", "OVERFITTED"}:
                warnings.append(f"Ticker v1: {ticker_edge_status or 'NO_EDGE'}")
            if overfit:
                warnings.append("Ticker en risque d'overfit")
            if n < 5 and portfolio_score >= 60 and sector_score >= 60 and regime_score >= 60:
                reasons.append("Insufficient sample mais contexte fort")
            if not reasons:
                reasons.append(f"Strategy {model.get('name', model.get('key'))} active")

            status = _status_from_score(
                combined,
                sample_status=sample_status,
                sector_status=sector_status,
                regime_status=regime_status,
                overfit=overfit,
            )
            allowed = _allowed_from_status(status) and status not in {"NO_EDGE_CONFIRMED", "V2_BLOCKED_SECTOR", "V2_BLOCKED_REGIME", "V2_OVERFIT_RISK"}
            if sample_status == "INSUFFICIENT_SAMPLE" and sector_status != "V2_BLOCKED_SECTOR" and regime_status != "V2_BLOCKED_REGIME":
                allowed = True
            if status == "NO_EDGE_CONFIRMED":
                allowed = False

            candidate = {
                "ticker": ticker,
                "strategy_name": _model_display_name(model),
                "edge_v2_score": round(combined, 1),
                "edge_v2_status": status,
                "strategy_portfolio_edge_score": round(portfolio_score, 1),
                "sector_edge_score": round(sector_score, 1),
                "regime_edge_score": round(regime_score, 1),
                "ticker_edge_component": round(ticker_score, 1),
                "setup_quality_score": round(setup_score, 1),
                "sample_status": sample_status,
                "sector_status": sector_status,
                "regime_status": regime_status,
                "allowed_by_v2_research": allowed,
                "reasons": reasons,
                "warnings": warnings,
                "edge_v2_strategy_key": model.get("key"),
                "edge_v2_period_months": model.get("period", period),
                "edge_v2_ticker_trades": n,
                "edge_v2_ticker_pf": round(pf, 2),
                "edge_v2_ticker_expectancy": round(expectancy, 2),
                "edge_v2_ticker_status": ticker_edge_status or "NO_EDGE",
            }

            if best_row is None or float(candidate["edge_v2_score"]) > float(best_row["edge_v2_score"]):
                best_row = candidate

        if best_row:
            rows.append(best_row)

    # summary
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["edge_v2_status"]] = counts.get(row["edge_v2_status"], 0) + 1

    data = {
        "strategy": strategy or "research",
        "period_months": period,
        "count": len(rows),
        "results": rows,
        "status": "ok" if rows else "degraded",
        "warnings": [],
        "errors": [],
        "summary": {
            "status_counts": counts,
            "allowed_count": sum(1 for row in rows if row["allowed_by_v2_research"]),
            "strong_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_STRONG_RESEARCH"),
            "valid_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_VALID_RESEARCH"),
            "watchlist_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_WATCHLIST"),
            "insufficient_count": sum(1 for row in rows if row["edge_v2_status"] == "INSUFFICIENT_SAMPLE"),
            "blocked_sector_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_BLOCKED_SECTOR"),
            "blocked_regime_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_BLOCKED_REGIME"),
            "overfit_count": sum(1 for row in rows if row["edge_v2_status"] == "V2_OVERFIT_RISK"),
        },
    }
    safe = _json_safe(data)
    _CACHE[cache_key] = {"ts": now, "data": safe}
    return safe
