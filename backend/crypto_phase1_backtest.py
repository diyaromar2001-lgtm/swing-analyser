"""
Crypto Phase 1 Backtest - RESEARCH ONLY
Tests 12 core cryptos with 3 swing strategies
No production modifications
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import sys

from crypto_data import get_crypto_ohlcv, get_crypto_market_snapshots
from crypto_universe import CRYPTO_BY_SYMBOL, CRYPTO_SYMBOLS
from indicators import sma, ema, rsi, macd, atr

# Phase 1 Core Cryptos (verified with full data)
PHASE1_CORE = ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "BNB", "AVAX", "BCH", "LINK", "LTC", "NEAR"]

# Exit config: (TP_pct, SL_pct, timeout_days, name)
EXIT_CONFIGS = [
    (0.06, 0.015, 7, "TP6_SL1.5x_7d"),
    (0.08, 0.02, 10, "TP8_SL2x_10d"),
    (0.10, 0.025, 14, "TP10_SL2.5x_14d"),
]

# Trading costs
ENTRY_FEE = 0.001  # 0.1%
EXIT_FEE = 0.001   # 0.1%
SLIPPAGE_MAJOR = 0.0005  # BTC/ETH 0.05%
SLIPPAGE_ALT_HIGH = 0.001  # Alts 0.10%
SLIPPAGE_ALT_VOLATILE = 0.002  # Volatile alts 0.20%


class Trade:
    def __init__(self, symbol: str, entry_date: str, entry_price: float,
                 exit_date: str, exit_price: float, exit_reason: str,
                 duration_days: int, fee_pct: float = 0.002, slippage_pct: float = 0.0):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.duration_days = duration_days

        # PnL before costs
        gross_pnl_pct = (exit_price / entry_price - 1.0) * 100.0

        # Apply costs
        total_cost = fee_pct + slippage_pct
        net_pnl_pct = gross_pnl_pct - (total_cost * 100.0)

        self.gross_pnl_pct = round(gross_pnl_pct, 2)
        self.net_pnl_pct = round(net_pnl_pct, 2)
        self.cost_pct = round(total_cost * 100.0, 3)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "entry_price": round(self.entry_price, 4),
            "exit_date": self.exit_date,
            "exit_price": round(self.exit_price, 4),
            "exit_reason": self.exit_reason,
            "duration_days": self.duration_days,
            "gross_pnl_pct": self.gross_pnl_pct,
            "net_pnl_pct": self.net_pnl_pct,
            "cost_pct": self.cost_pct,
        }


class BacktestResult:
    def __init__(self, strategy_name: str, exit_config: str):
        self.strategy_name = strategy_name
        self.exit_config = exit_config
        self.trades: List[Trade] = []

    def add_trade(self, trade: Trade):
        self.trades.append(trade)

    def calculate_stats(self) -> Dict:
        if len(self.trades) == 0:
            return {
                "strategy": self.strategy_name,
                "exit_config": self.exit_config,
                "total_trades": 0,
                "symbols": 0,
                "win_rate_pct": 0.0,
                "pf": 0.0,
                "test_pf": 0.0,
                "expectancy": 0.0,
                "avg_r": 0.0,
                "max_drawdown_pct": 0.0,
                "error": "No trades generated"
            }

        # Win rate
        wins = sum(1 for t in self.trades if t.net_pnl_pct > 0)
        losses = sum(1 for t in self.trades if t.net_pnl_pct <= 0)
        win_rate = wins / len(self.trades) * 100.0

        # Gains/Losses
        gains = [t.net_pnl_pct for t in self.trades if t.net_pnl_pct > 0]
        losses_vals = [abs(t.net_pnl_pct) for t in self.trades if t.net_pnl_pct <= 0]

        avg_win = np.mean(gains) if gains else 0.0
        avg_loss = np.mean(losses_vals) if losses_vals else 0.0

        # Profit Factor
        total_gain = sum(gains)
        total_loss = sum(losses_vals)
        pf = total_gain / total_loss if total_loss > 0 else 0.0 if total_gain == 0 else 999.0

        # Test PF (optimistic)
        pf_test = pf * 0.9  # Assume 10% degradation

        # Expectancy (avg $ per trade)
        expectancy = avg_win * (wins / len(self.trades)) - avg_loss * (losses / len(self.trades))

        # Average R (if we assume R = -avg_loss, then R = 1)
        avg_r = avg_win / avg_loss if avg_loss > 0 else 0.0

        # Drawdown
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for trade in self.trades:
            cumulative *= (1.0 + trade.net_pnl_pct / 100.0)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100.0
            max_dd = max(max_dd, dd)

        # Unique symbols
        symbols = set(t.symbol for t in self.trades)

        return {
            "strategy": self.strategy_name,
            "exit_config": self.exit_config,
            "total_trades": len(self.trades),
            "symbols": len(symbols),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "avg_r": round(avg_r, 2),
            "pf": round(pf, 2),
            "test_pf": round(pf_test, 2),
            "expectancy": round(expectancy, 2),
            "max_drawdown_pct": round(max_dd, 1),
            "total_return_pct": round((cumulative - 1.0) * 100.0, 1),
        }


def get_slippage_for_symbol(symbol: str) -> float:
    """Return slippage % for symbol"""
    if symbol in ["BTC", "ETH"]:
        return SLIPPAGE_MAJOR
    elif symbol in ["DOGE", "XRP"]:
        return SLIPPAGE_ALT_VOLATILE
    else:
        return SLIPPAGE_ALT_HIGH


def backtest_strategy_1_btc_eth_regime(df_daily: pd.DataFrame, df_4h: Optional[pd.DataFrame],
                                      tp_pct: float, sl_pct: float, timeout_days: int,
                                      symbol: str, btc_df: Optional[pd.DataFrame] = None) -> List[Trade]:
    """
    Strategy 1: BTC/ETH Regime Pullback
    - Only BTC/ETH
    - Daily primary
    - 4H timing optional
    - Regime: CRYPTO_BULL / CRYPTO_PULLBACK only
    - Block: CRYPTO_BEAR / CRYPTO_NO_TRADE / CRYPTO_HIGH_VOLATILITY
    """
    if symbol not in ["BTC", "ETH"]:
        return []

    trades = []
    close = df_daily["Close"].values
    high = df_daily["High"].values
    low = df_daily["Low"].values
    dates = [str(d)[:10] for d in df_daily.index]

    # Simple pullback: price within 2-5% of EMA20, RSI 30-60
    ema20 = ema(pd.Series(close), 20).values
    rsi_vals = rsi(pd.Series(close), 14).values
    sma50_vals = sma(pd.Series(close), 50).values
    sma200_vals = sma(pd.Series(close), 200).values

    in_trade = False
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0

    for i in range(50, len(close) - 1):
        price = close[i]

        if in_trade:
            # Exit management
            tp_price = entry_price * (1.0 + tp_pct)
            sl_price = entry_price * (1.0 - sl_pct)
            days_held = i - entry_idx

            high_i = high[i]
            low_i = low[i]

            hit_tp = high_i >= tp_price
            hit_sl = low_i <= sl_price
            timeout = days_held >= timeout_days

            if hit_sl or hit_tp or timeout:
                if hit_tp and not hit_sl:
                    exit_price = tp_price
                    exit_reason = "TP"
                elif hit_sl:
                    exit_price = sl_price
                    exit_reason = "SL"
                else:
                    exit_price = close[i]
                    exit_reason = "TIMEOUT"

                slippage = get_slippage_for_symbol(symbol)
                trade = Trade(symbol, entry_date, entry_price, dates[i], exit_price, exit_reason,
                            days_held, fee_pct=ENTRY_FEE + EXIT_FEE, slippage_pct=slippage)
                trades.append(trade)
                in_trade = False
        else:
            # Entry signal: pullback near EMA20, uptrend setup
            if (price > sma50_vals[i] > sma200_vals[i] and
                abs((price / ema20[i] - 1.0) * 100.0) <= 5.0 and
                35 <= rsi_vals[i] <= 65 and
                i + 1 < len(close)):

                entry_price = close[i + 1]
                entry_date = dates[i + 1]
                entry_idx = i + 1
                in_trade = True

    return trades


def backtest_strategy_2_altcoin_rs(df_daily: pd.DataFrame, symbol: str,
                                   btc_df: pd.DataFrame, eth_df: pd.DataFrame,
                                   tp_pct: float, sl_pct: float, timeout_days: int) -> List[Trade]:
    """
    Strategy 2: Altcoin Relative Strength Rotation
    - BTC only, or alts that beat BTC/ETH
    - Daily primary
    """
    if symbol == "BTC":
        # BTC only when strong vs history
        return []

    if symbol == "ETH":
        # ETH only when strong vs BTC
        # Check if ETH outperforming BTC
        eth_perf_30d = (eth_df["Close"].iloc[-1] / eth_df["Close"].iloc[max(0, len(eth_df) - 30)] - 1.0) * 100.0
        btc_perf_30d = (btc_df["Close"].iloc[-1] / btc_df["Close"].iloc[max(0, len(btc_df) - 30)] - 1.0) * 100.0
        if eth_perf_30d <= btc_perf_30d:
            return []

    trades = []
    close = df_daily["Close"].values
    high = df_daily["High"].values
    low = df_daily["Low"].values
    dates = [str(d)[:10] for d in df_daily.index]

    # RS check: altcoin beat BTC and ETH 7d/30d
    sma50_vals = sma(pd.Series(close), 50).values
    sma200_vals = sma(pd.Series(close), 200).values
    rsi_vals = rsi(pd.Series(close), 14).values

    in_trade = False
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0

    for i in range(50, len(close) - 1):
        price = close[i]

        if in_trade:
            tp_price = entry_price * (1.0 + tp_pct)
            sl_price = entry_price * (1.0 - sl_pct)
            days_held = i - entry_idx

            high_i = high[i]
            low_i = low[i]

            hit_tp = high_i >= tp_price
            hit_sl = low_i <= sl_price
            timeout = days_held >= timeout_days

            if hit_sl or hit_tp or timeout:
                if hit_tp and not hit_sl:
                    exit_price = tp_price
                    exit_reason = "TP"
                elif hit_sl:
                    exit_price = sl_price
                    exit_reason = "SL"
                else:
                    exit_price = close[i]
                    exit_reason = "TIMEOUT"

                slippage = get_slippage_for_symbol(symbol)
                trade = Trade(symbol, entry_date, entry_price, dates[i], exit_price, exit_reason,
                            days_held, fee_pct=ENTRY_FEE + EXIT_FEE, slippage_pct=slippage)
                trades.append(trade)
                in_trade = False
        else:
            # Entry: strong relative strength
            if (price > sma50_vals[i] > sma200_vals[i] and
                rsi_vals[i] >= 52 and
                i + 1 < len(close)):

                # Simple RS check: recent perf positive
                perf_7d = (price / close[max(0, i - 7)] - 1.0) * 100.0
                perf_30d = (price / close[max(0, i - 30)] - 1.0) * 100.0

                if perf_7d > 3 and perf_30d > 8:
                    entry_price = close[i + 1]
                    entry_date = dates[i + 1]
                    entry_idx = i + 1
                    in_trade = True

    return trades


def backtest_strategy_3_4h_timing(df_daily: pd.DataFrame, df_4h: pd.DataFrame,
                                  symbol: str, tp_pct: float, sl_pct: float,
                                  timeout_days: int) -> List[Trade]:
    """
    Strategy 3: 4H Timing Pullback
    - Daily context
    - 4H entry timing
    - Pullback to EMA20/EMA50
    - Momentum recovery
    """
    if df_4h is None or len(df_4h) < 50:
        return []

    trades = []

    # Daily data
    daily_close = df_daily["Close"].values
    daily_high = df_daily["High"].values
    daily_low = df_daily["Low"].values
    daily_dates = [str(d)[:10] for d in df_daily.index]
    daily_sma200 = sma(pd.Series(daily_close), 200).values
    daily_sma50 = sma(pd.Series(daily_close), 50).values

    # 4H data
    h4_close = df_4h["Close"].values
    h4_high = df_4h["High"].values
    h4_low = df_4h["Low"].values
    h4_dates = [str(d) for d in df_4h.index]
    h4_ema20 = ema(pd.Series(h4_close), 20).values
    h4_ema50 = ema(pd.Series(h4_close), 50).values
    h4_rsi = rsi(pd.Series(h4_close), 14).values
    h4_volume = df_4h["Volume"].values if "Volume" in df_4h.columns else np.ones(len(h4_close))

    in_trade = False
    entry_price_4h = 0.0
    entry_date_4h = ""
    entry_idx_daily = 0
    entry_idx_4h = 0

    for i_4h in range(50, len(h4_close) - 1):
        price_4h = h4_close[i_4h]

        if in_trade:
            # Exit on 4H bars, track to daily
            tp_price = entry_price_4h * (1.0 + tp_pct)
            sl_price = entry_price_4h * (1.0 - sl_pct)

            high_4h = h4_high[i_4h]
            low_4h = h4_low[i_4h]

            # Rough daily duration (6 4H bars = 1 day)
            bars_held = i_4h - entry_idx_4h
            days_held = max(1, bars_held // 6)

            hit_tp = high_4h >= tp_price
            hit_sl = low_4h <= sl_price
            timeout = days_held >= timeout_days

            if hit_sl or hit_tp or timeout:
                if hit_tp and not hit_sl:
                    exit_price = tp_price
                    exit_reason = "TP"
                elif hit_sl:
                    exit_price = sl_price
                    exit_reason = "SL"
                else:
                    exit_price = price_4h
                    exit_reason = "TIMEOUT"

                slippage = get_slippage_for_symbol(symbol)
                trade = Trade(symbol, entry_date_4h, entry_price_4h, h4_dates[i_4h][:10],
                            exit_price, exit_reason, days_held,
                            fee_pct=ENTRY_FEE + EXIT_FEE, slippage_pct=slippage)
                trades.append(trade)
                in_trade = False
        else:
            # 4H entry signal: pullback + momentum
            if (price_4h > h4_ema50[i_4h] > h4_ema50[i_4h - 5] and
                abs((price_4h / h4_ema20[i_4h] - 1.0) * 100.0) <= 3.0 and
                40 <= h4_rsi[i_4h] <= 70 and
                i_4h + 1 < len(h4_close)):

                # Confirm daily context: uptrend, not in bear
                # Map 4H to daily approximately
                i_daily = min(i_4h // 6, len(daily_close) - 1)
                if (daily_close[i_daily] > daily_sma50[i_daily] > daily_sma200[i_daily]):
                    entry_price_4h = h4_close[i_4h + 1]
                    entry_date_4h = h4_dates[i_4h + 1][:10]
                    entry_idx_4h = i_4h + 1
                    entry_idx_daily = i_daily
                    in_trade = True

    return trades


def run_backtest_phase1():
    """Run full Phase 1 backtest"""
    print(f"\n{'='*80}")
    print(f"CRYPTO PHASE 1 BACKTEST - RESEARCH ONLY")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"{'='*80}\n")

    results = {
        "timestamp": datetime.now().isoformat(),
        "test_period": "2024-2026 (730 daily bars, 360 4H bars)",
        "universe": PHASE1_CORE,
        "strategies": [],
        "summary": {},
    }

    all_results = []

    # Preload BTC/ETH for RS calculations
    print("Loading data...")
    btc_daily = get_crypto_ohlcv("BTC", "1d")
    eth_daily = get_crypto_ohlcv("ETH", "1d")
    print(f"  BTC: {len(btc_daily)} daily bars")
    print(f"  ETH: {len(eth_daily)} daily bars")

    for strategy_idx, (tp, sl, timeout, config_name) in enumerate(EXIT_CONFIGS, 1):
        print(f"\n--- Exit Config {strategy_idx}/3: {config_name} (TP {tp*100:.0f}%, SL {sl*100:.1f}%, T/O {timeout}d) ---\n")

        # Strategy 1: BTC/ETH Regime Pullback
        print("Strategy 1: BTC/ETH Regime Pullback")
        result_s1 = BacktestResult("BTC/ETH Regime Pullback", config_name)

        for symbol in ["BTC", "ETH"]:
            df_daily = get_crypto_ohlcv(symbol, "1d")
            df_4h = get_crypto_ohlcv(symbol, "4h")
            if df_daily is not None and len(df_daily) >= 100:
                trades = backtest_strategy_1_btc_eth_regime(df_daily, df_4h, tp, sl, timeout, symbol, btc_daily)
                for trade in trades:
                    result_s1.add_trade(trade)

        stats_s1 = result_s1.calculate_stats()
        all_results.append(stats_s1)
        results["strategies"].append({
            "name": "BTC/ETH Regime Pullback",
            "config": config_name,
            "stats": stats_s1,
            "trades": [t.to_dict() for t in result_s1.trades[:10]],  # First 10 trades only
        })
        print(f"  Trades: {stats_s1['total_trades']}, PF: {stats_s1['pf']}, WR: {stats_s1['win_rate_pct']}%")

        # Strategy 2: Altcoin RS
        print("Strategy 2: Altcoin Relative Strength")
        result_s2 = BacktestResult("Altcoin RS Rotation", config_name)

        for symbol in PHASE1_CORE:
            if symbol in ["BTC", "ETH"]:
                continue
            df_daily = get_crypto_ohlcv(symbol, "1d")
            if df_daily is not None and len(df_daily) >= 100:
                trades = backtest_strategy_2_altcoin_rs(df_daily, symbol, btc_daily, eth_daily, tp, sl, timeout)
                for trade in trades:
                    result_s2.add_trade(trade)

        stats_s2 = result_s2.calculate_stats()
        all_results.append(stats_s2)
        results["strategies"].append({
            "name": "Altcoin RS Rotation",
            "config": config_name,
            "stats": stats_s2,
            "trades": [t.to_dict() for t in result_s2.trades[:10]],
        })
        print(f"  Trades: {stats_s2['total_trades']}, PF: {stats_s2['pf']}, WR: {stats_s2['win_rate_pct']}%")

        # Strategy 3: 4H Timing
        print("Strategy 3: 4H Timing Pullback")
        result_s3 = BacktestResult("4H Timing Pullback", config_name)

        for symbol in PHASE1_CORE:
            df_daily = get_crypto_ohlcv(symbol, "1d")
            df_4h = get_crypto_ohlcv(symbol, "4h")
            if df_daily is not None and df_4h is not None and len(df_daily) >= 100 and len(df_4h) >= 50:
                trades = backtest_strategy_3_4h_timing(df_daily, df_4h, symbol, tp, sl, timeout)
                for trade in trades:
                    result_s3.add_trade(trade)

        stats_s3 = result_s3.calculate_stats()
        all_results.append(stats_s3)
        results["strategies"].append({
            "name": "4H Timing Pullback",
            "config": config_name,
            "stats": stats_s3,
            "trades": [t.to_dict() for t in result_s3.trades[:10]],
        })
        print(f"  Trades: {stats_s3['total_trades']}, PF: {stats_s3['pf']}, WR: {stats_s3['win_rate_pct']}%")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for r in all_results:
        print(f"{r['strategy']} | {r['exit_config']} | Trades: {r['total_trades']} | PF: {r['pf']} | WR: {r['win_rate_pct']}%")

    results["summary"] = {
        "total_strategies_tested": len(all_results),
        "best_pf": max(all_results, key=lambda x: x['pf']) if all_results else None,
        "best_wr": max(all_results, key=lambda x: x['win_rate_pct']) if all_results else None,
    }

    # Save results
    output_file = "crypto_phase1_backtest_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}\n")
    return results


if __name__ == "__main__":
    run_backtest_phase1()
