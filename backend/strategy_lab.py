"""
Strategy Lab — backteste 6 stratégies swing trading et les classe.
Utilise le Portfolio Backtest Engine pour une simulation réaliste
avec gestion du capital (10 000 $ · risque 1 % · max 8 positions).
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from indicators import sma, rsi, macd, atr
from portfolio_backtest import run_portfolio_backtest, INITIAL_CAPITAL


# ── Définition des stratégies ─────────────────────────────────────────────────

def _sig_pullback_sma50(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """Pullback vers SMA50 en uptrend."""
    p   = float(close.iloc[i])
    s50 = float(s50_s.iloc[i])
    s200= float(s200_s.iloc[i])
    r   = float(r_s.iloc[i])
    mh  = float(mh_s.iloc[i])
    if s50 <= 0 or s200 <= 0:
        return False
    dist = (p - s50) / s50 * 100
    return (
        p > s200
        and -5.0 <= dist <= 0.5
        and 40 <= r <= 57
        and mh > -0.3
    )


def _sig_breakout_30d(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """Cassure du plus haut des 30 derniers jours avec volume."""
    if i < 30:
        return False
    p    = float(close.iloc[i])
    h    = float(high.iloc[i])
    s200 = float(s200_s.iloc[i])
    r    = float(r_s.iloc[i])
    mh   = float(mh_s.iloc[i])
    if s200 <= 0:
        return False
    high_30  = float(high.iloc[i - 29: i + 1].max())
    vol_avg  = float(volume.iloc[max(0, i - 19): i + 1].mean())
    vol_cur  = float(volume.iloc[i])
    return (
        p > s200
        and h >= high_30
        and 55 <= r <= 76
        and mh > 0
        and vol_cur > vol_avg * 1.25
    )


def _sig_momentum_fort(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """RSI 60-72 + MACD positif + surperformance 3 mois."""
    if i < 63:
        return False
    p    = float(close.iloc[i])
    s50  = float(s50_s.iloc[i])
    s200 = float(s200_s.iloc[i])
    r    = float(r_s.iloc[i])
    mh   = float(mh_s.iloc[i])
    if s50 <= 0 or s200 <= 0:
        return False
    p3m = (p / float(close.iloc[i - 63]) - 1) * 100
    return (
        p > s50
        and s50 > s200
        and 60 <= r <= 72
        and mh > 0
        and p3m > 5.0
    )


def _sig_mean_reversion(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """Pullback profond (5-15%) sous SMA50 en tendance haussière."""
    p    = float(close.iloc[i])
    s50  = float(s50_s.iloc[i])
    s200 = float(s200_s.iloc[i])
    r    = float(r_s.iloc[i])
    if s50 <= 0 or s200 <= 0:
        return False
    dist = (p - s50) / s50 * 100
    return (
        p > s200
        and -15.0 <= dist <= -5.0
        and 30 <= r <= 48
    )


def _sig_low_vol_swing(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """ATR stable + prix dans ±2% de SMA50 + RSI neutre."""
    if i < 20:
        return False
    p    = float(close.iloc[i])
    s50  = float(s50_s.iloc[i])
    s200 = float(s200_s.iloc[i])
    r    = float(r_s.iloc[i])
    if s50 <= 0 or s200 <= 0:
        return False
    dist     = (p - s50) / s50 * 100
    atr_vals = atr_s.iloc[i - 19: i + 1]
    atr_m    = float(atr_vals.mean())
    stable   = (float(atr_vals.std()) / atr_m < 0.20) if atr_m > 0 else False
    return (
        p > s200
        and -2.0 <= dist <= 2.0
        and 45 <= r <= 60
        and stable
    )


def _sig_conservative_trend(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i):
    """Tendance stricte: RSI 50-62, MACD>0, perf 3m et 6m positives."""
    if i < 126:
        return False
    p    = float(close.iloc[i])
    s50  = float(s50_s.iloc[i])
    s200 = float(s200_s.iloc[i])
    r    = float(r_s.iloc[i])
    mh   = float(mh_s.iloc[i])
    if s50 <= 0 or s200 <= 0:
        return False
    dist = (p - s50) / s50 * 100
    p3m  = (p / float(close.iloc[i - 63]) - 1) * 100
    p6m  = (p / float(close.iloc[i - 126]) - 1) * 100
    return (
        p > s200
        and -1.0 <= dist <= 2.5
        and 50 <= r <= 62
        and mh > 0
        and p3m > 0
        and p6m > 0
        and r < 65
    )


# ── Registre des stratégies ────────────────────────────────────────────────────

LAB_STRATEGIES: List[Dict] = [
    {
        "key":         "pullback_sma50",
        "name":        "Pullback SMA50",
        "description": "Achat sur retour vers SMA50 en tendance haussière",
        "color":       "#818cf8",
        "emoji":       "📉",
        "tp_pct":      0.07,
        "sl_pct":      0.03,
        "fn":          _sig_pullback_sma50,
        "screener_strategy": "standard",
        "screener_signal":   "Pullback",
    },
    {
        "key":         "breakout_30d",
        "name":        "Breakout 30 jours",
        "description": "Cassure du plus haut des 30 jours avec volume",
        "color":       "#f59e0b",
        "emoji":       "🚀",
        "tp_pct":      0.10,
        "sl_pct":      0.04,
        "fn":          _sig_breakout_30d,
        "screener_strategy": "standard",
        "screener_signal":   "Breakout",
    },
    {
        "key":         "momentum_fort",
        "name":        "Momentum Fort",
        "description": "RSI 60-72 + MACD positif + surperformance 3 mois",
        "color":       "#4ade80",
        "emoji":       "⚡",
        "tp_pct":      0.08,
        "sl_pct":      0.03,
        "fn":          _sig_momentum_fort,
        "screener_strategy": "standard",
        "screener_signal":   "Momentum",
    },
    {
        "key":         "mean_reversion",
        "name":        "Mean Reversion Qualité",
        "description": "Achat sur pullback profond (5-15%) en uptrend",
        "color":       "#f87171",
        "emoji":       "🔄",
        "tp_pct":      0.06,
        "sl_pct":      0.03,
        "fn":          _sig_mean_reversion,
        "screener_strategy": "standard",
        "screener_signal":   "Pullback",
    },
    {
        "key":         "low_vol_swing",
        "name":        "Low Volatility Swing",
        "description": "ATR stable + prix proche SMA50 + RSI neutre",
        "color":       "#38bdf8",
        "emoji":       "🧊",
        "tp_pct":      0.05,
        "sl_pct":      0.02,
        "fn":          _sig_low_vol_swing,
        "screener_strategy": "conservative",
        "screener_signal":   "",
    },
    {
        "key":         "conservative_trend",
        "name":        "Conservative Trend",
        "description": "Tendance stricte: RSI 50-62, MACD>0, perf positive",
        "color":       "#34d399",
        "emoji":       "🛡",
        "tp_pct":      0.05,
        "sl_pct":      0.02,
        "fn":          _sig_conservative_trend,
        "screener_strategy": "conservative",
        "screener_signal":   "",
    },
]


# ── Backtest d'un ticker pour une stratégie ───────────────────────────────────

def backtest_ticker_lab(ticker: str, df: pd.DataFrame, strategy_def: Dict, period_months: int = 12) -> List[Dict]:
    """Simule une stratégie sur un ticker. Retourne la liste des trades."""
    try:
        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        s50_s  = sma(close, 50)
        s200_s = sma(close, 200)
        r_s    = rsi(close, 14)
        _, _, mh_s = macd(close)
        atr_s  = atr(high, low, close, 14)

        tp_pct   = strategy_def["tp_pct"]
        sl_pct   = strategy_def["sl_pct"]
        fn       = strategy_def["fn"]
        max_days = 30

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
            if any(np.isnan([s50_v, s200_v, r_v, mh_v])):
                continue

            if in_trade:
                tp_price    = entry_price * (1 + tp_pct)
                sl_price    = entry_price * (1 - sl_pct)
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

                pnl = (exit_price / entry_price - 1) * 100
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
                    sig = fn(close, high, low, volume, s50_s, s200_s, r_s, mh_s, atr_s, i)
                except Exception:
                    sig = False
                if sig:
                    entry_price = float(close.iloc[i + 1])
                    entry_date  = str(close.index[i + 1])[:10]
                    entry_idx   = i + 1
                    in_trade    = True

        # Trade ouvert à la fin
        if in_trade and len(close) > entry_idx:
            last_close = float(close.iloc[-1])
            pnl        = (last_close / entry_price - 1) * 100
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


# ── Agrégation des résultats ──────────────────────────────────────────────────

def compute_lab_score(total_trades: int, win_rate: float, expectancy: float, max_dd: float) -> float:
    """Score /100 : win rate 35%, expectancy 30%, drawdown 20%, trades 15%."""
    wr_score  = min(win_rate / 65.0, 1.0) * 35
    exp_score = min(max(expectancy, 0) / 2.5, 1.0) * 30
    dd_score  = max(0.0, 1.0 - abs(max_dd) / 25.0) * 20
    tr_score  = min(total_trades / 40.0, 1.0) * 15
    return round(wr_score + exp_score + dd_score + tr_score, 1)


def aggregate_lab_result(strategy_def: Dict, all_trades: List[Dict], period_months: int) -> Dict:
    """
    Calcule les stats agrégées d'une stratégie via le Portfolio Backtest Engine.

    Remplace la simple sommation de % par une simulation réaliste :
      - Capital 10 000 $, risque 1 % / trade, max 8 positions simultanées
      - Position sizing dynamique (sl_pct de chaque trade)
      - Commission 0.05 % aller/retour
    Les signaux fonctions (LAB_STRATEGIES) et backtest_ticker_lab() restent inchangés.
    """
    # ── Métadonnées de la stratégie ───────────────────────────────────────────
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

    # ── Simulation portfolio ──────────────────────────────────────────────────
    portfolio = run_portfolio_backtest(all_trades, period_months, INITIAL_CAPITAL)

    # ── Score composite (compatible avec le tri existant) ────────────────────
    score = compute_lab_score(
        portfolio["total_trades"],
        portfolio["win_rate"],
        portfolio["expectancy"],          # % moyen / trade
        portfolio["max_drawdown_pct"],
    )

    # ── ticker_returns en $ (pour compatibilité avec les outils existants) ───
    ticker_returns: Dict[str, float] = {}
    for t in portfolio.get("trades", []):
        tk = t["ticker"]
        ticker_returns[tk] = ticker_returns.get(tk, 0.0) + t["pnl_dollars"]

    return {
        **base,
        **portfolio,
        "score":          score,
        "eligible":       portfolio["total_trades"] >= 20,
        "ticker_returns": ticker_returns,
    }
