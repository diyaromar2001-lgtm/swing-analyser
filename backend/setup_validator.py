"""
Setup Validator — Validation historique des setups avec les EXACTES mêmes règles que le screener.

Pour chaque ticker, rejoue le screener jour par jour sur 24 mois
et calcule le win rate / expectancy réels des grades A+, A, B.

Résultat mis en cache 24h par ticker+grade.
"""

import time
import numpy as np
import pandas as pd

from indicators import sma, rsi, macd, atr, perf_pct, avg_volume_30d
from strategy import hard_filter, classify_setup


# ── Cache (TTL = 24h) ─────────────────────────────────────────────────────────
_cache: dict = {}
_CACHE_TTL = 86_400   # 24h


def _cache_key(ticker: str, grade: str, period: int) -> str:
    return f"{ticker}:{grade}:{period}"


# ── Swing low detection ────────────────────────────────────────────────────────

def find_swing_low(low: pd.Series, lookback: int = 40, n_bars: int = 3) -> float:
    """
    Dernier swing low structurel significatif.
    Un swing low = barre dont le low est inférieur aux n_bars barres adjacentes.
    """
    n = min(lookback, len(low))
    sub = low.iloc[-n:]
    swing_lows = []
    for i in range(n_bars, len(sub) - n_bars):
        v = sub.iloc[i]
        before_ok = all(v <= sub.iloc[i - j] for j in range(1, n_bars + 1))
        after_ok  = all(v <= sub.iloc[i + j] for j in range(1, n_bars + 1))
        if before_ok and after_ok:
            swing_lows.append(float(v))
    return swing_lows[-1] if swing_lows else float(sub.min())


# ── Moteur de validation historique ──────────────────────────────────────────

def validate_setup(
    ticker: str,
    df: pd.DataFrame,
    grade_filter: str,
    sp500_perf_3m: float = 5.0,
    sp500_perf_6m: float = 8.0,
    period_months: int = 24,
) -> dict:
    """
    Rejoue le screener avec les EXACTES mêmes règles sur [period_months] mois de data.
    Retourne les statistiques historiques pour le grade [grade_filter].
    """
    key = _cache_key(ticker, grade_filter, period_months)
    cached = _cache.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    result = _compute_validate(ticker, df, grade_filter, sp500_perf_3m, sp500_perf_6m, period_months)
    _cache[key] = {"ts": time.time(), "data": result}
    return result


def _compute_validate(
    ticker: str,
    df: pd.DataFrame,
    grade_filter: str,
    sp500_perf_3m: float,
    sp500_perf_6m: float,
    period_months: int,
) -> dict:
    try:
        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        n = len(close)
        if n < 260:
            return {"n_trades": 0, "sample_ok": False, "error": "Données insuffisantes (<260 barres)"}

        # ── Pré-calcul des indicateurs sur la série complète ──────────────────
        sma50_s       = sma(close, 50)
        sma200_s      = sma(close, 200)
        rsi_s         = rsi(close, 14)
        _, _, macd_s  = macd(close)
        atr_s         = atr(high, low, close, 14)

        # Période de recherche
        start_i = max(215, n - period_months * 21)

        trades = []

        # Pas de 5 jours pour la vitesse
        for i in range(start_i, n - 1, 5):
            price    = float(close.iloc[i])
            sma50_v  = float(sma50_s.iloc[i])
            sma200_v = float(sma200_s.iloc[i])
            rsi_v    = float(rsi_s.iloc[i])
            macd_v   = float(macd_s.iloc[i])
            atr_v    = float(atr_s.iloc[i])

            if any(np.isnan(x) for x in [sma50_v, sma200_v, rsi_v, macd_v, atr_v]):
                continue

            # Volume moyen 30j
            vol_slice = volume.iloc[max(0, i - 30):i]
            avg_vol   = float(vol_slice.mean()) if len(vol_slice) > 0 else 600_000

            # Filtres éliminatoires — identiques au screener
            filtered, _ = hard_filter(price, sma200_v, rsi_v, avg_vol, atr_v)
            if filtered:
                continue

            # Perf 3m / 6m
            p3m = perf_pct(close.iloc[:i + 1], 63)
            p6m = perf_pct(close.iloc[:i + 1], 126)

            # Support / résistance sur fenêtres glissantes
            sup_20  = float(low.iloc[max(0, i - 20):i + 1].min())
            resist  = float(high.iloc[max(0, i - 60):i + 1].max())

            # Entrée SMA50
            entry = sma50_v if (sma50_v > 0 and price > sma50_v * 1.005) else price

            # Stop Loss (ATR + support)
            sl_atr    = price - 1.5 * atr_v
            stop_raw  = max(sup_20, sl_atr)
            stop_loss = max(stop_raw, price * 0.94)

            # TP
            risk = max(entry - stop_loss, entry * 0.005)
            tp1  = entry + 1.5 * risk
            tp2  = min(entry + 3.0 * risk, resist) if resist > (entry + 1.5 * risk) else entry + 3.0 * risk
            rr   = (tp2 - entry) / risk if risk > 0 else 0
            dist = (price - entry) / entry * 100 if entry > 0 else 0

            # Score — MÊME logique que compute_professional_score
            b_above_sma200 = price > sma200_v
            b_sma50_gt_200 = sma50_v > sma200_v
            sma50_i10      = float(sma50_s.iloc[i - 10]) if i >= 10 else sma50_v
            b_slope_pos    = (not np.isnan(sma50_i10)) and (sma50_v > sma50_i10)
            h52_val        = float(high.iloc[max(0, i - 252):i + 1].max())
            b_near_52w     = price >= h52_val * 0.85

            trend_pts = (10 if b_above_sma200 else 0) + (10 if b_sma50_gt_200 else 0) \
                      + (5 if b_slope_pos else 0)   + (5 if b_near_52w else 0)

            b_rsi_ideal = 50 <= rsi_v <= 70
            b_rsi_ok    = (45 <= rsi_v < 50) or (70 < rsi_v <= 75)
            mom_pts = (15 if b_rsi_ideal else 7 if b_rsi_ok else 0) \
                    + (5 if macd_v > 0 else 0) + (5 if p3m > 0 else 0)

            rr_pts = 20 if rr >= 3.0 else 17 if rr >= 2.5 else 14 if rr >= 2.0 \
                else 10 if rr >= 1.5 else 5 if rr >= 1.0 else 0

            rs_pts = 15 if (p3m > sp500_perf_3m and p6m > sp500_perf_6m) \
                else 7 if (p3m > sp500_perf_3m or p6m > sp500_perf_6m) else 0

            curr_vol = float(volume.iloc[i]) if i < len(volume) else 0
            vol_pts  = 10 if curr_vol > avg_vol * 1.3 else 5 if curr_vol > avg_vol else 0

            score = min(100, trend_pts + mom_pts + rr_pts + rs_pts + vol_pts)

            # Classification — IDENTIQUE au screener
            grade, _ = classify_setup(score, dist, rr, rsi_v)
            if grade != grade_filter:
                continue

            # ── Simulation de trade ────────────────────────────────────────
            future_n = min(30, n - i - 1)
            if future_n <= 0:
                continue

            fh_s = high.iloc[i + 1: i + 1 + future_n]
            fl_s = low.iloc[i + 1: i + 1 + future_n]
            fc_s = close.iloc[i + 1: i + 1 + future_n]

            # Attendre que le prix revienne à l'entrée (si nécessaire)
            entry_price = entry
            entry_hit   = entry >= price * 0.999
            offset      = 0

            if not entry_hit:
                for j in range(len(fl_s)):
                    if float(fl_s.iloc[j]) <= entry * 1.005:
                        entry_hit = True
                        offset = j
                        break

            if not entry_hit:
                continue   # Jamais entré

            outcome = "TIMEOUT"
            pnl_pct  = 0.0
            days_held = future_n - offset

            for j in range(offset, len(fh_s)):
                fh = float(fh_s.iloc[j])
                fl = float(fl_s.iloc[j])

                if fh >= tp2:
                    outcome   = "TP2"
                    pnl_pct   = round((tp2 - entry_price) / entry_price * 100, 2)
                    days_held = j - offset + 1
                    break
                elif fh >= tp1:
                    outcome   = "TP1"
                    pnl_pct   = round((tp1 - entry_price) / entry_price * 100, 2)
                    days_held = j - offset + 1
                    break
                elif fl <= stop_loss:
                    outcome   = "SL"
                    pnl_pct   = round((stop_loss - entry_price) / entry_price * 100, 2)
                    days_held = j - offset + 1
                    break
            else:
                if len(fc_s) > offset:
                    pnl_pct = round((float(fc_s.iloc[-1]) - entry_price) / entry_price * 100, 2)

            trades.append({
                "date":      str(close.index[i])[:10],
                "outcome":   outcome,
                "pnl_pct":   pnl_pct,
                "days_held": days_held,
                "score":     score,
            })

        # ── Calcul des statistiques ───────────────────────────────────────────
        n_trades = len(trades)
        if n_trades == 0:
            return {
                "n_trades": 0,
                "sample_ok": False,
                "grade": grade_filter,
                "warning": f"Aucune occurrence '{grade_filter}' sur {period_months} mois",
            }

        wins   = [t for t in trades if t["outcome"] in ("TP1", "TP2")]
        losses = [t for t in trades if t["outcome"] == "SL"]

        win_rate   = round(len(wins) / n_trades * 100, 1)
        gains_pct  = [t["pnl_pct"] for t in wins]
        loss_pct   = [abs(t["pnl_pct"]) for t in losses]
        avg_gain   = round(float(np.mean(gains_pct)), 2) if gains_pct else 0.0
        avg_loss   = round(float(np.mean(loss_pct)), 2)  if loss_pct  else 0.0
        expectancy = round(win_rate / 100 * avg_gain - (1 - win_rate / 100) * avg_loss, 2)

        sum_gains  = sum(gains_pct)
        sum_losses = sum(loss_pct)
        profit_factor = round(sum_gains / sum_losses, 2) if sum_losses > 0 else 99.0

        all_pnls     = [t["pnl_pct"] for t in trades]
        cum          = np.cumsum(all_pnls)
        running_max  = np.maximum.accumulate(cum)
        max_dd       = round(float(np.min(cum - running_max)), 2)

        avg_days = round(float(np.mean([t["days_held"] for t in trades])), 1)

        # 3 derniers trades pour affichage
        recent = trades[-3:]

        return {
            "n_trades":          n_trades,
            "win_rate":          win_rate,
            "expectancy":        expectancy,
            "profit_factor":     profit_factor,
            "max_drawdown_pct":  max_dd,
            "avg_duration_days": avg_days,
            "avg_gain_pct":      avg_gain,
            "avg_loss_pct":      avg_loss,
            "sample_ok":         n_trades >= 20,
            "grade":             grade_filter,
            "period_months":     period_months,
            "recent_trades":     recent,
        }

    except Exception as e:
        return {"n_trades": 0, "sample_ok": False, "error": str(e)}
