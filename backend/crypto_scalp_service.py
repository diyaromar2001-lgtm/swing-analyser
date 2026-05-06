"""
Scope: CRYPTO SCALP

Service principal pour l'analyse Scalp en Phase 1.
Léger: Ne pas faire d'edge complet (arrivera en Phase 2).
"""

from __future__ import annotations
import time as _time
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from crypto_data import get_crypto_ohlcv_intraday, get_crypto_price_snapshot, get_crypto_data_freshness
from crypto_scalp_score import compute_scalp_score
from crypto_scalp_universe import (
    SCALP_WATCH_UNIVERSE,
    SCALP_TIER1_SET,
    SCALP_TIER2_SET,
    SCALP_TIER3_SET,
    get_scalp_tier,
    is_scalp_watchable,
)
from crypto_cost_calculator import (
    compute_roundtrip_cost_pct,
    estimate_net_rr,
)
from crypto_signal_enhancer import enhance_scalp_signal

_screener_cache: Dict[str, dict] = {}
_SCREENER_TTL = 60
_last_screener_update_ts: float = 0.0


def analyze_crypto_scalp_symbol(symbol: str) -> Dict[str, Any]:
    """
    Analyze a single crypto symbol for scalp trading (Phase 1-2).

    Returns:
        {
            "symbol": str,
            "tier": int (1/2/3),
            "side": "LONG" | "SHORT" | "NONE",
            "scalp_score": int (0-100),
            "scalp_grade": str (SCALP_A+ / A / B / REJECT),
            "long_score": int,
            "short_score": int,
            "strategy_name": str | None (detected pattern),
            "timeframe": str (1m/5m/15m),
            "entry": float | None,
            "stop_loss": float | None,
            "tp1": float | None,
            "tp2": float | None,
            "rr_ratio": float | None,
            "spread_status": str (OK / WARNING / UNAVAILABLE),
            "data_status": str (FRESH / STALE / UNAVAILABLE),
            "volatility_status": str (NORMAL / HIGH / LOW),
            "scalp_execution_authorized": bool (always false in Phase 1),
            "paper_allowed": bool,
            "watchlist_allowed": bool,
            "blocked_reasons": list,
            "signal_reasons": list,
            "spread_bps": int,  # Phase 2: Bid-ask spread in basis points
            "slippage_pct": float,  # Phase 2: Slippage percentage
            "entry_fee_pct": float,  # Phase 2: Entry fee percentage
            "exit_fee_pct": float,  # Phase 2: Exit fee percentage
            "estimated_roundtrip_cost_pct": float,  # Phase 2: Total roundtrip cost
            "estimated_net_rr": float | None,  # Phase 2: Net R/R after costs
        }
    """

    result = {
        "symbol": symbol.upper(),
        "tier": 0,
        "side": "NONE",
        "scalp_score": 0,
        "scalp_grade": "SCALP_REJECT",
        "long_score": 0,
        "short_score": 0,
        "strategy_name": None,
        "timeframe": "5m",  # Default, will update
        "entry": None,
        "stop_loss": None,
        "tp1": None,
        "tp2": None,
        "rr_ratio": None,
        "spread_status": "UNAVAILABLE",
        "data_status": "UNAVAILABLE",
        "volatility_status": "NORMAL",
        "scalp_execution_authorized": False,  # Always false in Phase 1
        "paper_allowed": False,
        "watchlist_allowed": False,
        "blocked_reasons": [],
        "signal_reasons": [],
    }

    # ─ Check if symbol is watchable ──────────────────────────────────────
    sym = symbol.upper()
    if not is_scalp_watchable(sym):
        result["blocked_reasons"].append(f"{sym} not in scalp universe")
        return result

    result["tier"] = get_scalp_tier(sym)
    result["watchlist_allowed"] = True  # All tiers can be watched

    # ─ Fetch price ──────────────────────────────────────────────────────
    price_snap = get_crypto_price_snapshot(sym)
    if not price_snap:
        result["data_status"] = "UNAVAILABLE"
        result["blocked_reasons"].append("Price data unavailable")
        return result

    current_price = price_snap.get("price", 0)
    change_24h = price_snap.get("change_pct", 0)
    volume_24h = price_snap.get("volume_24h", 0)

    # Check data freshness
    freshness = get_crypto_data_freshness()
    price_ts = price_snap.get("ts", 0)
    now = _time.time()
    if now - price_ts > 7200:  # > 2h stale
        result["data_status"] = "STALE"
        result["blocked_reasons"].append("Price data > 2h old")
        return result
    else:
        result["data_status"] = "FRESH"

    # ─ Fetch intraday OHLCV ────────────────────────────────────────────
    # Try 5m first (safer, more stable than 1m)
    ohlcv = get_crypto_ohlcv_intraday(sym, interval="5m")
    timeframe = "5m"

    if ohlcv is None or len(ohlcv) < 20:
        result["data_status"] = "UNAVAILABLE"
        result["blocked_reasons"].append("Intraday data unavailable (< 20 candles)")
        return result

    result["timeframe"] = timeframe

    # ─ Compute scalp score ──────────────────────────────────────────────
    score_result = compute_scalp_score(
        ohlcv_df=ohlcv,
        current_price=current_price,
        volume_24h=volume_24h,
        change_24h_pct=change_24h,
    )

    result["scalp_score"] = score_result.get("scalp_score", 0)
    result["scalp_grade"] = score_result.get("grade", "SCALP_REJECT")
    result["long_score"] = score_result.get("long_score", 0)
    result["short_score"] = score_result.get("short_score", 0)
    result["signal_reasons"] = score_result.get("signals", [])

    # Extract warnings separately for Phase 3A enhancement
    score_warnings = score_result.get("warnings", [])
    result["blocked_reasons"].extend(score_warnings)  # Keep for API response (backward compat)

    # ─ Determine side (LONG/SHORT/NONE) ─────────────────────────────────
    if result["long_score"] >= 60 and result["short_score"] < 50:
        result["side"] = "LONG"
        result["strategy_name"] = _detect_strategy_long(ohlcv, current_price)
    elif result["short_score"] >= 60 and result["long_score"] < 50:
        result["side"] = "SHORT"
        result["strategy_name"] = _detect_strategy_short(ohlcv, current_price)
    else:
        result["side"] = "NONE"
        result["blocked_reasons"].append("No clear LONG or SHORT signal")

    # ─ Calculate entry/SL/TP ───────────────────────────────────────────
    if result["side"] != "NONE" and len(ohlcv) >= 10:
        high_10 = ohlcv["High"].tail(10).max()
        low_10 = ohlcv["Low"].tail(10).min()
        atr_10 = (high_10 - low_10) / 2  # Simple ATR proxy

        if result["side"] == "LONG":
            result["entry"] = round(current_price, 4)
            result["stop_loss"] = round(low_10 - atr_10, 4)
            result["tp1"] = round(current_price + atr_10 * 0.5, 4)
            result["tp2"] = round(current_price + atr_10 * 1.0, 4)
        else:  # SHORT
            result["entry"] = round(current_price, 4)
            result["stop_loss"] = round(high_10 + atr_10, 4)
            result["tp1"] = round(current_price - atr_10 * 0.5, 4)
            result["tp2"] = round(current_price - atr_10 * 1.0, 4)

        # Calculate R/R
        if result["stop_loss"] and result["tp2"]:
            risk = abs(result["entry"] - result["stop_loss"])
            reward = abs(result["tp2"] - result["entry"])
            if risk > 0:
                result["rr_ratio"] = round(reward / risk, 2)

    # ─ Paper allowed if grade is A+, A, or B (Phase 1 Paper Mode) ──────
    # B = Medium confidence, test worthy
    # A = Good confidence, recommended
    # A+ = High confidence, priority
    if result["scalp_grade"] in ("SCALP_A+", "SCALP_A", "SCALP_B"):
        result["paper_allowed"] = True
        # Add confidence label
        if result["scalp_grade"] == "SCALP_A+":
            result["paper_confidence"] = "HIGH"
        elif result["scalp_grade"] == "SCALP_A":
            result["paper_confidence"] = "GOOD"
        else:  # SCALP_B
            result["paper_confidence"] = "MEDIUM"
    else:
        result["paper_allowed"] = False
        result["paper_confidence"] = "NONE"
        result["blocked_reasons"].append(f"Grade {result['scalp_grade']} — watchlist only")

    # ─ Cost Calculations (Phase 2 Paper Trading Enhancement) ────────────
    cost_data = compute_roundtrip_cost_pct(symbol, result["tier"], include_spread=False)
    result["spread_bps"] = cost_data.get("spread_bps")
    result["slippage_pct"] = cost_data.get("slippage_pct")
    result["entry_fee_pct"] = cost_data.get("entry_fee_pct")
    result["exit_fee_pct"] = cost_data.get("exit_fee_pct")
    result["estimated_roundtrip_cost_pct"] = cost_data.get("estimated_roundtrip_cost_pct")

    # Calculate estimated net R/R after costs
    if result.get("rr_ratio"):
        result["estimated_net_rr"] = estimate_net_rr(result["rr_ratio"], cost_data.get("estimated_roundtrip_cost_pct"))
    else:
        result["estimated_net_rr"] = None

    # ─ Volatility Status (Phase 3A: derived from score warnings) ────────
    # Infer from warnings to avoid recalculating ATR
    if "Very low ATR" in score_warnings or "dead market" in " ".join(score_warnings).lower():
        result["volatility_status"] = "LOW"
    elif "High ATR" in score_warnings or "choppy" in " ".join(score_warnings).lower():
        result["volatility_status"] = "HIGH"
    else:
        result["volatility_status"] = "NORMAL"

    # ─ Spread Status (Phase 3A: derived from spread_bps) ────────────────
    spread_bps = result.get("spread_bps")
    if spread_bps is None:
        result["spread_status"] = "UNAVAILABLE"
    elif spread_bps > 100:  # > 100 bps = 1% spread = warning threshold
        result["spread_status"] = "WARNING"
    else:
        result["spread_status"] = "OK"

    # ─ PHASE 3A: Signal Quality Enhancement ──────────────────────────────
    # Separate hard blockers from soft warnings
    hard_blockers = []
    if result["side"] == "NONE":
        hard_blockers.append("No clear LONG or SHORT signal")
    if result["scalp_grade"] == "SCALP_REJECT" or not result["paper_allowed"]:
        # These are already handled by veto rules in enhancer, but keep for consistency
        pass

    # Call enhancer with hard blockers and soft warnings separated
    enhanced = enhance_scalp_signal(
        long_score=result["long_score"],
        short_score=result["short_score"],
        scalp_grade=result["scalp_grade"],
        tier=result["tier"],
        data_status=result["data_status"],
        volatility_status=result["volatility_status"],
        spread_status=result["spread_status"],
        spread_bps=result.get("spread_bps", 0),
        estimated_roundtrip_cost_pct=result.get("estimated_roundtrip_cost_pct", 0.0),
        paper_allowed=result["paper_allowed"],
        blocked_reasons=hard_blockers,  # Only hard blockers (not soft warnings)
        signals=result["signal_reasons"],
        warnings=score_warnings,  # Soft warnings passed separately
    )

    # Add enhancement fields to response
    result["long_strength"] = enhanced.long_strength
    result["short_strength"] = enhanced.short_strength
    result["preferred_side"] = enhanced.preferred_side
    result["signal_strength"] = enhanced.signal_strength
    result["confidence_score"] = enhanced.confidence_score
    result["signal_reasons"] = enhanced.signal_reasons  # May be enriched by enhancer
    result["signal_warnings"] = enhanced.signal_warnings
    result["paper_allowed"] = enhanced.paper_allowed

    return result


def crypto_scalp_screener(
    sort_by: str = "grade",
    reverse: bool = True,
    limit: int = 50,
    min_score: int = 0,
    tier_filter: Optional[int] = None,
    hide_tier3: bool = True,
    hide_reject: bool = False,
) -> Dict[str, Any]:
    """
    Screen all symbols in SCALP_WATCH_UNIVERSE.

    Args:
        sort_by: "grade" (default), "scalp_score", "long_score", "short_score", "tier"
        reverse: True to sort descending
        limit: Max results
        min_score: Minimum scalp_score to include
        tier_filter: Only Tier 1, 2, or 3 (None = all)
        hide_tier3: Hide Tier 3 by default (True)
        hide_reject: Hide SCALP_REJECT by default (False, but can enable)

    Returns:
        {
            "timestamp": int,
            "symbols": list of analyzed symbols (dicts),
            "count": int,
        }
    """
    global _last_screener_update_ts, _screener_cache

    now = _time.time()
    cache_key = f"screener_{sort_by}_{reverse}_{limit}_{min_score}_{tier_filter}_{hide_tier3}_{hide_reject}"

    # Check cache
    if cache_key in _screener_cache:
        cached = _screener_cache[cache_key]
        if now - cached["ts"] < _SCREENER_TTL:
            return cached["data"]

    # Analyze all symbols (parallel)
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(analyze_crypto_scalp_symbol, sym): sym for sym in SCALP_WATCH_UNIVERSE}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception:
                pass

    # Filter tier_filter (explicit request)
    if tier_filter:
        results = [r for r in results if r["tier"] == tier_filter]
    elif hide_tier3:
        # Hide Tier 3 by default unless explicit filter
        results = [r for r in results if r["tier"] in (1, 2)]

    # Filter min_score
    if min_score > 0:
        results = [r for r in results if r["scalp_score"] >= min_score]

    # Filter hide_reject (optional)
    if hide_reject:
        results = [r for r in results if r["scalp_grade"] != "SCALP_REJECT"]

    # Push DATA_UNAVAILABLE to bottom
    def sort_key(x):
        """Sort: grade first, then score, then tier, then data_status, then symbol."""
        grade_order = {"SCALP_A+": 0, "SCALP_A": 1, "SCALP_B": 2, "SCALP_REJECT": 3}
        data_order = {"FRESH": 0, "STALE": 1, "UNAVAILABLE": 999}  # Unavailable last

        grade = grade_order.get(x.get("scalp_grade", "SCALP_REJECT"), 3)
        score = x.get("scalp_score", 0)
        tier = x.get("tier", 0)
        data = data_order.get(x.get("data_status", "UNAVAILABLE"), 999)
        symbol = x.get("symbol", "ZZZZZ")

        # Sort by: grade, then score (desc), then tier (asc), then data, then symbol
        return (grade, -score, tier, data, symbol)

    results.sort(key=sort_key)

    # Limit
    results = results[:limit]

    output = {
        "timestamp": int(now),
        "symbols": results,
        "count": len(results),
    }

    # Cache
    _screener_cache[cache_key] = {"data": output, "ts": now}

    return output


def _detect_strategy_long(df: pd.DataFrame, price: float) -> Optional[str]:
    """Simple strategy detection for LONG signals."""
    if df is None or len(df) < 5:
        return None

    # Placeholder: in Phase 2 will detect real strategies
    # For now, just return generic "Breakout" or "Support"
    high_5 = df["High"].tail(5).max()
    low_5 = df["Low"].tail(5).min()

    if price > high_5 * 0.99:
        return "Breakout"
    elif price < low_5 * 1.01:
        return "Support Test"
    else:
        return "Trend Follow"


def _detect_strategy_short(df: pd.DataFrame, price: float) -> Optional[str]:
    """Simple strategy detection for SHORT signals."""
    if df is None or len(df) < 5:
        return None

    high_5 = df["High"].tail(5).max()
    low_5 = df["Low"].tail(5).min()

    if price < low_5 * 1.01:
        return "Breakdown"
    elif price > high_5 * 0.99:
        return "Resistance Rejection"
    else:
        return "Trend Reverse"
