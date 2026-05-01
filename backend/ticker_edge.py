"""
ticker_edge.py — Per-ticker Strategy Edge Analysis v1

Pour chaque ticker :
  1. Teste les 5 stratégies du Strategy Lab sur 24 mois
  2. Split train (75 %) / test (25 %) temporal
  3. Sélectionne la meilleure stratégie selon robustesse
  4. Retourne : best_strategy, edge_status, metrics, overfit warnings

Edge statuts :
  STRONG_EDGE  — PF > 1.5, test PF > 1.2, ≥ 20 trades
  VALID_EDGE   — PF > 1.2, test PF > 1.0, ≥ 15 trades
  WEAK_EDGE    — PF > 1.1 mais un critère manque
  OVERFITTED   — train >> test (dégradation > 35 %)
  NO_EDGE      — rien ne passe
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import time as _time

from strategy_lab import LAB_STRATEGIES, backtest_ticker_lab

# ── Thresholds ────────────────────────────────────────────────────────────────

MIN_TRADES         = 15
MIN_PROFIT_FACTOR  = 1.2
MIN_TEST_PF        = 1.0
MAX_DRAWDOWN_PCT   = 40.0
MIN_EXPECTANCY     = 0.0       # expectancy positive (même faible)
OVERFIT_THRESHOLD  = 0.35      # dégradation PF > 35 % → overfitting
PERIOD_MONTHS      = 24        # fenêtre backtest (24 mois)
TRAIN_RATIO        = 0.75      # 75 % des trades pour le train

# ── Cache 24 h ────────────────────────────────────────────────────────────────

_edge_cache: Dict[str, dict] = {}
_EDGE_TTL   = 86_400          # 24 h


def _cache_key(ticker: str, period_months: int = PERIOD_MONTHS) -> str:
    """Conserve la cle historique pour l'horizon par defaut."""
    t = ticker.upper()
    if int(period_months) == PERIOD_MONTHS:
        return t
    return f"{t}:{int(period_months)}m"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _metrics(trades: List[Dict]) -> Dict:
    """Calcule win_rate, PF, expectancy, max_drawdown sur des trades fermés."""
    closed = [t for t in trades if t.get("exit_reason", "OPEN") != "OPEN"]
    if not closed:
        return {"n": 0, "win_rate": 0.0, "pf": 0.0,
                "expectancy": 0.0, "max_dd": 0.0,
                "avg_gain": 0.0, "avg_loss": 0.0}

    gains  = [t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]
    losses = [t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]

    n          = len(closed)
    wr         = len(gains) / n
    avg_gain   = float(np.mean(gains))   if gains   else 0.0
    avg_loss   = float(np.mean(losses))  if losses  else 0.0
    gp         = sum(gains)              if gains   else 0.0
    gl         = abs(sum(losses))        if losses  else 0.001
    pf         = gp / gl
    expectancy = float(np.mean([t["pnl_pct"] for t in closed]))

    # Equity curve drawdown
    equity = 100.0
    peak   = 100.0
    max_dd = 0.0
    for t in closed:
        equity *= (1 + t["pnl_pct"] / 100.0)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0
        if dd > max_dd:
            max_dd = dd

    return {
        "n":          n,
        "win_rate":   round(wr * 100, 1),
        "pf":         round(pf, 2),
        "expectancy": round(expectancy, 2),
        "max_dd":     round(max_dd, 1),
        "avg_gain":   round(avg_gain, 2),
        "avg_loss":   round(avg_loss, 2),
    }


def _edge_score_from(status: str, overall: Dict, test: Dict) -> int:
    """Score de robustesse 0-100 pondéré selon le statut."""
    if status == "STRONG_EDGE":
        base = 60
        s = int(
            20 * min(overall["pf"] / 2.0,  1.0) +
            15 * min(test["pf"]   / 1.5,  1.0) +
            10 * min(overall["n"] / 30,   1.0) +
            10 * (1 - min(overall["max_dd"] / 40, 1.0)) +
             5 * min(max(overall["expectancy"], 0) / 3.0, 1.0)
        )
        return min(100, base + s)
    elif status == "VALID_EDGE":
        base = 35
        s = int(
            15 * min(overall["pf"] / 2.0,  1.0) +
            10 * min(test["pf"]   / 1.5,  1.0) +
             8 * min(overall["n"] / 30,   1.0) +
             5 * (1 - min(overall["max_dd"] / 40, 1.0)) +
             2 * min(max(overall["expectancy"], 0) / 3.0, 1.0)
        )
        return min(60, base + s)
    elif status == "WEAK_EDGE":
        return min(35, int(
            10 * min(overall["pf"] / 2.0, 1.0) +
             8 * min(test["pf"]   / 1.5, 1.0) +
             7 * min(overall["n"] / 30,  1.0)
        ))
    return 0


def _classify_status(overall: Dict, train: Dict, test: Dict,
                      overfit: bool) -> str:
    """Détermine le statut d'edge pour une stratégie."""
    n_ok  = overall["n"] >= MIN_TRADES
    pf_ok = overall["pf"] >= MIN_PROFIT_FACTOR
    tpf   = test["pf"]  if test["n"] > 0 else 0.0
    exp   = overall["expectancy"]
    dd    = overall["max_dd"]

    if not n_ok:
        return "NO_EDGE"
    if overfit:
        return "OVERFITTED"
    if pf_ok and tpf >= MIN_TEST_PF and exp >= MIN_EXPECTANCY and dd <= MAX_DRAWDOWN_PCT:
        if overall["pf"] >= 1.5 and tpf >= 1.2 and overall["n"] >= 20:
            return "STRONG_EDGE"
        return "VALID_EDGE"
    if overall["pf"] >= 1.1 and (tpf >= 1.0 or exp >= MIN_EXPECTANCY):
        return "WEAK_EDGE"
    return "NO_EDGE"


# ── Calcul principal ──────────────────────────────────────────────────────────

def compute_ticker_edge(ticker: str, df: pd.DataFrame, period_months: int = PERIOD_MONTHS) -> Dict:
    """
    Calcule l'edge par stratégie pour un ticker.
    Résultat mis en cache 24 h.
    """
    now    = _time.time()
    period_months = int(period_months or PERIOD_MONTHS)
    cache_key = _cache_key(ticker, period_months)
    cached = _edge_cache.get(cache_key)
    if cached and (now - cached.get("ts", 0)) < _EDGE_TTL:
        return cached["data"]

    strategy_results = []

    for strat in LAB_STRATEGIES:
        try:
            all_trades = backtest_ticker_lab(
                ticker        = ticker,
                df            = df,
                strategy_def  = strat,
                period_months = period_months,
            )

            if not all_trades:
                _empty = {"n": 0, "win_rate": 0.0, "pf": 0.0,
                          "expectancy": 0.0, "max_dd": 0.0,
                          "avg_gain": 0.0, "avg_loss": 0.0}
                strategy_results.append({
                    "key":   strat["key"],
                    "name":  strat["name"],
                    "color": strat["color"],
                    "emoji": strat["emoji"],
                    "tp_pct": strat["tp_pct"],
                    "sl_pct": strat["sl_pct"],
                    "total_trades":  0,
                    "train":    _empty,
                    "test":     _empty,
                    "overall":  _empty,
                    "edge_status":    "NO_EDGE",
                    "edge_score":     0,
                    "overfit":        False,
                    "overfit_reasons": ["Aucun trade généré sur la période"],
                })
                continue

            # Séparation temporelle train / test (75 % / 25 % des trades)
            n_t    = len(all_trades)
            split  = max(1, int(n_t * TRAIN_RATIO))
            train_t = all_trades[:split]
            test_t  = all_trades[split:]

            overall_m = _metrics(all_trades)
            train_m   = _metrics(train_t)
            test_m    = _metrics(test_t)

            # Overfitting detection
            overfit          = False
            overfit_reasons: List[str] = []

            if train_m["pf"] > 0 and test_m["n"] > 0:
                deg = (train_m["pf"] - test_m["pf"]) / max(train_m["pf"], 0.001)
                if deg > OVERFIT_THRESHOLD:
                    overfit = True
                    overfit_reasons.append(
                        f"Dégradation train→test : PF {train_m['pf']:.2f} → {test_m['pf']:.2f} ({deg:.0%})"
                    )
            if train_m["pf"] > 1.5 and test_m["pf"] < 1.0:
                overfit = True
                overfit_reasons.append("Train OK / Test négatif")

            if overall_m["win_rate"] > 80 and overall_m["n"] < 20:
                overfit = True
                overfit_reasons.append(
                    f"WR {overall_m['win_rate']:.0f}% suspect sur seulement {overall_m['n']} trades"
                )
            if overall_m["pf"] > 3.5 and overall_m["max_dd"] > 30:
                overfit_reasons.append("PF très élevé + drawdown élevé")

            status     = _classify_status(overall_m, train_m, test_m, overfit)
            edge_score = _edge_score_from(status, overall_m, test_m)

            strategy_results.append({
                "key":   strat["key"],
                "name":  strat["name"],
                "color": strat["color"],
                "emoji": strat["emoji"],
                "tp_pct": strat["tp_pct"],
                "sl_pct": strat["sl_pct"],
                "total_trades":  overall_m["n"],
                "train":         train_m,
                "test":          test_m,
                "overall":       overall_m,
                "edge_status":   status,
                "edge_score":    edge_score,
                "overfit":       overfit,
                "overfit_reasons": overfit_reasons,
            })

        except Exception as exc:
            strategy_results.append({
                "key":   strat["key"],
                "name":  strat["name"],
                "color": strat.get("color", "#888"),
                "emoji": strat.get("emoji", ""),
                "tp_pct": strat.get("tp_pct", 0.05),
                "sl_pct": strat.get("sl_pct", 0.02),
                "total_trades": 0,
                "train":   {"n": 0, "win_rate": 0.0, "pf": 0.0, "expectancy": 0.0, "max_dd": 0.0},
                "test":    {"n": 0, "win_rate": 0.0, "pf": 0.0, "expectancy": 0.0, "max_dd": 0.0},
                "overall": {"n": 0, "win_rate": 0.0, "pf": 0.0, "expectancy": 0.0, "max_dd": 0.0},
                "edge_status":    "NO_EDGE",
                "edge_score":     0,
                "overfit":        False,
                "overfit_reasons": [str(exc)[:120]],
            })

    # ── Sélection meilleure stratégie ────────────────────────────────────────
    _priority = {"STRONG_EDGE": 4, "VALID_EDGE": 3, "WEAK_EDGE": 2,
                 "OVERFITTED": 1, "NO_EDGE": 0}

    ranked = sorted(
        strategy_results,
        key=lambda r: (_priority.get(r["edge_status"], 0), r["edge_score"]),
        reverse=True,
    )
    best = ranked[0] if ranked else None

    # Ticker edge status global (calqué sur la meilleure stratégie)
    ticker_edge_status = best["edge_status"] if best else "NO_EDGE"

    data: Dict = {
        "ticker":              ticker,
        "ticker_edge_status":  ticker_edge_status,
        # Meilleure stratégie
        "best_strategy":       best["key"]   if best else None,
        "best_strategy_name":  best["name"]  if best else None,
        "best_strategy_color": best["color"] if best else "#6b7280",
        "best_strategy_emoji": best["emoji"] if best else "",
        "edge_score":          best["edge_score"]  if best else 0,
        # Métriques consolidées
        "train_pf":    best["train"]["pf"]           if best else 0.0,
        "test_pf":     best["test"]["pf"]            if best else 0.0,
        "total_trades": best["total_trades"]         if best else 0,
        "win_rate":    best["overall"]["win_rate"]   if best else 0.0,
        "pf":          best["overall"]["pf"]         if best else 0.0,
        "expectancy":  best["overall"]["expectancy"] if best else 0.0,
        "max_dd":      best["overall"]["max_dd"]     if best else 0.0,
        "overfit_warning": best["overfit"]           if best else False,
        "overfit_reasons": best["overfit_reasons"]   if best else [],
        # Détail de toutes les stratégies
        "all_strategies":  strategy_results,
        "period_months":   period_months,
        "computed_at":     now,
    }

    _edge_cache[cache_key] = {"data": data, "ts": now}
    return data


def get_cached_edge(ticker: str, period_months: int = PERIOD_MONTHS) -> Optional[Dict]:
    """Retourne l'edge depuis le cache uniquement (sans recalcul)."""
    cached = _edge_cache.get(_cache_key(ticker, period_months))
    if cached:
        return cached["data"]
    return None


def invalidate_cache(ticker: Optional[str] = None) -> None:
    """Vide le cache (tout ou un ticker)."""
    if ticker:
        t = ticker.upper()
        for key in list(_edge_cache.keys()):
            if key == t or key.startswith(f"{t}:"):
                _edge_cache.pop(key, None)
    else:
        _edge_cache.clear()
