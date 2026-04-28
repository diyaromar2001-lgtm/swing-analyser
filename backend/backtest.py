import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Literal
from indicators import sma, rsi, macd, atr
from strategy import detect_buy_signal_standard, detect_buy_signal_conservative
from indicators import perf_pct as calc_perf_pct


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    exit_reason: str    # "TP" | "SL" | "TIMEOUT" | "OPEN"
    pnl_pct: float
    duration_days: int


@dataclass
class BacktestResult:
    ticker: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_gain_pct: float
    avg_loss_pct: float
    expectancy: float
    max_drawdown_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    total_return_pct: float
    avg_duration_days: float
    reliable: bool          # True si >= 5 trades
    trades: List[dict]
    error: Optional[str] = None


TP_PCT = 0.05   # +5 % — aligné sur le Portfolio Backtest Engine
SL_PCT = 0.02   # -2 % — identique pour tous les backtests


def run_backtest(ticker: str, df: pd.DataFrame, strategy: str = "standard") -> BacktestResult:
    """
    Simule les trades sur les 12 derniers mois de données.
    Entrée : signal BUY NOW détecté
    TP : +5%, SL : -2%, timeout : 30 jours
    Les trade dicts incluent sl_pct/tp_pct pour compatibilité
    avec run_portfolio_backtest().
    """
    try:
        close = df["Close"].squeeze()
        high  = df["High"].squeeze()
        low   = df["Low"].squeeze()

        # Indicateurs
        sma200_s = sma(close, 200)
        sma50_s  = sma(close, 50)
        rsi_s    = rsi(close, 14)
        _, _, macd_hist_s = macd(close)

        # On backtest sur les 252 derniers jours (~1 an)
        backtest_start = max(200, len(df) - 252)
        indices = range(backtest_start, len(df) - 1)

        trades: List[Trade] = []
        in_trade = False
        entry_price = 0.0
        entry_date = ""
        entry_idx = 0

        for i in indices:
            today_close = float(close.iloc[i])
            today_date  = str(close.index[i])[:10]

            if in_trade:
                # Vérifier TP, SL, timeout
                tp_price = entry_price * (1 + TP_PCT)
                sl_price = entry_price * (1 - SL_PCT)
                days_held = i - entry_idx
                today_high = float(high.iloc[i])
                today_low  = float(low.iloc[i])

                hit_tp = today_high >= tp_price
                hit_sl = today_low  <= sl_price
                timeout = days_held >= 30

                if hit_tp and hit_sl:
                    # Les deux touchés le même jour → on sort au SL (pire cas)
                    exit_price  = sl_price
                    exit_reason = "SL"
                elif hit_tp:
                    exit_price  = tp_price
                    exit_reason = "TP"
                elif hit_sl:
                    exit_price  = sl_price
                    exit_reason = "SL"
                elif timeout:
                    exit_price  = today_close
                    exit_reason = "TIMEOUT"
                else:
                    continue

                pnl = (exit_price / entry_price - 1) * 100
                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=today_date,
                    entry_price=round(entry_price, 2),
                    exit_price=round(exit_price, 2),
                    exit_reason=exit_reason,
                    pnl_pct=round(pnl, 2),
                    duration_days=days_held,
                ))
                in_trade = False

            else:
                # Chercher un signal d'entrée
                s200 = float(sma200_s.iloc[i])
                s50  = float(sma50_s.iloc[i])
                r    = float(rsi_s.iloc[i])
                mh   = float(macd_hist_s.iloc[i])

                if np.isnan(s200) or np.isnan(s50) or np.isnan(r) or np.isnan(mh):
                    continue

                # Perf rolling pour conservative
                p3m = calc_perf_pct(close.iloc[:i+1], 63)
                p6m = calc_perf_pct(close.iloc[:i+1], 126)

                if strategy == "conservative":
                    signal = detect_buy_signal_conservative(today_close, s50, s200, r, mh, p3m, p6m)
                else:
                    signal = detect_buy_signal_standard(today_close, s50, s200, r, mh)

                if signal:
                    # Entrée au close du jour suivant
                    next_open = float(close.iloc[i + 1])
                    in_trade   = True
                    entry_price = next_open
                    entry_date  = str(close.index[i + 1])[:10]
                    entry_idx   = i + 1

        # Si on est encore en trade à la fin → fermer au dernier prix
        if in_trade and len(close) > entry_idx:
            last_close  = float(close.iloc[-1])
            last_date   = str(close.index[-1])[:10]
            pnl         = (last_close / entry_price - 1) * 100
            days_held   = len(close) - 1 - entry_idx
            trades.append(Trade(
                entry_date=entry_date,
                exit_date=last_date,
                entry_price=round(entry_price, 2),
                exit_price=round(last_close, 2),
                exit_reason="OPEN",
                pnl_pct=round(pnl, 2),
                duration_days=days_held,
            ))

        if len(trades) == 0:
            return BacktestResult(
                ticker=ticker, total_trades=0, wins=0, losses=0,
                win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
                expectancy=0, max_drawdown_pct=0,
                best_trade_pct=0, worst_trade_pct=0,
                total_return_pct=0, avg_duration_days=0,
                reliable=False,
                trades=[],
                error="Aucun signal détecté sur la période",
            )

        # Calcul des stats
        pnls       = [t.pnl_pct for t in trades]
        wins_list  = [p for p in pnls if p > 0]
        loss_list  = [p for p in pnls if p <= 0]

        win_rate    = len(wins_list) / len(pnls) * 100
        avg_gain    = float(np.mean(wins_list)) if wins_list else 0.0
        avg_loss    = float(np.mean(loss_list)) if loss_list else 0.0
        expectancy  = (win_rate / 100 * avg_gain) + ((1 - win_rate / 100) * avg_loss)

        # Max drawdown sur la courbe d'équité cumulée
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns   = cumulative - running_max
        max_dd      = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

        total_return   = float(np.sum(pnls))
        avg_duration   = float(np.mean([t.duration_days for t in trades]))

        return BacktestResult(
            ticker=ticker,
            total_trades=len(trades),
            wins=len(wins_list),
            losses=len(loss_list),
            win_rate=round(win_rate, 1),
            avg_gain_pct=round(avg_gain, 2),
            avg_loss_pct=round(avg_loss, 2),
            expectancy=round(expectancy, 2),
            max_drawdown_pct=round(max_dd, 2),
            best_trade_pct=round(max(pnls), 2),
            worst_trade_pct=round(min(pnls), 2),
            total_return_pct=round(total_return, 2),
            avg_duration_days=round(avg_duration, 1),
            reliable=len(trades) >= 5,
            trades=[{
                "entry_date":    t.entry_date,
                "exit_date":     t.exit_date,
                "entry_price":   t.entry_price,
                "exit_price":    t.exit_price,
                "exit_reason":   t.exit_reason,
                "pnl_pct":       t.pnl_pct,
                "duration_days": t.duration_days,
                "sl_pct":        SL_PCT,   # pour run_portfolio_backtest
                "tp_pct":        TP_PCT,
            } for t in trades],
        )

    except Exception as e:
        return BacktestResult(
            ticker=ticker, total_trades=0, wins=0, losses=0,
            win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
            expectancy=0, max_drawdown_pct=0,
            best_trade_pct=0, worst_trade_pct=0,
            total_return_pct=0, avg_duration_days=0,
            reliable=False, trades=[],
            error=str(e),
        )
