"""
Market Regime Engine — classifie le marché en 5 états et active UNE seule stratégie.

Régimes :
  BULL_TREND       → SPY > SMA200, SPY > SMA50, SMA50 rising, RSI > 55, VIX < 22
  PULLBACK_TREND   → SPY > SMA200, prix proche SMA50 (±6%), RSI 40-60, VIX < 28
  RANGE            → SPY > SMA200 mais sans tendance claire
  HIGH_VOLATILITY  → VIX > 28 (peu importe le reste)
  BEAR_TREND       → SPY < SMA200

Stratégie active par régime :
  BULL_TREND       → BREAKOUT
  PULLBACK_TREND   → PULLBACK
  RANGE            → MEAN_REVERSION
  HIGH_VOLATILITY  → NO_TRADE
  BEAR_TREND       → NO_TRADE

Règle absolue : UNE seule stratégie active à la fois.
Cache TTL : 1h (données daily stables)
"""

import time
import threading
from typing import List

import yfinance as yf
import pandas as pd

from indicators import sma, rsi, sma_slope

# ── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}
_lock  = threading.Lock()
_TTL   = 3600  # 1 heure

# ── Strategy definitions ────────────────────────────────────────────────────────
STRATEGIES = {
    "BREAKOUT": {
        "name":          "Breakout Strategy",
        "description":   "Buy stocks breaking to new highs on strong volume in a bull market",
        "signal_filter": ["Breakout", "Momentum"],
        "min_score":     65,
        "min_rr":        1.5,
        "emoji":         "🚀",
        "color":         "#10b981",
    },
    "PULLBACK": {
        "name":          "Pullback Strategy",
        "description":   "Buy quality stocks pulling back to SMA50 in an uptrend",
        "signal_filter": ["Pullback"],
        "min_score":     60,
        "min_rr":        1.5,
        "emoji":         "📉",
        "color":         "#6366f1",
    },
    "MEAN_REVERSION": {
        "name":          "Mean Reversion Strategy",
        "description":   "Buy oversold stocks near support in a sideways market",
        "signal_filter": ["Pullback", "Neutral"],
        "min_score":     55,
        "min_rr":        1.5,
        "emoji":         "↩️",
        "color":         "#f59e0b",
    },
    "NO_TRADE": {
        "name":          "No Trade",
        "description":   "Market conditions unfavourable — preserve capital",
        "signal_filter": [],
        "min_score":     999,
        "min_rr":        999,
        "emoji":         "🚫",
        "color":         "#ef4444",
    },
}

REGIME_TO_STRATEGY = {
    "BULL_TREND":      "BREAKOUT",
    "PULLBACK_TREND":  "PULLBACK",
    "RANGE":           "MEAN_REVERSION",
    "HIGH_VOLATILITY": "NO_TRADE",
    "BEAR_TREND":      "NO_TRADE",
}

REGIME_LABELS = {
    "BULL_TREND":      "Bull Trend",
    "PULLBACK_TREND":  "Pullback Trend",
    "RANGE":           "Range",
    "HIGH_VOLATILITY": "High Volatility",
    "BEAR_TREND":      "Bear Trend",
    "UNKNOWN":         "Unknown",
}

REGIME_COLORS = {
    "BULL_TREND":      "#10b981",
    "PULLBACK_TREND":  "#6366f1",
    "RANGE":           "#f59e0b",
    "HIGH_VOLATILITY": "#f97316",
    "BEAR_TREND":      "#ef4444",
    "UNKNOWN":         "#6b7280",
}


def _classify(
    spy_price: float,
    spy_sma50: float,
    spy_sma200: float,
    spy_rsi: float,
    sma50_rising: bool,
    vix: float,
) -> tuple[str, List[str], int]:
    """
    Retourne (regime, reasons, confidence).
    Priorité top-down : HIGH_VOL → BEAR → BULL → PULLBACK → RANGE
    """
    # ── 1. HIGH VOLATILITY (VIX > 28, peu importe le reste) ──────────────────
    if vix > 28:
        return "HIGH_VOLATILITY", [
            f"VIX at {vix:.1f} — extremely elevated (threshold: 28)",
            "Risk too high — wait for VIX to normalize below 22",
        ], min(95, 60 + int((vix - 28) * 3))

    # ── 2. BEAR TREND (SPY sous SMA200) ──────────────────────────────────────
    if spy_price < spy_sma200:
        pct_below = (spy_sma200 - spy_price) / spy_sma200 * 100
        return "BEAR_TREND", [
            f"SPY ${spy_price:.0f} below SMA200 ${spy_sma200:.0f} ({pct_below:.1f}% below)",
            "Primary downtrend — no long positions",
            f"VIX {vix:.1f} — additional caution" if vix > 20 else f"VIX {vix:.1f}",
        ], min(95, 60 + int(pct_below * 4))

    # ── 3. BULL TREND (toutes conditions alignées) ────────────────────────────
    above_sma50  = spy_price > spy_sma50
    dist_sma50   = (spy_price - spy_sma50) / spy_sma50 * 100

    bull_conditions = [above_sma50, sma50_rising, spy_rsi > 55, vix < 22]
    bull_score = sum(bull_conditions)

    if bull_score >= 3 and spy_price > spy_sma200:
        reasons = []
        if above_sma50:     reasons.append(f"SPY above SMA50 (${spy_sma50:.0f}) — strong uptrend")
        if sma50_rising:    reasons.append("SMA50 slope rising — momentum accelerating")
        if spy_rsi > 55:    reasons.append(f"RSI {spy_rsi:.0f} — healthy momentum (>55)")
        if vix < 22:        reasons.append(f"VIX {vix:.1f} — calm market (< 22)")
        conf = 50 + bull_score * 10 + (5 if vix < 15 else 0) + (5 if spy_rsi > 60 else 0)
        return "BULL_TREND", reasons, min(95, conf)

    # ── 4. PULLBACK TREND (repli sur SMA50 en uptrend) ────────────────────────
    near_sma50 = abs(dist_sma50) <= 6
    rsi_cooled = 40 <= spy_rsi <= 62
    vix_ok     = vix < 28

    if spy_price > spy_sma200 and (near_sma50 or rsi_cooled) and vix_ok:
        reasons = [
            f"SPY pulling back to SMA50 (${spy_sma50:.0f}) — {dist_sma50:+.1f}%",
            "Uptrend intact (above SMA200)",
        ]
        if rsi_cooled:  reasons.append(f"RSI {spy_rsi:.0f} — momentum cooled, buying opportunity")
        if vix < 22:    reasons.append(f"VIX {vix:.1f} — controllable volatility")
        conf = 55 + (10 if near_sma50 else 0) + (5 if rsi_cooled else 0)
        return "PULLBACK_TREND", reasons, min(80, conf)

    # ── 5. RANGE (pas de tendance claire) ────────────────────────────────────
    reasons = [
        f"SPY ${spy_price:.0f} — no clear trend direction",
        f"RSI {spy_rsi:.0f} — neutral zone",
        f"VIX {vix:.1f}",
    ]
    return "RANGE", reasons, 50


def compute_regime_engine() -> dict:
    """
    Calcule le régime de marché et la stratégie active.
    Cache 1h — thread-safe.

    Retourne :
    {
      regime, regime_label, regime_color,
      active_strategy, strategy_name, strategy_description,
      strategy_emoji, strategy_color, strategy_min_score, strategy_min_rr,
      signal_filter,
      activation_reason, confidence, can_trade,
      spy_price, spy_sma50, spy_sma200, spy_rsi,
      sma50_rising, vix,
      error (optionnel)
    }
    """
    now = time.time()

    with _lock:
        if _cache and (now - _cache.get("ts", 0)) < _TTL:
            return {k: v for k, v in _cache.items() if k != "ts"}

    try:
        # ── Téléchargement SPY ────────────────────────────────────────────────
        spy_df = yf.download("SPY", period="14mo", interval="1d",
                             progress=False, auto_adjust=True)
        if spy_df.empty or len(spy_df) < 210:
            raise ValueError("SPY history insufficient")

        close       = spy_df["Close"].squeeze()
        spy_price   = float(close.iloc[-1])
        spy_sma50   = float(sma(close, 50).iloc[-1])
        spy_sma200  = float(sma(close, 200).iloc[-1])
        spy_rsi_val = float(rsi(close, 14).iloc[-1])
        rising      = sma_slope(close, 50, lookback=10)

        if spy_price <= 0 or spy_sma50 <= 0 or spy_sma200 <= 0:
            raise ValueError("SPY calculated values invalid")

        # ── VIX ───────────────────────────────────────────────────────────────
        vix_val = 20.0
        try:
            vix_df  = yf.download("^VIX", period="5d", interval="1d",
                                  progress=False, auto_adjust=True)
            if not vix_df.empty:
                vix_val = float(vix_df["Close"].squeeze().iloc[-1])
        except Exception:
            pass

        # ── Classification ────────────────────────────────────────────────────
        regime, reasons, confidence = _classify(
            spy_price, spy_sma50, spy_sma200, spy_rsi_val, rising, vix_val,
        )

        # ── Stratégie active ──────────────────────────────────────────────────
        strat_key  = REGIME_TO_STRATEGY[regime]
        strat      = STRATEGIES[strat_key]

        result = {
            # Régime
            "regime":                regime,
            "regime_label":          REGIME_LABELS[regime],
            "regime_color":          REGIME_COLORS[regime],
            # Stratégie
            "active_strategy":       strat_key,
            "strategy_name":         strat["name"],
            "strategy_description":  strat["description"],
            "strategy_emoji":        strat["emoji"],
            "strategy_color":        strat["color"],
            "strategy_min_score":    strat["min_score"],
            "strategy_min_rr":       strat["min_rr"],
            "signal_filter":         strat["signal_filter"],
            # Décision
            "activation_reason":     reasons,
            "confidence":            confidence,
            "can_trade":             strat_key != "NO_TRADE",
            # Données brutes
            "spy_price":             round(spy_price,   2),
            "spy_sma50":             round(spy_sma50,   2),
            "spy_sma200":            round(spy_sma200,  2),
            "spy_rsi":               round(spy_rsi_val, 1),
            "sma50_rising":          rising,
            "vix":                   round(vix_val,     1),
            # Cache
            "ts":                    now,
        }

        with _lock:
            _cache.clear()
            _cache.update(result)

        return {k: v for k, v in result.items() if k != "ts"}

    except Exception as exc:
        fallback = {
            "regime":               "UNKNOWN",
            "regime_label":         "Unknown",
            "regime_color":         "#6b7280",
            "active_strategy":      "NO_TRADE",
            "strategy_name":        "No Trade",
            "strategy_description": "Data unavailable — cannot assess market conditions",
            "strategy_emoji":       "⚠️",
            "strategy_color":       "#6b7280",
            "strategy_min_score":   999,
            "strategy_min_rr":      999,
            "signal_filter":        [],
            "activation_reason":    [f"Data error: {str(exc)[:80]}"],
            "confidence":           0,
            "can_trade":            False,
            "spy_price":            0.0,
            "spy_sma50":            0.0,
            "spy_sma200":           0.0,
            "spy_rsi":              0.0,
            "sma50_rising":         False,
            "vix":                  0.0,
            "error":                str(exc)[:120],
        }
        return fallback
