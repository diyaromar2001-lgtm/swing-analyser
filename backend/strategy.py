"""
Moteur de scoring professionnel — Minervini / O'Neil / Weinstein / Darvas

Score /100 :
  Tendance          30 pts  → SMA alignment + slope + proximity to 52W high
  Momentum          25 pts  → RSI zone idéale + MACD + perf 3m
  Risk / Reward     20 pts  → R/R dynamique (SL ATR/support, TP résistance)
  Force Relative    15 pts  → surperformance vs S&P500
  Volume / Qualité  10 pts  → volume vs moyenne 30j

Grades : A+ (≥80) | A (≥65) | B (≥50) | REJECT (<50 ou filtré)
"""

import pandas as pd
import numpy as np

from indicators import (
    sma, sma_slope, new_high_30d,
    support_level, resistance_level, high_52w, avg_volume_30d,
)


# ── Stop Loss structurel (swing low) ─────────────────────────────────────────

def find_swing_low(low: pd.Series, lookback: int = 40, n_bars: int = 3) -> float:
    """
    Retourne le dernier swing low structurel (local minimum significatif).
    Plus robuste que le simple minimum des N dernières barres.
    """
    n = min(lookback, len(low))
    sub = low.iloc[-n:]
    swing_lows = []
    for i in range(n_bars, len(sub) - n_bars):
        v = float(sub.iloc[i])
        before_ok = all(v <= float(sub.iloc[i - j]) for j in range(1, n_bars + 1))
        after_ok  = all(v <= float(sub.iloc[i + j]) for j in range(1, n_bars + 1))
        if before_ok and after_ok:
            swing_lows.append(v)
    # Dernier swing low trouvé, sinon fallback sur minimum simple
    return swing_lows[-1] if swing_lows else float(sub.min())


# ── Filtres éliminatoires (hard filters) ─────────────────────────────────────

def hard_filter(
    price: float,
    sma200: float,
    rsi_val: float,
    avg_vol: float,
    atr_val: float,
) -> tuple[bool, str]:
    """
    Retourne (True, raison) si l'actif est non tradable.
    Ces filtres éliminent sans exception — pas de grade pour ces actifs.
    """
    if price <= sma200:
        return True, "Prix < SMA200 — tendance baissière"
    if rsi_val > 80:
        return True, f"RSI suracheté ({rsi_val:.0f} > 80)"
    if rsi_val < 20:
        return True, f"RSI survendu ({rsi_val:.0f} < 20)"
    if avg_vol < 500_000:
        return True, f"Volume insuffisant ({avg_vol / 1_000:.0f}k < 500k)"
    if price > 0 and atr_val / price > 0.08:
        return True, f"Volatilité excessive (ATR {atr_val / price * 100:.1f}% > 8%)"
    return False, ""


# ── Niveaux dynamiques ────────────────────────────────────────────────────────

def compute_dynamic_levels(
    price: float,
    high: pd.Series,
    low: pd.Series,
    sma50: float,
    atr_val: float,
) -> dict:
    """
    Calcule les niveaux de trade dynamiques inspirés du swing pro :
    - Entrée    : SMA50 si prix > SMA50, sinon prix actuel
    - Stop Loss : max(support 20j, prix - 1.5×ATR), plafonné à -6%
    - TP1       : +1.5R depuis l'entrée (prise partielle)
    - TP2       : min(+3R, résistance 60j) — objectif final
    - Trailing  : TP1 - 0.5×R (activé après TP1)
    """
    # Entrée
    if sma50 > 0 and price > sma50 * 1.005:
        entry = sma50  # attendre pullback sur SMA50
    else:
        entry = price  # déjà en zone d'entrée

    # Stop Loss — combinaison swing low structurel + ATR
    swing_sl   = find_swing_low(low, lookback=40, n_bars=3)   # swing low structurel
    sup_20     = support_level(low, 20)                         # support simple 20j
    structural = max(swing_sl, sup_20)                          # le plus récent / haut des deux
    sl_atr     = price - 1.5 * atr_val                         # ATR-based
    stop_raw   = max(structural, sl_atr)                        # prendre le plus conservateur
    stop_loss  = max(stop_raw, price * 0.94)                    # jamais plus de 6% de risque
    sl_type    = "Structure" if structural > sl_atr else "ATR"

    # Résistance
    resist = resistance_level(high, 60)

    # Risk depuis l'entrée
    risk = max(entry - stop_loss, entry * 0.005)   # min 0.5%

    # Take Profits
    tp1      = round(entry + 1.5 * risk, 2)
    tp2_3r   = entry + 3.0 * risk
    tp2      = round(min(tp2_3r, resist) if resist > tp1 else tp2_3r, 2)
    trailing = round(tp1 - 0.5 * risk, 2)

    rr_ratio       = round((tp2 - entry) / risk, 2) if risk > 0 else 0
    dist_entry_pct = round((price - entry) / entry * 100, 2) if entry > 0 else 0
    risk_now_pct   = round((price - stop_loss) / price * 100, 2) if price > 0 else 0

    return {
        "entry":          round(entry, 2),
        "stop_loss":      round(stop_loss, 2),
        "tp1":            tp1,
        "tp2":            tp2,
        "take_profit":    tp2,
        "trailing_stop":  trailing,
        "sl_type":        sl_type,
        "resistance":     round(resist, 2),
        "rr_ratio":       rr_ratio,
        "dist_entry_pct": dist_entry_pct,
        "risk_now_pct":   risk_now_pct,
    }


# ── Scoring professionnel ─────────────────────────────────────────────────────

def compute_professional_score(
    price: float,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
    sma50: float,
    sma200: float,
    rsi_val: float,
    macd_hist: float,
    perf_3m: float,
    perf_6m: float,
    entry: float,
    stop_loss: float,
    resistance: float,
    sp500_perf_3m: float,
    sp500_perf_6m: float,
) -> tuple[int, dict, dict]:
    """
    Retourne (score/100, breakdown, details_bool).
    """

    # ── TENDANCE (30 pts) ─────────────────────────────────────────────────────
    trend_pts = 0
    b_above_sma200  = price > sma200
    b_sma50_gt_200  = sma50 > sma200 if sma50 > 0 and sma200 > 0 else False
    b_slope_pos     = sma_slope(close, 50, lookback=10)
    h52             = high_52w(high)
    b_near_52w      = price >= h52 * 0.85   # dans les 15% du plus haut annuel

    if b_above_sma200: trend_pts += 10
    if b_sma50_gt_200: trend_pts += 10
    if b_slope_pos:    trend_pts += 5
    if b_near_52w:     trend_pts += 5

    # ── MOMENTUM (25 pts) ─────────────────────────────────────────────────────
    mom_pts = 0
    b_rsi_ideal = 50 <= rsi_val <= 70
    b_rsi_ok    = (45 <= rsi_val < 50) or (70 < rsi_val <= 75)
    b_macd_pos  = macd_hist > 0
    b_perf3m    = perf_3m > 0

    if b_rsi_ideal: mom_pts += 15
    elif b_rsi_ok:  mom_pts += 7
    if b_macd_pos:  mom_pts += 5
    if b_perf3m:    mom_pts += 5

    # ── RISK / REWARD (20 pts) ───────────────────────────────────────────────
    rr_pts = 0
    risk   = max(entry - stop_loss, 0.01)
    reward = max(resistance - entry, 0)
    rr     = reward / risk if risk > 0 else 0

    if rr >= 3.0:   rr_pts = 20
    elif rr >= 2.5: rr_pts = 17
    elif rr >= 2.0: rr_pts = 14
    elif rr >= 1.5: rr_pts = 10
    elif rr >= 1.0: rr_pts = 5

    # ── FORCE RELATIVE (15 pts) ──────────────────────────────────────────────
    rs_pts = 0
    out_3m = perf_3m > sp500_perf_3m
    out_6m = perf_6m > sp500_perf_6m
    if out_3m and out_6m: rs_pts = 15
    elif out_3m or out_6m: rs_pts = 7

    # ── VOLUME / QUALITÉ (10 pts) ─────────────────────────────────────────────
    vol_pts  = 0
    avg_vol  = avg_volume_30d(volume)
    curr_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0
    b_vol_strong = curr_vol > avg_vol * 1.3
    b_vol_above  = curr_vol > avg_vol

    if b_vol_strong:     vol_pts = 10
    elif b_vol_above:    vol_pts = 5

    total = min(100, trend_pts + mom_pts + rr_pts + rs_pts + vol_pts)

    breakdown = {
        "trend":             trend_pts,
        "momentum":          mom_pts,
        "risk_reward":       rr_pts,
        "relative_strength": rs_pts,
        "volume_quality":    vol_pts,
    }

    details = {
        "prix_above_sma200":    b_above_sma200,
        "sma50_above_sma200":   b_sma50_gt_200,
        "sma50_slope_positive": b_slope_pos,
        "near_52w_high":        b_near_52w,
        "rsi_ideal_zone":       b_rsi_ideal,
        "macd_positif":         b_macd_pos,
        "perf_3m_positive":     b_perf3m,
        "outperforms_sp500":    out_3m and out_6m,
        "volume_eleve":         b_vol_strong,
        "rr_suffisant":         rr >= 1.5,
    }

    return total, breakdown, details


# ── Classification du setup ───────────────────────────────────────────────────

def classify_setup(
    score: int,
    dist_entry_pct: float,
    rr_ratio: float,
    rsi_val: float,
) -> tuple[str, str]:
    """
    A+ → entrée immédiate possible (conditions parfaites)
    A  → bon setup, attendre légère confirmation
    B  → setup en formation, watchlist
    REJECT → éviter
    """
    if score >= 80 and dist_entry_pct <= 3.0 and rr_ratio >= 2.5 and 50 <= rsi_val <= 70:
        return "A+", "Setup premium — alignement parfait, entrée immédiate possible"
    if score >= 65 and dist_entry_pct <= 8.0 and rr_ratio >= 1.5:
        return "A", "Bon setup — légère confirmation ou repli conseillé"
    if score >= 50:
        return "B", f"Setup en formation — surveiller (score {score}/100)"
    return "REJECT", f"Score insuffisant ({score}/100) — conditions défavorables"


# ── Score de confiance ────────────────────────────────────────────────────────

def compute_confidence(score: int, rr_ratio: float, rsi_val: float) -> int:
    """Score de confiance 0–100 (combinaison de score, R/R et timing RSI)."""
    conf = min(40, score // 2)

    if rr_ratio >= 3.0:   conf += 30
    elif rr_ratio >= 2.0: conf += 22
    elif rr_ratio >= 1.5: conf += 14
    elif rr_ratio >= 1.0: conf += 7

    if 55 <= rsi_val <= 65:   conf += 20
    elif 50 <= rsi_val <= 70: conf += 12
    elif 45 <= rsi_val <= 75: conf += 5

    # Bonus alignement parfait
    if score >= 80 and rr_ratio >= 2.0 and 50 <= rsi_val <= 70:
        conf += 10

    return min(100, conf)


# ── Signal type ───────────────────────────────────────────────────────────────

def detect_signal_type(
    price: float,
    sma50: float,
    rsi_val: float,
    macd_hist: float,
    high: pd.Series,
) -> str:
    if sma50 <= 0:
        return "Neutral"
    dist = (price - sma50) / sma50 * 100
    is_new_high = new_high_30d(high)

    if is_new_high and rsi_val > 55 and macd_hist > 0:
        return "Breakout"
    if -4 <= dist <= 3 and rsi_val < 68:
        return "Pullback"
    if rsi_val > 55 and macd_hist > 0 and 0 <= dist <= 12:
        return "Momentum"
    return "Neutral"


# ── Helpers de mapping ────────────────────────────────────────────────────────

def grade_to_category(grade: str) -> str:
    """Mapping grade → category (rétrocompat backtest / Strategy Lab)."""
    return {
        "A+":     "BUY NOW",
        "A":      "WAIT / SMALL POSITION",
        "B":      "WATCHLIST",
        "REJECT": "AVOID",
    }.get(grade, "AVOID")


def grade_to_position(grade: str) -> str:
    return {
        "A+":     "Complète (100%)",
        "A":      "Partielle (50–75%)",
        "B":      "Surveiller",
        "REJECT": "Ignorer",
    }.get(grade, "—")


# ── Rétrocompatibilité (backtest) ─────────────────────────────────────────────

def classify_standard(
    score, dist_entry_pct, risk_now_pct, rsi_val,
    macd_hist, perf_3m, perf_6m, price_above_sma200,
) -> tuple[str, str]:
    grade, _ = classify_setup(score, dist_entry_pct, 2.0, rsi_val)
    return grade_to_category(grade), grade_to_position(grade)


def classify_conservative(
    score, dist_entry_pct, risk_now_pct, rsi_val,
    macd_hist, perf_3m, perf_6m, price_above_sma200,
) -> tuple[str, str]:
    if not price_above_sma200:
        return "AVOID", "Ignorer"
    grade, _ = classify_setup(score, dist_entry_pct, 2.0, rsi_val)
    return grade_to_category(grade), grade_to_position(grade)


def detect_buy_signal_conservative(
    price, sma50, sma200, rsi_val, macd_hist, perf_3m, perf_6m,
) -> bool:
    if sma50 <= 0 or sma200 <= 0:
        return False
    dist = (price - sma50) / sma50 * 100
    return (
        price > sma200
        and -1.0 <= dist <= 2.5
        and 50 <= rsi_val <= 62
        and macd_hist > 0
        and perf_3m > 0
        and perf_6m > 0
    )


# ── Quality Score (timing) ────────────────────────────────────────────────────

def compute_quality_score(
    dist_entry_pct: float,
    rsi_val: float,
    close: pd.Series,
    atr_val: float,
    price: float,
) -> int:
    """
    Score de qualité du timing (0–100) — DISTINCT du score global.

    Répond à : "Est-ce le BON MOMENT pour entrer ?"
    - Timing distance (40 pts) : plus proche de l'entrée = mieux
    - RSI timing     (30 pts) : zone 55-65 = optimal
    - SMA50 slope    (20 pts) : accélération de la tendance
    - Volatilité     (10 pts) : ATR maîtrisé
    """
    pts = 0

    # ── Distance à l'entrée (40 pts) ─────────────────────────────────────────
    d = abs(dist_entry_pct)
    if d <= 1.0:      pts += 40
    elif d <= 2.0:    pts += 33
    elif d <= 3.5:    pts += 25
    elif d <= 5.0:    pts += 15
    elif d <= 8.0:    pts += 7
    # au-delà de 8% : 0

    # ── Timing RSI (30 pts) ───────────────────────────────────────────────────
    if 55 <= rsi_val <= 65:    pts += 30   # sweet spot
    elif 50 <= rsi_val <= 70:  pts += 20
    elif 45 <= rsi_val <= 75:  pts += 10

    # ── Accélération SMA50 (20 pts) ───────────────────────────────────────────
    # Comparer pente sur 5j vs 20j
    slope_ok = sma_slope(close, 50, lookback=10)
    if slope_ok:
        pts += 12
        # Bonus si accélération (pente courte > pente longue)
        if len(close) >= 25:
            s50 = sma(close, 50)
            slope_5d  = float(s50.iloc[-1]) - float(s50.iloc[-6])  if len(s50) >= 6  else 0
            slope_20d = (float(s50.iloc[-1]) - float(s50.iloc[-21])) / 4 if len(s50) >= 21 else 0
            if slope_5d > slope_20d > 0:
                pts += 8   # accélération → bonus

    # ── Volatilité (10 pts) ───────────────────────────────────────────────────
    atr_pct = atr_val / price * 100 if price > 0 else 5
    if atr_pct < 2.0:    pts += 10
    elif atr_pct < 3.5:  pts += 7
    elif atr_pct < 5.0:  pts += 4

    return min(100, pts)



# ── Final Decision (technique + filtres fondamentaux) ─────────────────────────

def compute_final_decision(
    setup_grade:   str,    # "A+" | "A" | "B" | "REJECT"
    setup_status:  str,    # "READY" | "WAIT" | "INVALID"
    risk_status:   str,    # "OK" | "CAUTION" | "BLOCKED"
    rr_ratio:      float,
    regime:        str,    # "BULL" | "RANGE" | "BEAR" | "UNKNOWN"
    vix_val:       float,
) -> str:
    """
    Décision finale combinant signal technique et filtres fondamentaux.

    BUY  : Grade A/A+ + setup READY + risques OK/CAUTION + R/R ≥ 1.5
    WAIT : Setup valide mais conditions non réunies (CAUTION ou pas READY)
    SKIP : BLOCKED par filtres, ou grade REJECT, ou R/R insuffisant
    """
    # SKIP si bloqué ou qualité insuffisante
    if risk_status == "BLOCKED":
        return "SKIP"
    if setup_grade == "REJECT":
        return "SKIP"
    if setup_status == "INVALID":
        return "SKIP"
    if rr_ratio < 1.5:
        return "SKIP"

    # BUY si tout est aligné
    if (
        setup_grade in ("A+", "A")
        and setup_status == "READY"
        and risk_status == "OK"
        and rr_ratio >= 1.5
        and regime in ("BULL", "RANGE")
    ):
        return "BUY"

    # WAIT dans tous les autres cas valides
    return "WAIT"


def detect_buy_signal_standard(
    price, sma50, sma200, rsi_val, macd_hist, perf_3m=0, perf_6m=0,
) -> bool:
    if sma50 <= 0 or sma200 <= 0:
        return False
    dist = (price - sma50) / sma50 * 100
    return (
        price > sma200
        and 0 <= dist <= 3.0
        and 45 <= rsi_val <= 68
        and macd_hist > 0
    )
