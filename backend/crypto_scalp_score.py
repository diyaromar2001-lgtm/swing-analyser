"""
Scope: CRYPTO SCALP

Calcul du scalp_score /100 et du grade SCALP_A+ / A / B / REJECT.
Phase 1 (léger): Ne pas faire d'edge complet, juste données techniques.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from indicators import rsi, ema, sma, macd, atr, perf_pct


def compute_scalp_score(
    ohlcv_df: Optional[pd.DataFrame],
    current_price: float,
    volume_24h: float,
    change_24h_pct: float,
) -> Dict[str, Any]:
    """
    Compute scalp_score /100 from intraday technicals (5m-15m).

    Components (max 100):
    - Trend alignment: 20 (price > EMA9 > EMA20, slope positive)
    - Momentum: 20 (RSI 35-65 zone, MACD positive)
    - Volume: 15 (24h volume good for tier, increasing)
    - Structure: 20 (swing highs/lows, distance from entry < 2%)
    - Volatility: 15 (ATR indicates healthy movement, not dead)
    - Support/Resistance: 10 (near support = lower risk)

    Returns:
        {
            "scalp_score": int (0-100),
            "long_score": int (0-100),
            "short_score": int (0-100),
            "trend": int (0-20),
            "momentum": int (0-20),
            "volume_quality": int (0-15),
            "structure": int (0-20),
            "volatility": int (0-15),
            "support_resistance": int (0-10),
            "components": dict with breakdown,
            "signals": list of detected signals,
            "warnings": list of warnings,
        }
    """

    score_dict = {
        "scalp_score": 0,
        "long_score": 0,
        "short_score": 0,
        "trend": 0,
        "momentum": 0,
        "volume_quality": 0,
        "structure": 0,
        "volatility": 0,
        "support_resistance": 0,
        "components": {},
        "signals": [],
        "warnings": [],
    }

    # Missing data = low score
    if ohlcv_df is None or len(ohlcv_df) < 20:
        score_dict["scalp_score"] = 10  # Minimal
        score_dict["warnings"].append("Insufficient intraday data (< 20 candles)")
        return score_dict

    try:
        df = ohlcv_df.copy()

        # ─ Trend: EMA alignment (0-20) — Paper-friendly thresholds ──────────
        ema9_val = ema(df["Close"], period=9).iloc[-1]
        ema20_val = ema(df["Close"], period=20).iloc[-1]
        ema50_val = ema(df["Close"], period=50).iloc[-1] if len(df) >= 50 else ema20_val
        close_val = df["Close"].iloc[-1]

        trend_score = 0
        # Uptrend signals (more lenient than before)
        if close_val > ema9_val > ema20_val > ema50_val:
            trend_score = 16  # Perfect alignment
            score_dict["signals"].append("Strong uptrend (price > EMA9 > EMA20 > EMA50)")
        elif close_val > ema9_val > ema20_val:
            trend_score = 12  # Good alignment
            score_dict["signals"].append("Uptrend confirmed (price > EMA9 > EMA20)")
        elif close_val > ema20_val and ema9_val > ema20_val:
            trend_score = 10  # Both above EMA20
            score_dict["signals"].append("Price and EMA9 above EMA20")
        elif close_val > ema20_val:
            trend_score = 6   # At least above 20
            score_dict["signals"].append("Price above EMA20")
        # Downtrend signals
        elif close_val < ema9_val < ema20_val < ema50_val:
            trend_score = 16  # Perfect downtrend
            score_dict["signals"].append("Strong downtrend (price < EMA9 < EMA20 < EMA50)")
        elif close_val < ema9_val < ema20_val:
            trend_score = 12  # Downtrend confirmed
            score_dict["signals"].append("Downtrend confirmed (price < EMA9 < EMA20)")
        elif close_val < ema20_val and ema9_val < ema20_val:
            trend_score = 10  # Both below EMA20
            score_dict["signals"].append("Price and EMA9 below EMA20")
        elif close_val < ema20_val:
            trend_score = 6   # Below 20
            score_dict["signals"].append("Price below EMA20")
        else:
            trend_score = 4   # Neutral, but not zero

        trend_score = max(0, min(20, trend_score))
        score_dict["trend"] = trend_score

        # ─ Momentum: RSI + MACD (0-20) ──────────────────────────────────────
        rsi_val = rsi(df["Close"], period=14).iloc[-1]

        # MACD: Handle different return types
        macd_val = 0
        macd_signal = 0
        try:
            macd_result = macd(df["Close"], fast=12, slow=26, signal=9)
            if macd_result is not None and not isinstance(macd_result, tuple) and len(macd_result) > 0:
                macd_val = macd_result["MACD"].iloc[-1] if "MACD" in macd_result else 0
                macd_signal = macd_result["Signal"].iloc[-1] if "Signal" in macd_result else 0
        except Exception:
            macd_val = 0
            macd_signal = 0

        momentum_score = 0
        rsi_info = ""

        # RSI: Give credit for healthy zones, not too extreme
        if 35 <= rsi_val <= 65:
            momentum_score += 8
            rsi_info = f"RSI {rsi_val:.0f} (healthy zone)"
        elif 25 < rsi_val < 75:
            momentum_score += 5
            rsi_info = f"RSI {rsi_val:.0f} (acceptable)"
        elif rsi_val <= 25:
            momentum_score += 4
            rsi_info = f"RSI {rsi_val:.0f} (oversold)"
        elif rsi_val >= 75:
            momentum_score += 4
            rsi_info = f"RSI {rsi_val:.0f} (overbought)"
        else:
            momentum_score += 2

        # MACD: Give credit for alignment, but not too harsh for neutral
        if macd_val > macd_signal:
            momentum_score += 8
            score_dict["signals"].append("MACD bullish cross above signal")
        elif macd_val < macd_signal:
            momentum_score += 4  # Changed from 0 to 4: bearish is still useful info
            score_dict["signals"].append("MACD bearish cross below signal")
        else:
            momentum_score += 2

        momentum_score = max(0, min(20, momentum_score))
        score_dict["momentum"] = momentum_score

        # ─ Volume Quality (0-15) ───────────────────────────────────────────
        vol_score = 0
        recent_vol = df["Volume"].tail(5).mean()
        overall_vol = df["Volume"].mean()

        if recent_vol > overall_vol * 1.3:
            vol_score += 10
            score_dict["signals"].append("Volume surge last 5 candles")
        elif recent_vol > overall_vol * 1.1:
            vol_score += 6
            score_dict["signals"].append("Volume above average")
        elif recent_vol > overall_vol * 0.8:
            vol_score += 4  # Changed from 2: Normal volume still acceptable
            score_dict["signals"].append("Volume normal")
        else:
            vol_score += 1
            score_dict["warnings"].append("Volume declining")

        # 24h volume gives tier bonus, not score weight
        if volume_24h > 500_000_000:  # $500M+ = excellent for scalp
            vol_score += 4
        elif volume_24h > 100_000_000:  # $100M+ = good
            vol_score += 2
        else:
            vol_score += 0

        vol_score = max(0, min(15, vol_score))
        score_dict["volume_quality"] = vol_score

        # ─ Structure: Price position in range (0-20) ───────────────────────
        struct_score = 0
        high_20 = df["High"].tail(20).max()
        low_20 = df["Low"].tail(20).min()
        range_20 = high_20 - low_20

        # Position in range: 0% = at low, 100% = at high
        if range_20 > 0:
            position_pct = (close_val - low_20) / range_20 * 100
        else:
            position_pct = 50

        # Give points for being at interesting levels
        if 95 < position_pct <= 100:  # Very close to high
            struct_score += 8
            score_dict["signals"].append(f"Price near 20-candle high ({position_pct:.1f}%)")
        elif 0 <= position_pct < 5:  # Very close to low
            struct_score += 8
            score_dict["signals"].append(f"Price near 20-candle low ({position_pct:.1f}%)")
        elif 80 < position_pct < 95 or 5 <= position_pct < 20:  # In upper/lower tercile
            struct_score += 5
            score_dict["signals"].append(f"Price in extremity zone ({position_pct:.1f}%)")
        else:  # Mid-range (30-70%)
            struct_score += 3  # Changed from 2: mid-range still has value
            score_dict["signals"].append(f"Price in mid-range ({position_pct:.1f}%)")

        struct_score = max(0, min(20, struct_score))
        score_dict["structure"] = struct_score

        # ─ Volatility: ATR tells us trading range (0-15) ────────────────────
        atr_val = atr(df["High"], df["Low"], df["Close"], period=14).iloc[-1]
        atr_pct = (atr_val / close_val * 100) if close_val > 0 else 0

        volatility_score = 0
        if 0.5 < atr_pct < 5:  # Healthy intraday range
            volatility_score += 12
            score_dict["signals"].append(f"ATR {atr_pct:.2f}% (good scalp volatility)")
        elif atr_pct <= 0.5:
            volatility_score += 2
            score_dict["warnings"].append("Very low ATR (dead market)")
        elif atr_pct >= 5:
            volatility_score += 5
            score_dict["warnings"].append("High ATR (choppy, risky)")

        volatility_score = max(0, min(15, volatility_score))
        score_dict["volatility"] = volatility_score

        # ─ Support/Resistance: Distance from major pivots (0-10) ────────────
        sr_score = 0
        # Simple: if close is within 1% of 50-period SMA = near support/resistance
        sma50_val = sma(df["Close"], period=50).iloc[-1] if len(df) >= 50 else close_val
        dist_sma50 = abs(close_val - sma50_val) / sma50_val * 100 if sma50_val > 0 else 0

        if dist_sma50 < 1:
            sr_score += 8
            score_dict["signals"].append(f"Near SMA50 (support/resistance {dist_sma50:.2f}% away)")
        elif dist_sma50 < 2:
            sr_score += 5
        else:
            sr_score += 2

        sr_score = max(0, min(10, sr_score))
        score_dict["support_resistance"] = sr_score

        # ─ Total scalp_score ────────────────────────────────────────────────
        # Components: trend (20) + momentum (20) + vol_quality (15) + struct (20) + volatility (15) + sr (10) = 100 max
        total = (
            trend_score +
            momentum_score +
            vol_score +  # Volume quality
            struct_score +
            volatility_score +  # ATR volatility
            sr_score
        )
        total = max(0, min(100, total))
        score_dict["scalp_score"] = total

        # ─ Long/Short signals ──────────────────────────────────────────────
        # Long = uptrend + bullish momentum + structure support
        long = 0
        if trend_score >= 12:
            long += 40
        if momentum_score >= 12:
            long += 30
        if struct_score >= 12:
            long += 20
        if rsi_val < 50:
            long += 10  # Room to run
        long = max(0, min(100, long))
        score_dict["long_score"] = long

        # Short = downtrend + bearish momentum + resistance
        short = 0
        if trend_score >= 12 and close_val < ema20_val:  # Downtrend
            short += 40
        if momentum_score >= 8 and macd_val < macd_signal:  # Bearish
            short += 30
        if struct_score >= 8:  # Resistance detected
            short += 20
        if rsi_val > 50:
            short += 10  # Room to fall
        short = max(0, min(100, short))
        score_dict["short_score"] = short

        # ─ Grade ───────────────────────────────────────────────────────────
        grade = _classify_scalp_grade(total, long, short, rsi_val)
        score_dict["grade"] = grade

        return score_dict

    except Exception as e:
        score_dict["scalp_score"] = 10
        score_dict["warnings"].append(f"Score calculation error: {str(e)}")
        return score_dict


def _classify_scalp_grade(score: int, long: int, short: int, rsi_val: float) -> str:
    """Classify SCALP_A+ / A / B / REJECT based on score and signals.

    Grades are for PAPER TRADING only — show quality of technical setup, not authorization.
    """

    # SCALP_A+: Excellent paper setup
    if score >= 70 and (long >= 65 or short >= 65):
        return "SCALP_A+"

    # SCALP_A: Good paper setup
    if score >= 55 and (long >= 50 or short >= 50):
        return "SCALP_A"

    # SCALP_B: Worthwhile paper setup
    if score >= 40 and (long >= 35 or short >= 35):
        return "SCALP_B"

    # SCALP_REJECT: Not interesting for paper
    return "SCALP_REJECT"
