"""
Parameter Optimizer
===================
Cherche automatiquement les meilleures combinaisons de paramètres pour
les signaux swing trading en backtestant ~200 jeux de paramètres sur
tous les tickers.

Architecture clé : les indicateurs sont calculés UNE SEULE FOIS par ticker,
puis tous les jeux de paramètres sont testés sur ces séries pré-calculées.
Cela rend l'exploration très rapide (~10-30 secondes pour 200 combos × 40 tickers).
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product

from indicators import sma, rsi, macd, atr

# ── Cache résultats ──────────────────────────────────────────────────────────
import time as _time
_opt_cache: Dict[int, dict] = {}   # {period_months: {ts, data}}
OPT_CACHE_TTL = 60 * 60            # 1 heure


def _cache_get_opt(period: int) -> Optional[dict]:
    e = _opt_cache.get(period)
    if e and (_time.time() - e["ts"]) < OPT_CACHE_TTL:
        return e["data"]
    return None


def _cache_set_opt(period: int, data: dict):
    _opt_cache[period] = {"ts": _time.time(), "data": data}


# ── Pré-calcul des indicateurs ───────────────────────────────────────────────

def precompute(df_cache: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Calcule les indicateurs une seule fois pour tous les tickers.
    Convertit en arrays NumPy pour maximiser la vitesse dans la boucle de backtest.
    """
    result = {}
    for ticker, df in df_cache.items():
        try:
            close  = df["Close"].squeeze()
            high   = df["High"].squeeze()
            low    = df["Low"].squeeze()
            volume = df["Volume"].squeeze()

            s50_s      = sma(close, 50)
            s200_s     = sma(close, 200)
            rsi_s      = rsi(close, 14)
            _, _, mh_s = macd(close)

            n = len(close)
            result[ticker] = {
                "close":  close.to_numpy(dtype=float),
                "high":   high.to_numpy(dtype=float),
                "low":    low.to_numpy(dtype=float),
                "volume": volume.to_numpy(dtype=float),
                "s50":    s50_s.to_numpy(dtype=float),
                "s200":   s200_s.to_numpy(dtype=float),
                "rsi":    rsi_s.to_numpy(dtype=float),
                "mh":     mh_s.to_numpy(dtype=float),
                "n":      n,
            }
        except Exception:
            continue
    return result


# ── Backtest d'un jeu de paramètres sur un ticker ────────────────────────────

def _run_one(td: Dict, params: Dict, period_months: int) -> List[float]:
    """
    Backtest ultra-rapide sur les arrays NumPy pré-calculés.
    Retourne la liste des PnL en %.
    """
    close  = td["close"]
    high   = td["high"]
    low    = td["low"]
    volume = td["volume"]
    s50    = td["s50"]
    s200   = td["s200"]
    rsi_a  = td["rsi"]
    mh     = td["mh"]
    n      = td["n"]

    tp_pct   = params["tp_pct"]
    sl_pct   = params["sl_pct"]
    max_days = params["max_days"]

    dist_min     = params["dist_min"]
    dist_max     = params["dist_max"]
    rsi_min      = params["rsi_min"]
    rsi_max      = params["rsi_max"]
    req_uptrend  = params.get("req_uptrend", True)
    req_macd     = params.get("req_macd", True)
    req_vol      = params.get("req_vol", False)
    vol_mult     = params.get("vol_mult", 1.0)
    req_new_high = params.get("req_new_high", False)
    perf_min     = params.get("perf_3m_min", 0.0)

    trading_days   = int(252 * period_months / 12)
    backtest_start = max(200, n - trading_days)

    pnls: List[float] = []
    in_trade    = False
    entry_price = 0.0
    entry_idx   = 0

    for i in range(backtest_start, n - 1):
        s50_v  = s50[i]
        s200_v = s200[i]
        r_v    = rsi_a[i]
        mh_v   = mh[i]

        if np.isnan(s50_v) or np.isnan(s200_v) or np.isnan(r_v) or np.isnan(mh_v):
            continue
        if s50_v <= 0 or s200_v <= 0:
            continue

        p = close[i]

        if in_trade:
            tp_price   = entry_price * (1.0 + tp_pct)
            sl_price   = entry_price * (1.0 - sl_pct)
            days_held  = i - entry_idx
            h_i, l_i   = high[i], low[i]

            hit_tp  = h_i >= tp_price
            hit_sl  = l_i <= sl_price
            timeout = days_held >= max_days

            if hit_tp and hit_sl:
                ep = sl_price
            elif hit_tp:
                ep = tp_price
            elif hit_sl:
                ep = sl_price
            elif timeout:
                ep = close[i]
            else:
                continue

            pnls.append((ep / entry_price - 1.0) * 100.0)
            in_trade = False

        else:
            dist = (p - s50_v) / s50_v * 100.0

            ok = (dist_min <= dist <= dist_max) and (rsi_min <= r_v <= rsi_max)
            if not ok:
                continue
            if req_uptrend and p <= s200_v:
                continue
            if req_macd and mh_v <= 0:
                continue
            if req_vol and i >= 20:
                vol_avg = float(np.mean(volume[max(0, i - 19): i + 1]))
                if volume[i] < vol_avg * vol_mult:
                    continue
            if req_new_high and i >= 29:
                if high[i] < float(np.max(high[max(0, i - 29): i + 1])):
                    continue
            if perf_min > 0 and i >= 63:
                p3m = (p / close[i - 63] - 1.0) * 100.0
                if p3m < perf_min:
                    continue
            elif perf_min > 0:
                continue

            # Signal validé → entrée au close du lendemain
            entry_price = close[i + 1]
            entry_idx   = i + 1
            in_trade    = True

    if in_trade and n > entry_idx:
        pnls.append((close[-1] / entry_price - 1.0) * 100.0)

    return pnls


# ── Calcul du score d'un jeu de paramètres ───────────────────────────────────

def score_paramset(pnls: List[float]) -> Dict:
    if not pnls:
        return {
            "score": 0.0, "win_rate": 0.0, "expectancy": 0.0,
            "profit_factor": 0.0, "max_drawdown_pct": 0.0,
            "total_trades": 0, "total_return_pct": 0.0,
        }

    arr   = np.array(pnls)
    wins  = arr[arr > 0]
    loss  = arr[arr <= 0]

    win_rate   = len(wins) / len(arr) * 100.0
    avg_gain   = float(np.mean(wins))  if len(wins) > 0 else 0.0
    avg_loss   = float(np.mean(loss))  if len(loss) > 0 else 0.0
    expectancy = (win_rate / 100.0 * avg_gain) + ((1.0 - win_rate / 100.0) * avg_loss)

    gp = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gl = float(abs(np.sum(loss))) if len(loss) > 0 else 0.0
    pf = round(gp / gl, 2) if gl > 0 else 99.0

    cum = np.cumsum(arr)
    run_max = np.maximum.accumulate(cum)
    max_dd  = float(np.min(cum - run_max))

    # Score /100
    wr_s  = min(win_rate / 65.0,  1.0) * 30
    ex_s  = min(max(expectancy, 0) / 2.5, 1.0) * 30
    pf_s  = min(max(pf - 1.0, 0) / 2.0,  1.0) * 20
    dd_s  = max(0.0, 1.0 - abs(max_dd) / 25.0) * 10
    tr_s  = min(len(pnls) / 30.0, 1.0) * 10
    score = round(wr_s + ex_s + pf_s + dd_s + tr_s, 1)

    return {
        "score":            score,
        "win_rate":         round(win_rate, 1),
        "expectancy":       round(expectancy, 2),
        "profit_factor":    pf,
        "max_drawdown_pct": round(max_dd, 2),
        "total_trades":     len(pnls),
        "total_return_pct": round(float(np.sum(arr)), 2),
    }


# ── Grille de paramètres ─────────────────────────────────────────────────────

def build_param_grid() -> List[Dict]:
    """
    Construit ~200 jeux de paramètres couvrant les 5 familles de signaux.
    Chaque dimension est limitée à 2-4 valeurs pour rester rapide.
    """
    params: List[Dict] = []

    # ── 1. Pullback SMA50 ─────────────────────────────────────────────────
    # Prix revient sur la SMA50 depuis le dessus
    for dist in [(-6, 0.5), (-4, 1.0), (-8, 1.5), (-3, 2.0), (-10, 0.0)]:
        for r_range in [(38, 58), (35, 62), (40, 65), (30, 55)]:
            for tp, sl in [(0.05, 0.02), (0.07, 0.03), (0.04, 0.02)]:
                for max_d in [20, 30]:
                    params.append(dict(
                        family="Pullback SMA50",
                        req_uptrend=True, dist_min=dist[0], dist_max=dist[1],
                        rsi_min=r_range[0], rsi_max=r_range[1],
                        req_macd=True, req_vol=False, vol_mult=1.0,
                        req_new_high=False, perf_3m_min=0.0,
                        tp_pct=tp, sl_pct=sl, max_days=max_d,
                    ))

    # ── 2. Breakout 30 jours ──────────────────────────────────────────────
    # Nouveau plus haut 30j avec ou sans volume
    for dist in [(-1, 8), (0, 12), (-2, 5)]:
        for r_range in [(50, 78), (55, 80), (52, 75)]:
            for vol_m, req_v in [(1.0, False), (1.2, True), (1.5, True)]:
                for tp, sl in [(0.08, 0.035), (0.10, 0.04), (0.07, 0.03)]:
                    for max_d in [20, 30]:
                        params.append(dict(
                            family="Breakout 30j",
                            req_uptrend=True, dist_min=dist[0], dist_max=dist[1],
                            rsi_min=r_range[0], rsi_max=r_range[1],
                            req_macd=True, req_vol=req_v, vol_mult=vol_m,
                            req_new_high=True, perf_3m_min=0.0,
                            tp_pct=tp, sl_pct=sl, max_days=max_d,
                        ))

    # ── 3. Momentum Fort ──────────────────────────────────────────────────
    # Prix au-dessus SMA50, RSI en zone momentum, perf 3m positive
    for dist in [(0, 8), (0, 12), (-2, 6), (1, 10)]:
        for r_range in [(55, 72), (58, 78), (50, 70)]:
            for perf in [0.0, 3.0, 5.0]:
                for tp, sl in [(0.07, 0.03), (0.08, 0.03), (0.10, 0.04)]:
                    for max_d in [20, 30]:
                        params.append(dict(
                            family="Momentum Fort",
                            req_uptrend=True, dist_min=dist[0], dist_max=dist[1],
                            rsi_min=r_range[0], rsi_max=r_range[1],
                            req_macd=True, req_vol=False, vol_mult=1.0,
                            req_new_high=False, perf_3m_min=perf,
                            tp_pct=tp, sl_pct=sl, max_days=max_d,
                        ))

    # ── 4. Mean Reversion ─────────────────────────────────────────────────
    # Prix bien en dessous de SMA50, RSI survendu, rebond potentiel
    for dist in [(-15, -5), (-12, -3), (-20, -7), (-10, -4)]:
        for r_range in [(25, 48), (28, 52), (30, 55), (20, 45)]:
            for tp, sl in [(0.05, 0.02), (0.06, 0.025), (0.08, 0.035), (0.04, 0.02)]:
                for max_d in [20, 30, 45]:
                    params.append(dict(
                        family="Mean Reversion",
                        req_uptrend=True, dist_min=dist[0], dist_max=dist[1],
                        rsi_min=r_range[0], rsi_max=r_range[1],
                        req_macd=False, req_vol=False, vol_mult=1.0,
                        req_new_high=False, perf_3m_min=0.0,
                        tp_pct=tp, sl_pct=sl, max_days=max_d,
                    ))

    # ── 5. Low Volatility Swing ───────────────────────────────────────────
    # Prix très proche de SMA50, RSI neutre, faible ATR (approximé par dist étroite)
    for dist in [(-2, 2), (-3, 3), (-1.5, 1.5), (-4, 1)]:
        for r_range in [(42, 62), (40, 65), (45, 60), (38, 58)]:
            for tp, sl in [(0.04, 0.015), (0.05, 0.02), (0.06, 0.025)]:
                for max_d in [15, 20, 30]:
                    params.append(dict(
                        family="Low Vol Swing",
                        req_uptrend=True, dist_min=dist[0], dist_max=dist[1],
                        rsi_min=r_range[0], rsi_max=r_range[1],
                        req_macd=False, req_vol=False, vol_mult=1.0,
                        req_new_high=False, perf_3m_min=0.0,
                        tp_pct=tp, sl_pct=sl, max_days=max_d,
                    ))

    return params


# ── Point d'entrée principal ─────────────────────────────────────────────────

def run_optimizer(df_cache: Dict, period_months: int = 12) -> Dict:
    """
    Lance l'optimisation de paramètres.
    Retourne le top 10 + statistiques globales.
    """
    cached = _cache_get_opt(period_months)
    if cached:
        return {**cached, "from_cache": True}

    # 1) Pré-calcul des indicateurs (une fois pour tous)
    ticker_data = precompute(df_cache)
    if not ticker_data:
        return {"error": "Aucune donnée ticker disponible", "top": [], "stats": {}}

    param_sets = build_param_grid()
    tickers    = list(ticker_data.keys())

    # 2) Pour chaque jeu de paramètres : backtest sur tous les tickers en parallèle
    def eval_params(params: Dict) -> Dict:
        all_pnls: List[float] = []
        for td in ticker_data.values():
            all_pnls.extend(_run_one(td, params, period_months))
        stats = score_paramset(all_pnls)
        # Description lisible des paramètres
        desc = (
            f"Dist SMA50 [{params['dist_min']:+.0f}% → {params['dist_max']:+.1f}%] · "
            f"RSI [{params['rsi_min']}-{params['rsi_max']}] · "
            f"TP +{params['tp_pct']*100:.0f}% / SL -{params['sl_pct']*100:.1f}% · "
            f"{params['max_days']}j"
        )
        extras = []
        if params.get("req_macd"):     extras.append("MACD>0")
        if params.get("req_new_high"): extras.append("New High 30j")
        if params.get("req_vol"):      extras.append(f"Vol ×{params['vol_mult']:.1f}")
        if params.get("perf_3m_min", 0) > 0: extras.append(f"Perf3m>{params['perf_3m_min']:.0f}%")
        if extras:
            desc += " · " + " · ".join(extras)

        return {
            **params,
            **stats,
            "description": desc,
            "eligible":    stats["total_trades"] >= 20,
        }

    results: List[Dict] = []
    # Traitement en parallèle par jeux de paramètres
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(eval_params, p): p for p in param_sets}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception:
                pass

    # 3) Tri et sélection
    results.sort(key=lambda r: (r["score"], r["total_trades"]), reverse=True)

    eligible    = [r for r in results if r["eligible"]]
    top_pool    = eligible if eligible else results
    top10       = top_pool[:10]

    # Ajout du rang à chaque top entry + conversion tp/sl en %
    for i, r in enumerate(top10):
        r["rank"] = i + 1
        # Convertir tp_pct et sl_pct de décimal → pourcentage pour le frontend
        r["params"] = {
            "dist_min":    r["dist_min"],
            "dist_max":    r["dist_max"],
            "rsi_min":     r["rsi_min"],
            "rsi_max":     r["rsi_max"],
            "req_uptrend": r.get("req_uptrend", True),
            "req_macd":    r.get("req_macd", True),
            "req_vol":     r.get("req_vol", False),
            "vol_mult":    r.get("vol_mult", 1.0),
            "req_new_high":r.get("req_new_high", False),
            "perf_3m_min": r.get("perf_3m_min", 0.0),
            "tp_pct":      round(r["tp_pct"] * 100, 1),
            "sl_pct":      round(r["sl_pct"] * 100, 1),
            "max_days":    r["max_days"],
        }

    # Stats globales de l'optimisation
    all_scores  = [r["score"]      for r in results]
    all_wr      = [r["win_rate"]   for r in results if r["total_trades"] > 0]
    all_exp     = [r["expectancy"] for r in results if r["total_trades"] > 0]
    output = {
        "top": top10,
        "total_tested":    len(param_sets),
        "eligible_count":  len(eligible),
        "has_eligible":    len(eligible) > 0,
        "tickers_used":    len(tickers),
        "period_months":   period_months,
        "from_cache":      False,
        "stats": {
            "avg_score":      round(sum(all_scores)  / len(all_scores),  1) if all_scores  else 0,
            "avg_win_rate":   round(sum(all_wr)       / len(all_wr),      1) if all_wr      else 0,
            "avg_expectancy": round(sum(all_exp)      / len(all_exp),     2) if all_exp     else 0,
        },
    }
    _cache_set_opt(period_months, output)
    return output
