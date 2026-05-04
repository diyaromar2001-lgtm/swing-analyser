"""
Scope: CRYPTO
"""

from __future__ import annotations

import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pandas as pd

from crypto_data import (
    PRICE_TTL,
    OHLCV_4H_TTL,
    OHLCV_DAILY_TTL,
    available_crypto_symbols,
    crypto_sector,
    get_crypto_data_freshness,
    get_crypto_market_snapshots,
    get_crypto_ohlcv,
    get_crypto_price_snapshot,
)
from crypto_edge import _EDGE_TTL, compute_crypto_edge, get_cached_crypto_edge
from crypto_regime_engine import _CACHE_TTL as CRYPTO_REGIME_TTL, _cache as _crypto_regime_cache, compute_crypto_regime
from crypto_strategy_lab import CRYPTO_LAB_STRATEGIES
from crypto_universe import is_tradable_crypto
from indicators import atr, ema, macd, perf_pct, rsi, sma, support_level
import os

_screener_cache: Dict[str, dict] = {}
_SCREENER_TTL = 60
_last_screener_update_ts: float = 0.0


def _empty_score_detail(details: Dict[str, bool]) -> Dict[str, Any]:
    return {
        "trend": details.get("trend", 0),
        "momentum": details.get("momentum", 0),
        "risk_reward": details.get("risk_reward", 0),
        "relative_strength": details.get("relative_strength", 0),
        "volume_quality": details.get("volume_quality", 0),
        "details": {
            "prix_above_sma200": details.get("prix_above_sma200", False),
            "sma50_above_sma200": details.get("sma50_above_sma200", False),
            "sma50_slope_positive": details.get("sma50_slope_positive", False),
            "near_52w_high": details.get("near_52w_high", False),
            "rsi_ideal_zone": details.get("rsi_ideal_zone", False),
            "macd_positif": details.get("macd_positif", False),
            "perf_3m_positive": details.get("perf_3m_positive", False),
            "outperforms_sp500": details.get("outperforms_sp500", False),
            "volume_eleve": details.get("volume_eleve", False),
            "rr_suffisant": details.get("rr_suffisant", False),
        },
    }


def _classify_grade(score: int, rr_ratio: float, dist_entry_pct: float, rsi_val: float) -> tuple[str, str]:
    if score >= 90 and rr_ratio >= 2.0 and dist_entry_pct <= 2.5 and 52 <= rsi_val <= 68:
        return "A+", "Setup crypto premium — edge + timing + régime alignés"
    if score >= 74 and rr_ratio >= 1.7 and dist_entry_pct <= 5.0 and 45 <= rsi_val <= 70:
        return "A", "Bon setup crypto — confirmation légère ou entrée proche"
    if score >= 58 and rr_ratio >= 1.3:
        return "B", "Setup crypto en formation — watchlist"
    return "REJECT", f"Setup crypto trop faible ({score}/100)"


def _decision_from(
    grade: str,
    setup_status: str,
    edge_status: str,
    overfit_warning: bool,
    rr_ratio: float,
    dist_entry_pct: float,
    regime: str,
    strategy_allowed: bool,
    volatility_pct: float,
    liquid_ok: bool,
) -> str:
    if grade == "REJECT" or setup_status == "INVALID":
        return "SKIP"
    if overfit_warning or edge_status == "OVERFITTED":
        return "SKIP"
    if edge_status in ("NO_EDGE", "WEAK_EDGE"):
        return "WATCHLIST"
    if regime in ("CRYPTO_BEAR", "CRYPTO_HIGH_VOLATILITY", "CRYPTO_NO_TRADE"):
        return "NO_TRADE"
    if not strategy_allowed or not liquid_ok or volatility_pct > 9.0 or rr_ratio < 1.5:
        return "WAIT"
    if grade in ("A+", "A") and dist_entry_pct <= 1.5 and setup_status == "READY":
        return "BUY NOW"
    if grade in ("A+", "A") and dist_entry_pct <= 4.0:
        return "BUY NEAR ENTRY"
    return "WAIT"


def _signal_type(best_strategy_key: Optional[str], regime: str) -> str:
    if best_strategy_key == "btc_eth_trend_breakout":
        return "Breakout"
    if best_strategy_key == "volatility_compression_breakout":
        return "Breakout"
    if best_strategy_key == "momentum_relative_strength":
        return "Momentum"
    if best_strategy_key == "btc_leader_rotation":
        return "Momentum"
    if best_strategy_key == "mean_reversion_range" or regime == "CRYPTO_RANGE":
        return "Neutral"
    return "Pullback"


def _levels(price: float, high: pd.Series, low: pd.Series, ema20_v: float, atr_v: float) -> Dict[str, float]:
    entry = ema20_v if price > ema20_v * 1.02 else price
    support = float(support_level(low, 20))
    stop = max(support, entry - 1.8 * atr_v, entry * 0.90)
    risk = max(entry - stop, entry * 0.01)
    tp1 = entry + 1.5 * risk
    tp2 = entry + 3.0 * risk
    trailing = tp1 - 0.5 * risk
    rr = (tp2 - entry) / max(risk, 0.0001)
    return {
        "entry": round(entry, 4 if entry < 10 else 2),
        "stop_loss": round(stop, 4 if stop < 10 else 2),
        "tp1": round(tp1, 4 if tp1 < 10 else 2),
        "tp2": round(tp2, 4 if tp2 < 10 else 2),
        "take_profit": round(tp2, 4 if tp2 < 10 else 2),
        "trailing_stop": round(trailing, 4 if trailing < 10 else 2),
        "support": round(support, 4 if support < 10 else 2),
        "resistance": round(float(high.iloc[-30:].max()), 4 if price < 10 else 2),
        "rr_ratio": round(rr, 2),
        "risk_now_pct": round((price - stop) / max(price, 0.0001) * 100.0, 2),
        "dist_entry_pct": round((price - entry) / max(entry, 0.0001) * 100.0, 2),
    }


def _get_btc_eth_context(regime_data: Dict[str, Any], fast: bool = False) -> Dict[str, Any]:
    """Get BTC/ETH context for evaluating altcoin tradability.

    Returns:
        Dict with BTC/ETH price-to-SMA context and regime alignment
    """
    btc_price = float(regime_data.get("btc_price", 0.0))
    btc_sma200 = float(regime_data.get("btc_sma200", 0.0))
    eth_price = float(regime_data.get("eth_price", 0.0))
    eth_sma200 = float(regime_data.get("eth_sma200", 0.0))

    btc_above = btc_price > btc_sma200 if btc_sma200 > 0 else False
    eth_above = eth_price > eth_sma200 if eth_sma200 > 0 else False

    return {
        "btc_price": round(btc_price, 2),
        "btc_above_sma200": btc_above,
        "eth_price": round(eth_price, 2),
        "eth_above_sma200": eth_above,
        "regime": regime_data.get("crypto_regime", "UNKNOWN"),
        "status": "OK" if regime_data.get("data_status") == "OK" else "MISSING",
        "confidence": int(regime_data.get("confidence", 0)),
    }


def compute_crypto_execution_authorization(
    symbol: str,
    regime: str,
    setup_status: str,
    setup_grade: str,
    edge_status: str,
    overfit_warning: bool,
    rr_ratio: float,
    dist_entry_pct: float,
    volatility_pct: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    final_decision: str,
    regime_data: Dict[str, Any],
    fast: bool = False,
) -> Dict[str, Any]:
    """Compute Crypto Tradable V1 execution authorization.

    Checks all 12 mandatory conditions for crypto trading.
    Authorization is STRICT: all conditions must pass.

    Args:
        symbol: Crypto symbol (BTC, ETH, etc.)
        regime: Current crypto regime (CRYPTO_BULL, CRYPTO_BEAR, etc.)
        setup_status: Setup status (READY, WAIT, INVALID)
        setup_grade: Setup grade (A+, A, B, REJECT)
        edge_status: Edge status (VALID_EDGE, STRONG_EDGE, WEAK_EDGE, NO_EDGE, OVERFITTED, etc.)
        overfit_warning: Whether overfit warning is active
        rr_ratio: Risk/reward ratio
        dist_entry_pct: Distance to entry as percentage
        volatility_pct: Current volatility percentage
        stop_loss: Stop loss level
        tp1: Take profit 1 level
        tp2: Take profit 2 level
        final_decision: Current final decision (BUY NOW, BUY NEAR ENTRY, WAIT, SKIP, NO_TRADE)
        regime_data: Full regime data dict for BTC/ETH context
        fast: Fast mode flag

    Returns:
        Dict with:
        - crypto_execution_authorized: bool (true only if all 12 conditions pass)
        - crypto_tradable_decision: str (BUY NOW / BUY NEAR ENTRY if authorized, else WATCHLIST/SKIP/NO_TRADE)
        - crypto_blocked_reasons: list of reasons why not authorized
        - crypto_authorized_conditions: list of conditions that are met
        - authorization_checklist: dict of all 12 condition statuses
        - crypto_watchlist_eligible: bool (true if setup not INVALID/REJECT, independent of auth)
        - btc_context: dict with BTC context
        - eth_context: dict with ETH context
    """
    # Feature flag check
    CRYPTO_TRADABLE_V1_ENABLED = os.getenv("CRYPTO_TRADABLE_V1_ENABLED", "true").lower() == "true"

    if not CRYPTO_TRADABLE_V1_ENABLED:
        btc_ctx = _get_btc_eth_context(regime_data, fast)
        eth_ctx = {k.replace("btc_", "eth_"): v for k, v in btc_ctx.items()}
        return {
            "crypto_execution_authorized": False,
            "crypto_tradable_decision": "UNAVAILABLE",
            "crypto_blocked_reasons": ["Crypto Tradable V1 disabled"],
            "crypto_authorized_conditions": [],
            "authorization_checklist": {
                "regime_favorable": False,
                "btc_eth_context_ok": False,
                "setup_grade_sufficient": False,
                "setup_ready": False,
                "entry_near": False,
                "stop_defined": False,
                "tp_defined": False,
                "rr_adequate": False,
                "volatility_acceptable": False,
                "overfit_ok": False,
                "tradable_universe_symbol": False,
                "edge_validated": False,
            },
            "crypto_watchlist_eligible": setup_status not in ("INVALID",),
            "btc_context": btc_ctx,
            "eth_context": eth_ctx,
        }

    # Initialize checks
    blocked_reasons: List[str] = []
    authorized_conditions: List[str] = []
    checklist = {
        "regime_favorable": False,
        "btc_eth_context_ok": False,
        "setup_grade_sufficient": False,
        "setup_ready": False,
        "entry_near": False,
        "stop_defined": False,
        "tp_defined": False,
        "rr_adequate": False,
        "volatility_acceptable": False,
        "overfit_ok": False,
        "tradable_universe_symbol": False,
        "edge_validated": False,
    }

    # Get BTC/ETH context
    btc_ctx = _get_btc_eth_context(regime_data, fast)
    eth_ctx = {k.replace("btc_", "eth_"): v for k, v in btc_ctx.items()}

    # 1. REGIME CHECK: Only CRYPTO_BULL or CRYPTO_PULLBACK
    if regime in ("CRYPTO_BULL", "CRYPTO_PULLBACK"):
        checklist["regime_favorable"] = True
        authorized_conditions.append("✓ Régime favorable (BULL/PULLBACK)")
    else:
        checklist["regime_favorable"] = False
        blocked_reasons.append(f"Régime défavorable: {regime} (only BULL/PULLBACK allow trading)")

    # 2. BTC/ETH CONTEXT: At least one above SMA200
    btc_eth_ok = btc_ctx["btc_above_sma200"] or eth_ctx.get("eth_above_sma200", False)
    if btc_eth_ok:
        checklist["btc_eth_context_ok"] = True
        authorized_conditions.append("✓ BTC/ETH context compatible")
    else:
        checklist["btc_eth_context_ok"] = False
        blocked_reasons.append("BTC/ETH context incompatible (both below SMA200)")

    # 3. SETUP GRADE: A+ or A only
    if setup_grade in ("A+", "A"):
        checklist["setup_grade_sufficient"] = True
        authorized_conditions.append(f"✓ Setup grade sufficient ({setup_grade})")
    else:
        checklist["setup_grade_sufficient"] = False
        blocked_reasons.append(f"Setup grade insufficient: {setup_grade} (need A+ or A)")

    # 4. SETUP READY: Must be READY
    if setup_status == "READY":
        checklist["setup_ready"] = True
        authorized_conditions.append("✓ Setup status READY")
    else:
        checklist["setup_ready"] = False
        blocked_reasons.append(f"Setup not ready: {setup_status}")

    # 5. ENTRY NEAR: Distance ≤ 5%
    entry_near = abs(dist_entry_pct) <= 5.0
    if entry_near:
        checklist["entry_near"] = True
        authorized_conditions.append(f"✓ Entry near ({abs(dist_entry_pct):.1f}%)")
    else:
        checklist["entry_near"] = False
        blocked_reasons.append(f"Entry distance too far: {abs(dist_entry_pct):.1f}% (max 5%)")

    # 6. STOP LOSS DEFINED: Non-zero and reasonable
    if stop_loss > 0:
        checklist["stop_defined"] = True
        authorized_conditions.append("✓ Stop loss defined")
    else:
        checklist["stop_defined"] = False
        blocked_reasons.append("Stop loss not defined")

    # 7. TP1 and TP2 DEFINED: Both non-zero and TP2 > TP1
    tp_ok = tp1 > 0 and tp2 > 0 and tp2 > tp1
    if tp_ok:
        checklist["tp_defined"] = True
        authorized_conditions.append("✓ TP1/TP2 defined")
    else:
        checklist["tp_defined"] = False
        blocked_reasons.append("Take profit levels not properly defined")

    # 8. RISK/REWARD ADEQUATE: ≥ 1.5x
    if rr_ratio >= 1.5:
        checklist["rr_adequate"] = True
        authorized_conditions.append(f"✓ Risk/reward adequate ({rr_ratio:.1f}x)")
    else:
        checklist["rr_adequate"] = False
        blocked_reasons.append(f"Risk/reward insufficient: {rr_ratio:.1f}x (min 1.5x)")

    # 9. VOLATILITY ACCEPTABLE: ≤ 9%
    if volatility_pct <= 9.0:
        checklist["volatility_acceptable"] = True
        authorized_conditions.append(f"✓ Volatility acceptable ({volatility_pct:.1f}%)")
    else:
        checklist["volatility_acceptable"] = False
        blocked_reasons.append(f"Volatility too high: {volatility_pct:.1f}% (max 9%)")

    # 10. NO OVERFIT WARNING
    if not overfit_warning:
        checklist["overfit_ok"] = True
        authorized_conditions.append("✓ No overfit warning")
    else:
        checklist["overfit_ok"] = False
        blocked_reasons.append("Overfit warning detected")

    # 11. TRADABLE UNIVERSE: Symbol in Phase 1 universe (7 symbols)
    if is_tradable_crypto(symbol):
        checklist["tradable_universe_symbol"] = True
        authorized_conditions.append(f"✓ Symbol in Phase 1 tradable universe")
    else:
        checklist["tradable_universe_symbol"] = False
        blocked_reasons.append(f"Symbol {symbol} not in Phase 1 tradable universe")

    # 12. EDGE VALIDATED: VALID_EDGE or STRONG_EDGE only (MANDATORY)
    # This is a HARD BLOCK — edge is not optional, not informational
    if edge_status in ("VALID_EDGE", "STRONG_EDGE"):
        checklist["edge_validated"] = True
        authorized_conditions.append(f"✓ Edge validated ({edge_status})")
    else:
        checklist["edge_validated"] = False
        blocked_reasons.append(f"Edge not validated: {edge_status} (need VALID_EDGE or STRONG_EDGE)")

    # FINAL DECISION
    all_conditions_met = all(checklist.values())
    crypto_execution_authorized = all_conditions_met

    # Determine tradable decision
    if crypto_execution_authorized:
        if abs(dist_entry_pct) <= 1.5 and setup_status == "READY":
            crypto_tradable_decision = "BUY NOW"
        else:
            crypto_tradable_decision = "BUY NEAR ENTRY"
    else:
        # If not authorized, revert to original decision but cannot execute
        crypto_tradable_decision = final_decision if final_decision in ("WAIT", "SKIP", "NO_TRADE") else "WAIT"

    # WATCHLIST ELIGIBILITY: Independent of auth, only blocked by INVALID/REJECT setup
    crypto_watchlist_eligible = setup_status not in ("INVALID",) and setup_grade != "REJECT"

    return {
        "crypto_execution_authorized": crypto_execution_authorized,
        "crypto_tradable_decision": crypto_tradable_decision,
        "crypto_blocked_reasons": blocked_reasons,
        "crypto_authorized_conditions": authorized_conditions,
        "authorization_checklist": checklist,
        "crypto_watchlist_eligible": crypto_watchlist_eligible,
        "btc_context": btc_ctx,
        "eth_context": eth_ctx,
    }


def analyze_crypto_symbol(
    symbol: str,
    regime_data: Optional[Dict[str, Any]] = None,
    fast: bool = False,
) -> Optional[Dict[str, Any]]:
    df = get_crypto_ohlcv(symbol, "1d", allow_download=not fast)
    if df is None or len(df) < 220:
        return None
    h4_df = get_crypto_ohlcv(symbol, "4h", allow_download=not fast)
    price_info = get_crypto_price_snapshot(symbol, allow_download=not fast) or {}
    market_info = get_crypto_market_snapshots(allow_download=not fast).get(symbol, {})
    regime = regime_data or compute_crypto_regime(fast=fast)
    edge = get_cached_crypto_edge(symbol) if fast else (get_cached_crypto_edge(symbol) or compute_crypto_edge(symbol))
    if not edge:
        edge = {
            "ticker_edge_status": "NO_EDGE",
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
            "overfit_reasons": [],
            "all_strategies": [],
        }

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    sma50_s = sma(close, 50)
    sma200_s = sma(close, 200)
    ema20_s = ema(close, 20)
    _, _, macd_hist = macd(close)

    price = float(price_info.get("price") or close.iloc[-1])
    sma50_v = float(sma50_s.iloc[-1])
    sma200_v = float(sma200_s.iloc[-1])
    ema20_v = float(ema20_s.iloc[-1])
    rsi_v = float(rsi(close, 14).iloc[-1])
    macd_v = float(macd_hist.iloc[-1])
    atr_v = float(atr(high, low, close, 14).iloc[-1])
    perf_7d = perf_pct(close, 7)
    perf_30d = perf_pct(close, 30)
    perf_90d = perf_pct(close, 90)
    perf_180d = perf_pct(close, 180)
    volatility_pct = round(atr_v / max(price, 0.0001) * 100.0, 2)
    levels = _levels(price, high, low, ema20_v, atr_v)
    liquid_ok = float(market_info.get("volume_24h", price_info.get("volume_24h", 0.0)) or 0.0) >= 25_000_000

    trend = 0
    momentum = 0
    risk_reward = 0
    relative_strength = 0
    volume_quality = 0
    above_200 = price > sma200_v
    above_50 = sma50_v > sma200_v
    near_high = price >= float(high.iloc[-90:].max()) * 0.82
    rsi_ok = 45 <= rsi_v <= 68
    macd_pos = macd_v > 0
    perf_pos = perf_30d > 0
    outperf_btc = perf_30d > perf_pct(get_crypto_ohlcv("BTC", "1d")["Close"], 30) if get_crypto_ohlcv("BTC", "1d") is not None else False
    vol_ratio = float(volume.iloc[-1]) / max(float(volume.iloc[-20:].mean()), 1.0)
    vol_high = vol_ratio >= 1.15
    rr_ok = levels["rr_ratio"] >= 1.5

    if above_200:
        trend += 10
    if above_50:
        trend += 10
    if price > ema20_v:
        trend += 5
    if near_high:
        trend += 5
    if rsi_ok:
        momentum += 12
    if macd_pos:
        momentum += 6
    if perf_7d > 0:
        momentum += 3
    if perf_pos:
        momentum += 4
    if levels["rr_ratio"] >= 3:
        risk_reward = 20
    elif levels["rr_ratio"] >= 2:
        risk_reward = 15
    elif levels["rr_ratio"] >= 1.5:
        risk_reward = 10
    if outperf_btc:
        relative_strength += 8
    if float(market_info.get("change_7d", 0.0) or 0.0) > 0:
        relative_strength += 4
    if float(market_info.get("market_cap", 0.0) or 0.0) > 1_000_000_000:
        relative_strength += 3
    if vol_high:
        volume_quality += 6
    if liquid_ok:
        volume_quality += 4

    score = int(max(0, min(100, trend + momentum + risk_reward + relative_strength + volume_quality)))
    grade, setup_reason = _classify_grade(score, levels["rr_ratio"], abs(levels["dist_entry_pct"]), rsi_v)
    setup_status = "READY" if grade in ("A+", "A") and abs(levels["dist_entry_pct"]) <= 2.0 else ("INVALID" if grade == "REJECT" or levels["rr_ratio"] < 1.3 else "WAIT")

    best_strategy = edge.get("best_strategy")
    signal_type = _signal_type(best_strategy, regime["crypto_regime"])
    strategy_allowed = best_strategy in {
        row["key"] for row in CRYPTO_LAB_STRATEGIES if regime["crypto_regime"] in row["regimes"]
    }
    final_decision = _decision_from(
        grade=grade,
        setup_status=setup_status,
        edge_status=edge.get("ticker_edge_status", "NO_EDGE"),
        overfit_warning=bool(edge.get("overfit_warning", False)),
        rr_ratio=levels["rr_ratio"],
        dist_entry_pct=abs(levels["dist_entry_pct"]),
        regime=regime["crypto_regime"],
        strategy_allowed=strategy_allowed,
        volatility_pct=volatility_pct,
        liquid_ok=liquid_ok,
    )
    tradable = final_decision in ("BUY NOW", "BUY NEAR ENTRY")
    rejection_reason = ""
    if not tradable:
        if edge.get("ticker_edge_status") in ("NO_EDGE", "WEAK_EDGE"):
            rejection_reason = "Edge non validé historiquement"
        elif edge.get("ticker_edge_status") == "OVERFITTED":
            rejection_reason = "Stratégie overfittée"
        elif regime["crypto_regime"] in ("CRYPTO_BEAR", "CRYPTO_HIGH_VOLATILITY", "CRYPTO_NO_TRADE"):
            rejection_reason = "Régime crypto défavorable"
        elif not liquid_ok:
            rejection_reason = "Liquidité insuffisante"
        elif volatility_pct > 9.0:
            rejection_reason = "Volatilité extrême"
        else:
            rejection_reason = "Conditions incomplètes"

    score_detail = _empty_score_detail(
        {
            "trend": trend,
            "momentum": momentum,
            "risk_reward": risk_reward,
            "relative_strength": relative_strength,
            "volume_quality": volume_quality,
            "prix_above_sma200": above_200,
            "sma50_above_sma200": above_50,
            "sma50_slope_positive": price > sma50_v,
            "near_52w_high": near_high,
            "rsi_ideal_zone": rsi_ok,
            "macd_positif": macd_pos,
            "perf_3m_positive": perf_pos,
            "outperforms_sp500": outperf_btc,
            "volume_eleve": vol_high,
            "rr_suffisant": rr_ok,
        }
    )

    final_score = int(
        0.35 * int(edge.get("edge_score", 0))
        + 0.30 * score
        + 0.20 * min(levels["rr_ratio"] / 3.0, 1.0) * 100
        + 0.15 * max(0, 100 - abs(levels["dist_entry_pct"]) * 10)
    )

    # ── CRYPTO TRADABLE V1 AUTHORIZATION ─────────────────────────────────────────
    # Compute execution authorization for crypto trading
    auth_result = compute_crypto_execution_authorization(
        symbol=symbol,
        regime=regime["crypto_regime"],
        setup_status=setup_status,
        setup_grade=grade,
        edge_status=edge.get("ticker_edge_status", "NO_EDGE"),
        overfit_warning=bool(edge.get("overfit_warning", False)),
        rr_ratio=levels["rr_ratio"],
        dist_entry_pct=abs(levels["dist_entry_pct"]),
        volatility_pct=volatility_pct,
        stop_loss=levels["stop_loss"],
        tp1=levels["tp1"],
        tp2=levels["tp2"],
        final_decision=final_decision,
        regime_data=regime,
        fast=fast,
    )

    return {
        "ticker": symbol,
        "sector": crypto_sector(symbol),
        "price": round(price, 4 if price < 10 else 2),
        "score": score,
        "setup_grade": grade,
        "setup_reason": setup_reason,
        "confidence": min(100, int(score * 0.8 + min(levels["rr_ratio"] * 10, 20))),
        "quality_score": max(0, min(100, int(100 - abs(levels["dist_entry_pct"]) * 12))),
        "category": "BUY NOW" if final_decision == "BUY NOW" else ("WAIT / SMALL POSITION" if final_decision == "BUY NEAR ENTRY" else ("WATCHLIST" if final_decision in ("WAIT", "WATCHLIST") else "AVOID")),
        "position_size": "Partielle (crypto 0.5–1%)" if grade in ("A+", "A") else "Surveiller",
        "signal_type": signal_type,
        "entry": levels["entry"],
        "stop_loss": levels["stop_loss"],
        "sl_type": "ATR",
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "take_profit": levels["take_profit"],
        "trailing_stop": levels["trailing_stop"],
        "resistance": levels["resistance"],
        "support": levels["support"],
        "high_52w": round(float(high.iloc[-365:].max()), 4 if price < 10 else 2),
        "rr_ratio": levels["rr_ratio"],
        "risk_now_pct": levels["risk_now_pct"],
        "dist_entry_pct": levels["dist_entry_pct"],
        "trend_status": "Uptrend crypto" if above_200 else "Weak trend",
        "sma50": round(sma50_v, 4 if sma50_v < 10 else 2),
        "sma200": round(sma200_v, 4 if sma200_v < 10 else 2),
        "rsi_val": round(rsi_v, 1),
        "macd_val": round(macd_v, 4),
        "atr_val": round(atr_v, 4 if atr_v < 10 else 2),
        "perf_3m": round(perf_90d, 2),
        "perf_6m": round(perf_180d, 2),
        "score_detail": score_detail,
        "earnings_date": None,
        "earnings_days": None,
        "earnings_warning": False,
        "setup_status": setup_status,
        "strategy_fit": "BREAKOUT" if signal_type in ("Breakout", "Momentum") else ("MEAN_REVERSION" if signal_type == "Neutral" else "PULLBACK"),
        "risk_filters_status": "OK" if liquid_ok and volatility_pct <= 9.0 else ("CAUTION" if volatility_pct <= 11.0 else "BLOCKED"),
        "risk_filter_reasons": ([] if liquid_ok else ["Liquidité insuffisante"]) + ([] if volatility_pct <= 9.0 else [f"Volatilité {volatility_pct:.1f}%"]),
        "fundamental_risk": "LOW",
        "news_risk": "LOW",
        "sector_rank": "STRONG" if perf_30d > 0 else "NEUTRAL",
        "vix_risk": "HIGH" if volatility_pct > 9.0 else ("MEDIUM" if volatility_pct > 6.5 else "LOW"),
        "final_decision": final_decision,
        "tradable": tradable,
        "rejection_reason": rejection_reason,
        "ticker_edge_status": edge.get("ticker_edge_status", "NO_EDGE"),
        "best_strategy_for_ticker": best_strategy,
        "best_strategy_name": edge.get("best_strategy_name"),
        "best_strategy_color": edge.get("best_strategy_color", "#6b7280"),
        "best_strategy_emoji": edge.get("best_strategy_emoji", ""),
        "edge_score": edge.get("edge_score", 0),
        "edge_train_pf": edge.get("train_pf", 0.0),
        "edge_test_pf": edge.get("test_pf", 0.0),
        "edge_trades": edge.get("total_trades", 0),
        "edge_win_rate": edge.get("win_rate", 0.0),
        "edge_pf": edge.get("pf", 0.0),
        "edge_expectancy": edge.get("expectancy", 0.0),
        "edge_max_dd": edge.get("max_dd", 0.0),
        "overfit_warning": bool(edge.get("overfit_warning", False)),
        "overfit_reasons": edge.get("overfit_reasons", []),
        "final_score": final_score,
        "execution_quality": max(0, min(100, int(100 - abs(levels["dist_entry_pct"]) * 10))),
        "change_pct": price_info.get("change_pct", market_info.get("change_24h")),
        "change_abs": price_info.get("change_abs"),
        "asset_scope": "CRYPTO",
        "volume_24h": float(market_info.get("volume_24h", price_info.get("volume_24h", 0.0)) or 0.0),
        "market_cap": float(market_info.get("market_cap", 0.0) or 0.0),
        "volatility_pct": volatility_pct,
        "liquidity_score": float(market_info.get("liquidity_score", 0.0) or 0.0),
        "avg_hold_days": edge.get("all_strategies", [{}])[0].get("avg_duration_days", 0.0) if edge.get("all_strategies") else 0.0,
        # ── CRYPTO TRADABLE V1 AUTHORIZATION FIELDS ──────────────────────────────
        "crypto_execution_authorized": auth_result.get("crypto_execution_authorized", False),
        "crypto_tradable_decision": auth_result.get("crypto_tradable_decision", "UNAVAILABLE"),
        "crypto_blocked_reasons": auth_result.get("crypto_blocked_reasons", []),
        "crypto_authorized_conditions": auth_result.get("crypto_authorized_conditions", []),
        "authorization_checklist": auth_result.get("authorization_checklist", {}),
        "crypto_watchlist_eligible": auth_result.get("crypto_watchlist_eligible", False),
        "btc_context": auth_result.get("btc_context", {}),
        "eth_context": auth_result.get("eth_context", {}),
        "tradable_universe_symbol": auth_result.get("authorization_checklist", {}).get("tradable_universe_symbol", False),
    }


def crypto_screener(
    sector: Optional[str] = None,
    min_score: int = 0,
    signal: Optional[str] = None,
    fast: bool = False,
) -> List[Dict[str, Any]]:
    global _last_screener_update_ts
    cache_key = f"{sector or ''}|{min_score}|{signal or ''}"
    now = _time.time()
    cached = _screener_cache.get(cache_key)
    if cached and ((now - cached.get("ts", 0)) < _SCREENER_TTL or fast):
        return cached["data"]

    if fast and not cached:
        regime = compute_crypto_regime(fast=True)
    else:
        regime = compute_crypto_regime(fast=fast)
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(analyze_crypto_symbol, symbol, regime, fast): symbol
            for symbol in available_crypto_symbols()
        }
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception:
                row = None
            if row:
                results.append(row)

    if sector:
        results = [row for row in results if row["sector"] == sector]
    if min_score > 0:
        results = [row for row in results if row["score"] >= min_score]
    if signal:
        results = [row for row in results if row["signal_type"] == signal]
    results.sort(key=lambda row: (row.get("final_score", 0), row.get("score", 0)), reverse=True)
    _screener_cache[cache_key] = {"ts": now, "data": results}
    _last_screener_update_ts = now
    return results


def crypto_prices(symbols: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for symbol in symbols:
        snap = get_crypto_price_snapshot(symbol)
        if snap:
            rows.append(
                {
                    "ticker": symbol.upper(),
                    "price": snap["price"],
                    "change_abs": snap["change_abs"],
                    "change_pct": snap["change_pct"],
                }
            )
    return rows


def crypto_data_freshness() -> Dict[str, Any]:
    ts = get_crypto_data_freshness()
    from crypto_edge import _last_edge_update_ts
    from crypto_regime_engine import _last_regime_update_ts

    edge_ts = _last_edge_update_ts
    regime_ts = _last_regime_update_ts or _crypto_regime_cache.get("ts", 0)
    return {
        "price_label": "Prix crypto live approximatif / différé (30–60s)",
        "screener_label": "Analyse crypto daily/4h (cache 1h à 4h)",
        "regime_label": "Crypto regime (cache 1h)",
        "market_context_label": "Crypto market context global (cache 15min)",
        "edge_label": "Crypto edge (cache 24h)",
        "price_ttl_seconds": PRICE_TTL,
        "screener_ttl_seconds": OHLCV_DAILY_TTL,
        "regime_ttl_seconds": CRYPTO_REGIME_TTL,
        "market_context_ttl_seconds": OHLCV_4H_TTL,
        "edge_ttl_seconds": _EDGE_TTL,
        "last_price_update": ts["price_ts"],
        "last_screener_update": _last_screener_update_ts or ts["daily_ts"],
        "last_regime_update": regime_ts,
        "last_market_context_update": ts["market_ts"] or ts["global_ts"] or ts["h4_ts"],
        "last_edge_update": edge_ts,
    }


def clear_crypto_screener_cache() -> None:
    global _last_screener_update_ts
    _screener_cache.clear()
    _last_screener_update_ts = 0.0
