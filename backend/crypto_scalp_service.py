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
from crypto_signal_enhancer import enhance_scalp_signal, determine_scalp_side

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
    has_valid_data = ohlcv is not None and len(ohlcv) >= 20

    if not has_valid_data:
        result["data_status"] = "UNAVAILABLE"
        result["blocked_reasons"].append("Intraday data unavailable (< 20 candles)")
        # DON'T return early - continue to apply Phase 3A enhancement
        result["scalp_score"] = 0
        result["scalp_grade"] = "SCALP_REJECT"
        result["long_score"] = 0
        result["short_score"] = 0
        result["signal_reasons"] = []
        score_warnings = []
        ohlcv = None  # Mark as no valid data for later checks
    else:
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
        # DO NOT add soft warnings to blocked_reasons
        # Only hard blockers should be in blocked_reasons

    # ─ Add price tracing fields (informational, no logic change) ──────────
    # These fields are JSON-safe and help debug price sources
    # Note: current_price selection logic unchanged (still uses snapshot)

    # Extract intraday last close for comparison
    intraday_last_close = None
    if has_valid_data:
        try:
            intraday_last_close = float(ohlcv["Close"].iloc[-1])
            if intraday_last_close is not None and intraday_last_close <= 0:
                intraday_last_close = None
        except (ValueError, TypeError, IndexError):
            intraday_last_close = None

    # Add price source and timestamp (DEFENSIVE: force numeric types)
    result["price_source"] = "snapshot"  # Still using snapshot for current logic
    result["displayed_price"] = current_price
    result["intraday_last_close"] = intraday_last_close
    result["snapshot_price"] = current_price  # Both same for now

    # Timestamp: FORCE to numeric (prevent datetime serialization crash)
    ts = price_snap.get("ts", 0)
    try:
        result["price_timestamp"] = float(ts) if ts else 0.0
    except (ValueError, TypeError):
        result["price_timestamp"] = 0.0

    # Price divergence (informational only)
    price_difference_pct = None
    price_suspect = False
    if intraday_last_close is not None and intraday_last_close > 0 and current_price > 0:
        try:
            diff = abs(current_price - intraday_last_close) / intraday_last_close * 100
            if not (diff != diff or diff == float('inf') or diff == float('-inf')):  # Not NaN or Inf
                price_difference_pct = round(diff, 2)
                if diff > 5:
                    price_suspect = True
        except (ValueError, ZeroDivisionError, TypeError):
            price_difference_pct = None
            price_suspect = False

    result["price_suspect"] = price_suspect
    result["price_difference_pct"] = price_difference_pct

    # ─ DATA QUALITY CHECK: Intraday vs Snapshot Divergence ────────────────
    # PROTECTION: Block/warn if intraday data is too different from snapshot
    # This prevents false signals from stale or wrong intraday sources
    data_quality_status = "OK"  # Default
    data_quality_blocked = False

    if price_difference_pct is not None:
        if price_difference_pct > 10:
            # HARD BLOCKER: Divergence too high (>10%)
            data_quality_status = "BLOCKED"
            data_quality_blocked = True
            result["blocked_reasons"].append(
                f"Data quality: intraday divergence {price_difference_pct:.1f}% > 10% threshold"
            )
        elif price_difference_pct > 5:
            # SOFT WARNING: Moderate divergence (5-10%)
            data_quality_status = "WARNING"
            # Will add warning below when signal_warnings is accessible

    result["data_quality_status"] = data_quality_status
    result["data_quality_blocked"] = data_quality_blocked

    # ─ Determine side (LONG/SHORT/NONE) using centralized rule ──────────
    # Rule: LONG if long_score >= 50 AND long_score >= short_score + 10
    #       SHORT if short_score >= 50 AND short_score >= long_score + 10
    #       NONE otherwise (unclear/conflicting direction)
    result["side"] = determine_scalp_side(result["long_score"], result["short_score"])

    if result["side"] == "LONG":
        result["strategy_name"] = _detect_strategy_long(ohlcv, current_price) if ohlcv is not None else None
    elif result["side"] == "SHORT":
        result["strategy_name"] = _detect_strategy_short(ohlcv, current_price) if ohlcv is not None else None
    else:
        # side = NONE: unclear or conflicting direction
        # NOTE: This is a soft warning in Phase 3A, not a hard blocker
        # Will be handled with penalties in enhance_scalp_signal()
        pass

    # ─ Calculate entry/SL/TP ───────────────────────────────────────────
    if result["side"] != "NONE" and ohlcv is not None and len(ohlcv) >= 10:
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

    # ─ Pre-calculate paper_allowed preliminary state ──────────────────────
    # NOTE: Final paper_allowed decision comes from enhance_scalp_signal()
    # This is a preliminary check for basic requirements.
    # Hard blockers that definitely prevent paper trading:
    preliminary_paper_allowed = (
        result["data_status"] == "FRESH"
        and not data_quality_blocked
        and result["scalp_grade"] in ("SCALP_A+", "SCALP_A", "SCALP_B")
        and result["side"] in ("LONG", "SHORT")
        and result["spread_status"] == "OK"
        and result["entry"] is not None
        and result["stop_loss"] is not None
    )

    result["paper_allowed"] = preliminary_paper_allowed

    # Add paper_confidence label based on grade (for UI hints)
    if result["scalp_grade"] == "SCALP_A+":
        result["paper_confidence"] = "HIGH" if preliminary_paper_allowed else "NONE"
    elif result["scalp_grade"] == "SCALP_A":
        result["paper_confidence"] = "GOOD" if preliminary_paper_allowed else "NONE"
    elif result["scalp_grade"] == "SCALP_B":
        result["paper_confidence"] = "MEDIUM" if preliminary_paper_allowed else "NONE"
    else:
        result["paper_confidence"] = "NONE"
        if result["scalp_grade"] == "SCALP_REJECT":
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
    # Separate HARD BLOCKERS (critical failures) from SOFT WARNINGS (penalties)

    # HARD BLOCKERS: Critical failures that prevent any trading or signal
    hard_blockers = []

    # Data quality BLOCKED is a hard blocker
    if data_quality_blocked and price_difference_pct is not None:
        hard_blockers.append(f"Data quality BLOCKED: intraday divergence {price_difference_pct:.1f}% > 10%")

    # Grade REJECT is a hard blocker
    if result["scalp_grade"] == "SCALP_REJECT":
        hard_blockers.append(f"Grade {result['scalp_grade']} — not tradeable")

    # SOFT WARNINGS: Issues that reduce confidence/signal_strength but don't auto-reject
    soft_warnings = list(score_warnings)  # Copy existing warnings from compute_scalp_score

    # "No clear LONG or SHORT signal" is now a SOFT WARNING, not a hard blocker
    if result["side"] == "NONE":
        soft_warnings.append("No clear LONG or SHORT signal")

    # Data quality WARNING (5-10%) is a soft warning with penalty
    if data_quality_status == "WARNING" and price_difference_pct is not None:
        soft_warnings.append(
            f"Data quality warning: intraday divergence {price_difference_pct:.1f}% (5-10% range) — verify before trading"
        )

    # Call enhancer with hard blockers and soft warnings properly separated
    enhanced = enhance_scalp_signal(
        long_score=result["long_score"],
        short_score=result["short_score"],
        scalp_grade=result["scalp_grade"],
        tier=result["tier"],
        data_status=result["data_status"],
        volatility_status=result["volatility_status"],
        spread_status=result["spread_status"],
        data_quality_status=data_quality_status,  # Pass DQ status explicitly
        data_quality_blocked=data_quality_blocked,  # Pass DQ blocker explicitly
        spread_bps=result.get("spread_bps", 0),
        estimated_roundtrip_cost_pct=result.get("estimated_roundtrip_cost_pct", 0.0),
        paper_allowed=result["paper_allowed"],
        blocked_reasons=hard_blockers,  # Only critical hard blockers
        signals=result["signal_reasons"],
        warnings=soft_warnings,  # Soft warnings for penalties
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


def warmup_crypto_scalp_intraday(
    tier: str = "all",
    max_workers: int = 6,
    timeout_seconds: int = 90
) -> Dict[str, Any]:
    """
    Warm intraday 5m cache for Crypto Scalp symbols.

    Args:
        tier: "1" (5 symbols), "2" (27 symbols), "all" (37 symbols)
        max_workers: Parallel fetch workers (6 default)
        timeout_seconds: Total timeout for all symbols

    Returns:
        {
            "tier": str,
            "total_symbols": int,
            "success_count": int,
            "failed_count": int,
            "failed_symbols": {symbol: error_msg},
            "duration_ms": float,
            "timestamp": str (ISO),
        }
    """
    from datetime import datetime, timezone
    from crypto_data import _log_source_event

    # Select symbols by tier
    if tier == "1":
        symbols = list(SCALP_TIER1_SET)  # 5
    elif tier == "2":
        symbols = list(SCALP_TIER1_SET | SCALP_TIER2_SET)  # 27
    else:  # "all"
        symbols = list(SCALP_WATCH_UNIVERSE)  # 37

    from crypto_data import _intraday_provider_used

    started = _time.perf_counter()
    success_count = 0
    failed_symbols = {}
    symbol_results = {}  # Track provider and candles per symbol

    def _warm_one(sym: str):
        """Warm one symbol's intraday cache."""
        start = _time.perf_counter()
        try:
            df = get_crypto_ohlcv_intraday(sym, interval="5m", allow_download=True)
            elapsed_ms = (_time.perf_counter() - start) * 1000
            if df is not None and len(df) >= 20:
                provider = _intraday_provider_used.get(sym, "UNKNOWN")
                return (True, sym, len(df), provider, elapsed_ms)
            else:
                candle_count = len(df) if df is not None else 0
                df_info = "None" if df is None else f"{candle_count} rows"
                return (False, sym, 0, "NONE", elapsed_ms, f"insufficient data ({df_info})")
        except Exception as exc:
            elapsed_ms = (_time.perf_counter() - start) * 1000
            error_msg = f"{type(exc).__name__}: {str(exc)[:60]}"
            return (False, sym, 0, "NONE", elapsed_ms, error_msg)

    # Parallel warmup with timeout
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_warm_one, sym): sym for sym in symbols}

            for future in as_completed(futures, timeout=timeout_seconds):
                result = future.result(timeout=1)
                if result[0]:  # Success
                    ok, sym, candles, provider, elapsed_ms = result
                    success_count += 1
                    symbol_results[sym] = {
                        "status": "success",
                        "candles_count": candles,
                        "provider": provider,
                        "elapsed_ms": round(elapsed_ms, 1),
                    }
                    try:
                        _log_source_event("OK", "scalp-warmup", sym, "intraday_5m", 0, f"success ({candles} candles, {provider})")
                    except:
                        pass
                else:  # Failure
                    ok, sym, candles, provider, elapsed_ms, error_msg = result
                    failed_symbols[sym] = error_msg
                    symbol_results[sym] = {
                        "status": "failed",
                        "error": error_msg,
                        "elapsed_ms": round(elapsed_ms, 1),
                    }
                    try:
                        _log_source_event("FAIL", "scalp-warmup", sym, "intraday_5m", 0, error_msg)
                    except:
                        pass
    except Exception as exc:
        # Timeout or execution error
        for sym in symbols:
            if sym not in failed_symbols:
                failed_symbols[sym] = f"timeout ({type(exc).__name__})"
                symbol_results[sym] = {
                    "status": "timeout",
                    "error": f"timeout ({type(exc).__name__})",
                }

    elapsed_ms = (_time.perf_counter() - started) * 1000

    return {
        "tier": tier,
        "total_symbols": len(symbols),
        "success_count": success_count,
        "failed_count": len(failed_symbols),
        "failed_symbols": failed_symbols,
        "symbol_results": symbol_results,
        "duration_ms": round(elapsed_ms, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
