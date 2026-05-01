"""
Strategy Lab v2 — moteur de backtesting avancé.

Améliorations v2 :
  • 5 familles de stratégies avec EMA20, volume confirmé, pente SMA50
  • Walk-forward validation (75 % train / 25 % test)
  • Détection d'overfitting (divergence train/test, concentration ticker)
  • Critères TRADABLE stricts (≥ 50 trades, PF > 1.3, DD < 25 %, Sharpe > 0.5)
  • Classement : Best Robust / Best WR / Best PF / Best Low DD
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from indicators import sma, ema, rsi, macd, atr
from portfolio_backtest import run_portfolio_backtest, INITIAL_CAPITAL, _empty_result


# ─── Signal functions ──────────────────────────────────────────────────────────
#
# Signature commune :
#   fn(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i)
# Toutes les séries sont des pd.Series.


def _sig_pullback_trend(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    A. Pullback Trend — retour vers EMA20 en uptrend qualifié.

    Conditions :
      • prix > SMA200, SMA50 > SMA200 (double uptrend)
      • SMA50 en pente positive (hausse sur 10 barres)
      • prix revient sur EMA20 (dist -4 % → +1 %)
      • RSI 42-60 (momentum sain, non suracheté)
      • MACD histogram > -0.3 (pas de retournement fort)
      • volume stable ou décroissant (pullback ordonné)
    """
    if i < 10:
        return False
    p    = float(close.iloc[i])
    s50v = float(s50.iloc[i])
    s200v= float(s200.iloc[i])
    e20v = float(e20_s.iloc[i])
    rv   = float(rsi_s.iloc[i])
    mhv  = float(mh_s.iloc[i])

    if s50v <= 0 or s200v <= 0 or e20v <= 0:
        return False

    # Pente SMA50 (hausse sur 10 barres)
    s50_prev = float(s50.iloc[i - 10])
    sma50_rising = s50v > s50_prev if not np.isnan(s50_prev) else False

    dist_e20 = (p - e20v) / e20v * 100.0

    # Volume : moyenne 10j vs 5j (pullback calme)
    vol_avg10 = float(volume.iloc[max(0, i - 9): i + 1].mean())
    vol_avg5  = float(volume.iloc[max(0, i - 4): i + 1].mean())
    calm_vol  = (vol_avg5 <= vol_avg10 * 1.15) if vol_avg10 > 0 else True

    return (
        p > s200v
        and s50v > s200v
        and sma50_rising
        and -4.0 <= dist_e20 <= 1.0
        and 42 <= rv <= 60
        and mhv > -0.3
        and calm_vol
    )


def _sig_pullback_confirmed(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    Pullback Confirmed - pullback vers EMA20/SMA50 avec rebond confirme.

    Conditions :
      - prix > SMA200, SMA50 > SMA200
      - SMA50 en pente positive
      - pullback recent vers EMA20 ou SMA50
      - RSI 42-62
      - MACD histogram pas fortement negatif
      - rebond confirme par close > close veille ou close > high veille

    Le volume n'est pas obligatoire ici : il reste un facteur qualitatif dans
    l'analyse globale, mais ne bloque pas le signal de base.
    """
    if i < 10:
        return False

    p = float(close.iloc[i])
    prev_close = float(close.iloc[i - 1])
    prev_high = float(high.iloc[i - 1])
    s50v = float(s50.iloc[i])
    s200v = float(s200.iloc[i])
    e20v = float(e20_s.iloc[i])
    rv = float(rsi_s.iloc[i])
    mhv = float(mh_s.iloc[i])

    if any(np.isnan(x) for x in [p, prev_close, prev_high, s50v, s200v, e20v, rv, mhv]):
        return False
    if s50v <= 0 or s200v <= 0 or e20v <= 0:
        return False

    s50_prev = float(s50.iloc[i - 10])
    sma50_rising = s50v > s50_prev if not np.isnan(s50_prev) else False

    dist_e20 = (p - e20v) / e20v * 100.0
    dist_s50 = (p - s50v) / s50v * 100.0

    # Pullback observe sur les 5 dernieres bougies, vers EMA20 ou SMA50.
    pullback_recent = False
    for j in range(max(0, i - 4), i + 1):
        cj = float(close.iloc[j])
        e20j = float(e20_s.iloc[j])
        s50j = float(s50.iloc[j])
        if any(np.isnan(x) for x in [cj, e20j, s50j]) or e20j <= 0 or s50j <= 0:
            continue
        d20 = (cj - e20j) / e20j * 100.0
        d50 = (cj - s50j) / s50j * 100.0
        if -5.0 <= d20 <= 2.0 or -6.0 <= d50 <= 3.0:
            pullback_recent = True
            break

    rebound_confirmed = p > prev_close or p > prev_high

    return (
        p > s200v
        and s50v > s200v
        and sma50_rising
        and pullback_recent
        and (-4.0 <= dist_e20 <= 3.0 or -6.0 <= dist_s50 <= 3.0)
        and 42 <= rv <= 62
        and mhv > -0.5
        and rebound_confirmed
    )


def _sig_breakout_quality(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    B. Breakout Quality — cassure de plus haut 20 jours avec confirmation volume.

    Conditions :
      • SMA50 > SMA200 (tendance haussière)
      • nouveau plus haut 20 jours sur High
      • volume > 1.4× moyenne 20 jours
      • RSI 52-72 (force mais pas suracheté)
      • prix dans les 5 % au-dessus de l'EMA20 (pas trop extended)
      • MACD positif
    """
    if i < 20:
        return False
    p    = float(close.iloc[i])
    h    = float(high.iloc[i])
    s50v = float(s50.iloc[i])
    s200v= float(s200.iloc[i])
    e20v = float(e20_s.iloc[i])
    rv   = float(rsi_s.iloc[i])
    mhv  = float(mh_s.iloc[i])

    if s50v <= 0 or s200v <= 0 or e20v <= 0:
        return False

    high_20  = float(high.iloc[i - 19: i + 1].max())
    vol_avg  = float(volume.iloc[i - 19: i + 1].mean())
    vol_cur  = float(volume.iloc[i])
    dist_e20 = (p - e20v) / e20v * 100.0

    return (
        s50v > s200v
        and h >= high_20
        and vol_cur >= vol_avg * 1.4
        and 52 <= rv <= 72
        and 0.0 <= dist_e20 <= 5.0
        and mhv > 0
    )


def _sig_relative_strength(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    C. Relative Strength Leader — action en tête de marché.

    Conditions :
      • prix > SMA50 > SMA200
      • performance 3 mois > 8 % (proxy force relative)
      • performance 1 mois > 2 %
      • RSI 50-68 (momentum fort mais contrôlé)
      • pullback contrôlé vers EMA20 ou SMA50 (-5 % → +3 % vs EMA20)
      • volume > 0.8× moyenne (institutionnels toujours présents)
    """
    if i < 63:
        return False
    p    = float(close.iloc[i])
    s50v = float(s50.iloc[i])
    s200v= float(s200.iloc[i])
    e20v = float(e20_s.iloc[i])
    rv   = float(rsi_s.iloc[i])
    mhv  = float(mh_s.iloc[i])

    if s50v <= 0 or s200v <= 0 or e20v <= 0:
        return False

    p3m = (p / float(close.iloc[i - 63]) - 1.0) * 100.0
    p1m = (p / float(close.iloc[i - 21]) - 1.0) * 100.0 if i >= 21 else 0.0
    dist_e20 = (p - e20v) / e20v * 100.0

    vol_avg  = float(volume.iloc[max(0, i - 19): i + 1].mean())
    vol_cur  = float(volume.iloc[i])
    vol_ok   = (vol_cur >= vol_avg * 0.8) if vol_avg > 0 else True

    return (
        p > s50v > s200v
        and p3m >= 8.0
        and p1m >= 2.0
        and 50 <= rv <= 68
        and -5.0 <= dist_e20 <= 3.0
        and vol_ok
    )


def _sig_low_vol_compounder(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    D. Low Volatility Compounder — tendance régulière, faible ATR.

    Conditions :
      • prix > SMA200
      • ATR/prix < 2.5 % (faible volatilité)
      • prix dans ±2.5 % de la SMA50
      • RSI 45-58 (zone neutre stable)
      • performance 3 mois positive
      • MACD positif ou légèrement négatif (> -0.2)
    """
    if i < 20:
        return False
    p    = float(close.iloc[i])
    s50v = float(s50.iloc[i])
    s200v= float(s200.iloc[i])
    rv   = float(rsi_s.iloc[i])
    mhv  = float(mh_s.iloc[i])
    atr_v= float(atr_s.iloc[i])

    if s50v <= 0 or s200v <= 0 or p <= 0:
        return False

    dist_s50  = (p - s50v) / s50v * 100.0
    atr_ratio = atr_v / p * 100.0

    # ATR stable (faible std/mean sur 20 barres)
    atr_vals = atr_s.iloc[max(0, i - 19): i + 1]
    atr_mean = float(atr_vals.mean())
    atr_std  = float(atr_vals.std()) if len(atr_vals) > 1 else 0.0
    atr_stable = (atr_std / atr_mean < 0.20) if atr_mean > 0 else False

    p3m = (p / float(close.iloc[i - 63]) - 1.0) * 100.0 if i >= 63 else 0.0

    return (
        p > s200v
        and atr_ratio < 2.5
        and atr_stable
        and -2.5 <= dist_s50 <= 2.5
        and 45 <= rv <= 58
        and mhv > -0.2
        and p3m > 0.0
    )


def _sig_mean_reversion_uptrend(close, high, low, volume, s50, s200, rsi_s, mh_s, atr_s, e20_s, i):
    """
    E. Mean Reversion in Uptrend — pullback vers support en marché haussier.

    Conditions :
      • prix > SMA200 (uptrend fondamental intact)
      • SMA50 > SMA200
      • prix a tiré vers EMA20 (dist -8 % → -1 %)
      • RSI 35-52 (oversold temporaire)
      • MACD histogram > -1.5 (pas de retournement majeur)
      • volume décroissant sur le pullback (vente épuisée)
    """
    if i < 10:
        return False
    p    = float(close.iloc[i])
    s50v = float(s50.iloc[i])
    s200v= float(s200.iloc[i])
    e20v = float(e20_s.iloc[i])
    rv   = float(rsi_s.iloc[i])
    mhv  = float(mh_s.iloc[i])

    if s50v <= 0 or s200v <= 0 or e20v <= 0:
        return False

    dist_e20 = (p - e20v) / e20v * 100.0

    # Volume décroissant (épuisement des vendeurs)
    vol_prev5 = float(volume.iloc[max(0, i - 7): max(0, i - 2) + 1].mean())
    vol_cur3  = float(volume.iloc[max(0, i - 2): i + 1].mean())
    vol_declining = (vol_cur3 <= vol_prev5 * 1.1) if vol_prev5 > 0 else True

    return (
        p > s200v
        and s50v > s200v
        and -8.0 <= dist_e20 <= -1.0
        and 35 <= rv <= 52
        and mhv > -1.5
        and vol_declining
    )


# ─── Registre des stratégies ───────────────────────────────────────────────────

LAB_STRATEGIES: List[Dict] = [
    {
        "key":         "pullback_trend",
        "name":        "Pullback Trend",
        "description": "Retour vers EMA20 en double uptrend (SMA50 > SMA200)",
        "color":       "#818cf8",
        "emoji":       "📉",
        "tp_pct":      0.07,
        "sl_pct":      0.03,
        "fn":          _sig_pullback_trend,
        "screener_strategy": "standard",
        "screener_signal":   "Pullback",
    },
    {
        "key":         "pullback_confirmed",
        "name":        "Pullback Confirmed",
        "description": "Pullback vers EMA20/SMA50 avec rebond confirme",
        "color":       "#22c55e",
        "emoji":       "✓",
        "tp_pct":      0.07,
        "sl_pct":      0.03,
        "fn":          _sig_pullback_confirmed,
        "screener_strategy": "standard",
        "screener_signal":   "Pullback",
    },
    {
        "key":         "breakout_quality",
        "name":        "Breakout Quality",
        "description": "Cassure plus haut 20j avec volume × 1.4 + RSI 52-72",
        "color":       "#f59e0b",
        "emoji":       "🚀",
        "tp_pct":      0.10,
        "sl_pct":      0.04,
        "fn":          _sig_breakout_quality,
        "screener_strategy": "standard",
        "screener_signal":   "Breakout",
    },
    {
        "key":         "relative_strength",
        "name":        "Relative Strength Leader",
        "description": "Action en tête de marché : perf 3m > 8 %, RSI 50-68",
        "color":       "#4ade80",
        "emoji":       "⚡",
        "tp_pct":      0.09,
        "sl_pct":      0.035,
        "fn":          _sig_relative_strength,
        "screener_strategy": "standard",
        "screener_signal":   "Momentum",
    },
    {
        "key":         "low_vol_compounder",
        "name":        "Low Volatility Compounder",
        "description": "ATR faible + SMA50 stable + RSI neutre 45-58",
        "color":       "#38bdf8",
        "emoji":       "🧊",
        "tp_pct":      0.05,
        "sl_pct":      0.02,
        "fn":          _sig_low_vol_compounder,
        "screener_strategy": "conservative",
        "screener_signal":   "",
    },
    {
        "key":         "mean_reversion",
        "name":        "Mean Reversion in Uptrend",
        "description": "Pullback profond (-8%/-1% EMA20), RSI 35-52, volume épuisé",
        "color":       "#f87171",
        "emoji":       "🔄",
        "tp_pct":      0.05,
        "sl_pct":      0.025,
        "fn":          _sig_mean_reversion_uptrend,
        "screener_strategy": "standard",
        "screener_signal":   "Pullback",
    },
]


# ─── Backtest d'un ticker ──────────────────────────────────────────────────────

def backtest_ticker_lab(
    ticker: str,
    df: pd.DataFrame,
    strategy_def: Dict,
    period_months: int = 12,
) -> List[Dict]:
    """
    Simule une stratégie sur un ticker.
    Inclut EMA20 pour les nouvelles fonctions de signal.
    Retourne la liste des trades (incluant les OPEN).
    """
    try:
        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        s50_s  = sma(close, 50)
        s200_s = sma(close, 200)
        e20_s  = ema(close, 20)          # EMA20 — nouveau
        r_s    = rsi(close, 14)
        _, _, mh_s = macd(close)
        atr_s  = atr(high, low, close, 14)

        tp_pct   = strategy_def["tp_pct"]
        sl_pct   = strategy_def["sl_pct"]
        fn       = strategy_def["fn"]
        max_days = 30                     # timeout par défaut

        n              = len(df)
        trading_days   = int(252 * period_months / 12)
        backtest_start = max(200, n - trading_days)

        trades: List[Dict] = []
        in_trade    = False
        entry_price = 0.0
        entry_date  = ""
        entry_idx   = 0

        for i in range(backtest_start, n - 1):
            s50_v  = float(s50_s.iloc[i])
            s200_v = float(s200_s.iloc[i])
            r_v    = float(r_s.iloc[i])
            mh_v   = float(mh_s.iloc[i])
            e20_v  = float(e20_s.iloc[i])

            if any(np.isnan(x) for x in [s50_v, s200_v, r_v, mh_v, e20_v]):
                continue

            if in_trade:
                tp_price    = entry_price * (1.0 + tp_pct)
                sl_price    = entry_price * (1.0 - sl_pct)
                today_high  = float(high.iloc[i])
                today_low   = float(low.iloc[i])
                today_close = float(close.iloc[i])
                days_held   = i - entry_idx

                hit_tp  = today_high >= tp_price
                hit_sl  = today_low  <= sl_price
                timeout = days_held  >= max_days

                if hit_tp and hit_sl:
                    exit_price, reason = sl_price, "SL"
                elif hit_tp:
                    exit_price, reason = tp_price, "TP"
                elif hit_sl:
                    exit_price, reason = sl_price, "SL"
                elif timeout:
                    exit_price, reason = today_close, "TIMEOUT"
                else:
                    continue

                pnl = (exit_price / entry_price - 1.0) * 100.0
                trades.append({
                    "ticker":        ticker,
                    "entry_date":    entry_date,
                    "exit_date":     str(close.index[i])[:10],
                    "entry_price":   round(entry_price, 2),
                    "exit_price":    round(exit_price, 2),
                    "exit_reason":   reason,
                    "pnl_pct":       round(pnl, 2),
                    "duration_days": days_held,
                    "sl_pct":        sl_pct,
                    "tp_pct":        tp_pct,
                })
                in_trade = False

            else:
                try:
                    sig = fn(
                        close, high, low, volume,
                        s50_s, s200_s, r_s, mh_s, atr_s, e20_s, i,
                    )
                except Exception:
                    sig = False

                if sig:
                    entry_price = float(close.iloc[i + 1])
                    entry_date  = str(close.index[i + 1])[:10]
                    entry_idx   = i + 1
                    in_trade    = True

        # Trade encore ouvert à la fin
        if in_trade and len(close) > entry_idx:
            last_close = float(close.iloc[-1])
            pnl        = (last_close / entry_price - 1.0) * 100.0
            trades.append({
                "ticker":        ticker,
                "entry_date":    entry_date,
                "exit_date":     str(close.index[-1])[:10],
                "entry_price":   round(entry_price, 2),
                "exit_price":    round(last_close, 2),
                "exit_reason":   "OPEN",
                "pnl_pct":       round(pnl, 2),
                "duration_days": len(close) - 1 - entry_idx,
                "sl_pct":        sl_pct,
                "tp_pct":        tp_pct,
            })

        return trades

    except Exception:
        return []


# ─── Walk-Forward Validation ───────────────────────────────────────────────────

def _walk_forward_split(
    all_trades: List[Dict],
    train_pct: float = 0.75,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Divise les trades chronologiquement.
    Train : première `train_pct` des trades (75 %).
    Test  : derniers (1 - train_pct) des trades (25 %).
    """
    if not all_trades:
        return [], []
    sorted_t = sorted(
        [t for t in all_trades if t.get("exit_reason") != "OPEN"],
        key=lambda t: t["entry_date"],
    )
    n     = len(sorted_t)
    split = max(1, int(n * train_pct))
    return sorted_t[:split], sorted_t[split:]


def _overfitting_warnings(
    total_trades: int,
    train_pf: float,
    test_pf:  float,
    train_wr: float,
    test_wr:  float,
    ticker_returns: Dict[str, float],
) -> Tuple[bool, List[str]]:
    """
    Détecte les signaux d'overfitting.
    Retourne (overfitting_risk: bool, reasons: List[str]).
    """
    risk    = False
    reasons = []

    # 1. Nombre de trades insuffisant
    if total_trades < 50:
        reasons.append(f"Seulement {total_trades} trades — minimum 50 requis")

    # 2. Divergence train / test (risque majeur)
    if train_pf > 1.5 and test_pf < 1.0:
        risk = True
        reasons.append(f"Divergence train/test : PF train={train_pf:.2f} → PF test={test_pf:.2f}")

    if abs(train_wr - test_wr) > 20:
        risk = True
        reasons.append(
            f"Win rate s'effondre en test : {train_wr:.0f}% → {test_wr:.0f}%"
        )

    # 3. Concentration sur un seul ticker
    if ticker_returns:
        total_abs = sum(abs(v) for v in ticker_returns.values())
        if total_abs > 0:
            best_t  = max(ticker_returns, key=lambda k: abs(ticker_returns[k]))
            best_v  = abs(ticker_returns[best_t])
            conc    = best_v / total_abs
            if conc >= 0.40:
                risk = True
                reasons.append(
                    f"Concentration excessive : {best_t} représente {conc*100:.0f}% du P&L"
                )

    return risk, reasons


# ─── Score composite ───────────────────────────────────────────────────────────

def compute_lab_score(
    total_trades: int,
    win_rate: float,
    expectancy: float,
    max_dd: float,
    profit_factor: float,
    sharpe: float,
    overfitting_risk: bool,
    test_pf: float,
) -> float:
    """
    Score /100 intégrant la robustesse walk-forward.
    Penalise les stratégies avec overfitting ou mauvais test.
    """
    wr_s   = min(win_rate / 65.0,        1.0) * 25
    exp_s  = min(max(expectancy, 0) / 2.5, 1.0) * 20
    pf_s   = min(max(profit_factor - 1.0, 0) / 2.0, 1.0) * 20
    dd_s   = max(0.0, 1.0 - abs(max_dd) / 25.0) * 15
    sh_s   = min(max(sharpe, 0) / 2.0,    1.0) * 10
    tr_s   = min(total_trades / 60.0,     1.0) * 10

    raw = wr_s + exp_s + pf_s + dd_s + sh_s + tr_s

    # Pénalité overfitting
    if overfitting_risk:
        raw *= 0.60
    elif test_pf < 1.0 and total_trades >= 10:
        raw *= 0.80   # test non profitable mais pas d'overfitting flagrant

    return round(raw, 1)


# ─── Agrégation des résultats ──────────────────────────────────────────────────

def aggregate_lab_result(
    strategy_def: Dict,
    all_trades: List[Dict],
    period_months: int,
) -> Dict:
    """
    Calcule les stats agrégées via le Portfolio Backtest Engine
    + Walk-Forward Validation + détection d'overfitting.
    """
    base = {
        "key":               strategy_def["key"],
        "name":              strategy_def["name"],
        "description":       strategy_def["description"],
        "color":             strategy_def["color"],
        "emoji":             strategy_def["emoji"],
        "tp_pct":            int(round(strategy_def["tp_pct"] * 100)),
        "sl_pct":            int(round(strategy_def["sl_pct"] * 100)),
        "screener_strategy": strategy_def["screener_strategy"],
        "screener_signal":   strategy_def["screener_signal"],
        "period_months":     period_months,
    }

    # ── Simulation portfolio complète ─────────────────────────────────────────
    closed_trades = [t for t in all_trades if t.get("exit_reason") != "OPEN"]
    portfolio     = run_portfolio_backtest(closed_trades, period_months, INITIAL_CAPITAL)

    # ── Walk-Forward (75 % train / 25 % test) ─────────────────────────────────
    train_trades, test_trades = _walk_forward_split(all_trades, train_pct=0.75)

    empty = _empty_result(INITIAL_CAPITAL)
    train_portfolio = (
        run_portfolio_backtest(train_trades, period_months, INITIAL_CAPITAL)
        if train_trades else empty
    )
    test_portfolio = (
        run_portfolio_backtest(test_trades, period_months, INITIAL_CAPITAL)
        if test_trades else empty
    )

    train_pf = train_portfolio["profit_factor"]
    test_pf  = test_portfolio["profit_factor"]
    train_wr = train_portfolio["win_rate"]
    test_wr  = test_portfolio["win_rate"]

    # Dégradation en %
    wr_degradation = round(train_wr - test_wr, 1)
    pf_degradation = round((train_pf - test_pf) / max(train_pf, 0.01) * 100, 1)

    # ── Ticker returns ($ par ticker) ─────────────────────────────────────────
    ticker_returns: Dict[str, float] = {}
    for t in portfolio.get("trades", []):
        tk = t["ticker"]
        ticker_returns[tk] = ticker_returns.get(tk, 0.0) + t["pnl_dollars"]

    # ── Overfitting detection ─────────────────────────────────────────────────
    overfitting_risk, overfitting_reasons = _overfitting_warnings(
        portfolio["total_trades"],
        train_pf, test_pf,
        train_wr, test_wr,
        ticker_returns,
    )

    # ── Score final ───────────────────────────────────────────────────────────
    score = compute_lab_score(
        portfolio["total_trades"],
        portfolio["win_rate"],
        portfolio["expectancy"],
        portfolio["max_drawdown_pct"],
        portfolio["profit_factor"],
        portfolio["sharpe_ratio"],
        overfitting_risk,
        test_pf,
    )

    # eligible = au moins 30 trades (affichage) ; TRADABLE = ≥ 50 (portfolio_backtest)
    eligible = portfolio["total_trades"] >= 30

    return {
        **base,
        **portfolio,
        "score":   score,
        "eligible": eligible,
        "ticker_returns": ticker_returns,

        # ── Walk-Forward ──────────────────────────────────────────────────────
        "walk_forward": {
            "train_trades":    train_portfolio["total_trades"],
            "train_win_rate":  train_portfolio["win_rate"],
            "train_pf":        train_pf,
            "train_expectancy":train_portfolio["expectancy"],
            "test_trades":     test_portfolio["total_trades"],
            "test_win_rate":   test_wr,
            "test_pf":         test_pf,
            "test_expectancy": test_portfolio["expectancy"],
            "wr_degradation":  wr_degradation,
            "pf_degradation":  pf_degradation,
        },

        # ── Overfitting ───────────────────────────────────────────────────────
        "overfitting_risk":    overfitting_risk,
        "overfitting_reasons": overfitting_reasons,
    }
