"""
Scope: CRYPTO
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from crypto_data import get_crypto_ohlcv
from crypto_universe import CRYPTO_SYMBOLS
from indicators import atr, ema, macd, rsi, sma


CryptoSignalFn = Callable[[Dict[str, pd.Series], Dict[str, Any], int], bool]


def _perf(close: pd.Series, bars: int, i: int) -> float:
    if i < bars:
        return 0.0
    base = float(close.iloc[i - bars])
    if base <= 0:
        return 0.0
    return (float(close.iloc[i]) / base - 1.0) * 100.0


def _vol_ratio(volume: pd.Series, i: int, lookback: int = 20) -> float:
    if i < lookback:
        return 1.0
    avg = float(volume.iloc[i - lookback + 1: i + 1].mean())
    cur = float(volume.iloc[i])
    return cur / max(avg, 1.0)


def _sig_btc_eth_trend_breakout(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    close = series["close"]
    high = series["high"]
    s50 = series["sma50"]
    s200 = series["sma200"]
    rv = series["rsi"]
    mh = series["macd_hist"]
    e20 = series["ema20"]
    if i < 30:
        return False
    price = float(close.iloc[i])
    high20 = float(high.iloc[i - 19: i + 1].max())
    dist_e20 = (price / max(float(e20.iloc[i]), 0.0001) - 1.0) * 100.0
    return (
        price > float(s50.iloc[i]) > float(s200.iloc[i])
        and float(rv.iloc[i]) >= 54
        and float(rv.iloc[i]) <= 72
        and float(mh.iloc[i]) > 0
        and price >= high20
        and _vol_ratio(series["volume"], i) >= 1.15
        and 0 <= dist_e20 <= 8
    )


def _sig_pullback_uptrend(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    close = series["close"]
    s50 = series["sma50"]
    s200 = series["sma200"]
    e20 = series["ema20"]
    rv = series["rsi"]
    if i < 25:
        return False
    price = float(close.iloc[i])
    dist_e20 = (price / max(float(e20.iloc[i]), 0.0001) - 1.0) * 100.0
    return (
        price > float(s200.iloc[i])
        and float(s50.iloc[i]) > float(s200.iloc[i])
        and -4.5 <= dist_e20 <= 1.0
        and 40 <= float(rv.iloc[i]) <= 60
    )


def _sig_momentum_rs(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    close = series["close"]
    s50 = series["sma50"]
    s200 = series["sma200"]
    rv = series["rsi"]
    mh = series["macd_hist"]
    symbol = ctx["symbol"]
    btc_rel = ctx.get("btc_perf_30d", {}).get(symbol, 0.0)
    eth_rel = ctx.get("eth_perf_30d", {}).get(symbol, 0.0)
    p7 = _perf(close, 7, i)
    p30 = _perf(close, 30, i)
    return (
        float(close.iloc[i]) > float(s50.iloc[i]) > float(s200.iloc[i])
        and p7 > 3
        and p30 > 8
        and btc_rel > 0
        and eth_rel > 0
        and float(rv.iloc[i]) >= 52
        and float(mh.iloc[i]) > 0
        and _vol_ratio(series["volume"], i) >= 1.05
    )


def _sig_vol_compression(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    close = series["close"]
    high = series["high"]
    low = series["low"]
    atr_s = series["atr"]
    s50 = series["sma50"]
    s200 = series["sma200"]
    if i < 25:
        return False
    price = float(close.iloc[i])
    range20 = (float(high.iloc[i - 19: i + 1].max()) - float(low.iloc[i - 19: i + 1].min())) / max(price, 0.0001) * 100.0
    atr_pct = float(atr_s.iloc[i]) / max(price, 0.0001) * 100.0
    breakout = price >= float(high.iloc[i - 9: i + 1].max())
    return (
        price > float(s200.iloc[i])
        and float(s50.iloc[i]) > float(s200.iloc[i])
        and atr_pct < 6.0
        and range20 < 18.0
        and breakout
        and _vol_ratio(series["volume"], i) >= 1.2
    )


def _sig_mean_reversion(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    if ctx.get("regime") != "CRYPTO_RANGE":
        return False
    close = series["close"]
    low = series["low"]
    rv = series["rsi"]
    s200 = series["sma200"]
    if i < 20:
        return False
    price = float(close.iloc[i])
    support20 = float(low.iloc[i - 19: i + 1].min())
    dist_support = (price / max(support20, 0.0001) - 1.0) * 100.0
    return price > float(s200.iloc[i]) and dist_support <= 4.0 and float(rv.iloc[i]) <= 40


def _sig_btc_leader_rotation(series: Dict[str, pd.Series], ctx: Dict[str, Any], i: int) -> bool:
    if ctx.get("btc_dominance", 100.0) > 62.5:
        return False
    close = series["close"]
    s50 = series["sma50"]
    s200 = series["sma200"]
    rv = series["rsi"]
    symbol = ctx["symbol"]
    btc_rel = ctx.get("btc_perf_30d", {}).get(symbol, 0.0)
    return (
        float(close.iloc[i]) > float(s200.iloc[i])
        and float(s50.iloc[i]) > float(s200.iloc[i])
        and btc_rel > 4.0
        and 48 <= float(rv.iloc[i]) <= 68
        and _vol_ratio(series["volume"], i) >= 1.0
    )


CRYPTO_LAB_STRATEGIES: List[Dict[str, Any]] = [
    {
        "key": "btc_eth_trend_breakout",
        "name": "BTC/ETH Trend Breakout",
        "description": "Breakout confirmé dans un contexte crypto haussier.",
        "color": "#f59e0b",
        "emoji": "🚀",
        "tp_pct": 0.14,
        "sl_pct": 0.06,
        "timeout_bars": 28,
        "signal_filter": "Breakout",
        "regimes": ["CRYPTO_BULL", "CRYPTO_PULLBACK"],
        "fn": _sig_btc_eth_trend_breakout,
    },
    {
        "key": "pullback_uptrend",
        "name": "Pullback in Crypto Uptrend",
        "description": "Retour vers EMA20/SMA50 dans un uptrend sain.",
        "color": "#818cf8",
        "emoji": "📉",
        "tp_pct": 0.12,
        "sl_pct": 0.05,
        "timeout_bars": 24,
        "signal_filter": "Pullback",
        "regimes": ["CRYPTO_BULL", "CRYPTO_PULLBACK"],
        "fn": _sig_pullback_uptrend,
    },
    {
        "key": "momentum_relative_strength",
        "name": "Momentum Relative Strength",
        "description": "Surperformance vs BTC/ETH avec momentum 7j/30j.",
        "color": "#4ade80",
        "emoji": "⚡",
        "tp_pct": 0.16,
        "sl_pct": 0.07,
        "timeout_bars": 24,
        "signal_filter": "Momentum",
        "regimes": ["CRYPTO_BULL"],
        "fn": _sig_momentum_rs,
    },
    {
        "key": "volatility_compression_breakout",
        "name": "Volatility Compression Breakout",
        "description": "Compression puis expansion avec volume.",
        "color": "#22d3ee",
        "emoji": "🧊",
        "tp_pct": 0.13,
        "sl_pct": 0.055,
        "timeout_bars": 20,
        "signal_filter": "Breakout",
        "regimes": ["CRYPTO_BULL", "CRYPTO_RANGE"],
        "fn": _sig_vol_compression,
    },
    {
        "key": "mean_reversion_range",
        "name": "Mean Reversion in Range",
        "description": "Rebond technique proche support, uniquement en range.",
        "color": "#f87171",
        "emoji": "🔄",
        "tp_pct": 0.08,
        "sl_pct": 0.04,
        "timeout_bars": 12,
        "signal_filter": "Mean Reversion",
        "regimes": ["CRYPTO_RANGE"],
        "fn": _sig_mean_reversion,
    },
    {
        "key": "btc_leader_rotation",
        "name": "BTC Leader Rotation",
        "description": "Altcoins qui commencent à surperformer quand BTC mène.",
        "color": "#a78bfa",
        "emoji": "🧭",
        "tp_pct": 0.15,
        "sl_pct": 0.065,
        "timeout_bars": 20,
        "signal_filter": "Momentum",
        "regimes": ["CRYPTO_BULL", "CRYPTO_PULLBACK"],
        "fn": _sig_btc_leader_rotation,
    },
]


def build_context_maps(period_months: int = 24) -> Dict[str, Any]:
    period_bars = 365 if period_months >= 12 else 180
    btc = get_crypto_ohlcv("BTC", "1d")
    eth = get_crypto_ohlcv("ETH", "1d")
    btc_perf_30d: Dict[str, float] = {}
    eth_perf_30d: Dict[str, float] = {}
    closes: Dict[str, pd.Series] = {}
    for symbol in CRYPTO_SYMBOLS:
        df = get_crypto_ohlcv(symbol, "1d")
        if df is None or len(df) < max(220, period_bars):
            continue
        closes[symbol] = df["Close"]
    if btc is not None and len(btc) >= 31 and eth is not None and len(eth) >= 31:
        btc_ret = (float(btc["Close"].iloc[-1]) / float(btc["Close"].iloc[-31]) - 1.0) * 100.0
        eth_ret = (float(eth["Close"].iloc[-1]) / float(eth["Close"].iloc[-31]) - 1.0) * 100.0
        for symbol, close in closes.items():
            price = float(close.iloc[-1])
            perf30 = (price / float(close.iloc[-31]) - 1.0) * 100.0
            btc_perf_30d[symbol] = round(perf30 - btc_ret, 2)
            eth_perf_30d[symbol] = round(perf30 - eth_ret, 2)
    return {
        "btc_perf_30d": btc_perf_30d,
        "eth_perf_30d": eth_perf_30d,
    }


def _prepare_series(df: pd.DataFrame) -> Dict[str, pd.Series]:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    _, _, macd_hist = macd(close)
    return {
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
        "sma50": sma(close, 50),
        "sma200": sma(close, 200),
        "ema20": ema(close, 20),
        "rsi": rsi(close, 14),
        "macd_hist": macd_hist,
        "atr": atr(high, low, close, 14),
    }


def backtest_crypto_strategy(
    symbol: str,
    df: pd.DataFrame,
    strategy_def: Dict[str, Any],
    regime: str,
    ctx_maps: Dict[str, Any],
    period_months: int = 12,
) -> List[Dict[str, Any]]:
    series = _prepare_series(df)
    n = len(df)
    start = max(200, n - (730 if period_months >= 24 else 365))
    fn: CryptoSignalFn = strategy_def["fn"]
    tp_pct = float(strategy_def["tp_pct"])
    sl_pct = float(strategy_def["sl_pct"])
    timeout_bars = int(strategy_def.get("timeout_bars", 20))

    trades: List[Dict[str, Any]] = []
    in_trade = False
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0

    ctx = {**ctx_maps, "symbol": symbol, "regime": regime}

    for i in range(start, n - 1):
        values = [
            series["sma50"].iloc[i], series["sma200"].iloc[i], series["ema20"].iloc[i],
            series["rsi"].iloc[i], series["macd_hist"].iloc[i], series["atr"].iloc[i],
        ]
        if any(pd.isna(v) for v in values):
            continue

        if in_trade:
            tp = entry_price * (1.0 + tp_pct)
            sl = entry_price * (1.0 - sl_pct)
            day_high = float(series["high"].iloc[i])
            day_low = float(series["low"].iloc[i])
            exit_price: Optional[float] = None
            exit_reason: Optional[str] = None
            if day_high >= tp and day_low <= sl:
                exit_price, exit_reason = sl, "SL"
            elif day_high >= tp:
                exit_price, exit_reason = tp, "TP"
            elif day_low <= sl:
                exit_price, exit_reason = sl, "SL"
            elif i - entry_idx >= timeout_bars:
                exit_price, exit_reason = float(series["close"].iloc[i]), "TIMEOUT"
            if exit_price is not None and exit_reason is not None:
                pnl = (exit_price / entry_price - 1.0) * 100.0
                trades.append(
                    {
                        "ticker": symbol,
                        "entry_date": entry_date,
                        "exit_date": str(series["close"].index[i])[:10],
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "exit_reason": exit_reason,
                        "pnl_pct": round(pnl, 2),
                        "duration_days": i - entry_idx,
                    }
                )
                in_trade = False
            continue

        if regime not in strategy_def.get("regimes", []):
            continue
        if fn(series, ctx, i):
            entry_price = float(series["close"].iloc[i + 1])
            entry_date = str(series["close"].index[i + 1])[:10]
            entry_idx = i + 1
            in_trade = True

    return trades


def _metrics(trades: List[Dict[str, Any]], period_months: int) -> Dict[str, float]:
    closed = [t for t in trades if t.get("exit_reason") != "OPEN"]
    if not closed:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "cagr_pct": 0.0,
            "total_return_pct": 0.0,
            "avg_duration_days": 0.0,
            "final_capital": 10_000.0,
            "equity_curve": [10_000.0],
        }

    pnls = [float(t["pnl_pct"]) for t in closed]
    wins = [v for v in pnls if v > 0]
    losses = [v for v in pnls if v <= 0]

    equity = 10_000.0
    curve = [equity]
    peak = equity
    max_dd = 0.0
    returns = []
    for pnl in pnls:
        returns.append(pnl / 100.0)
        equity *= (1.0 + pnl / 100.0)
        curve.append(equity)
        peak = max(peak, equity)
        dd = (peak - equity) / max(peak, 1.0) * 100.0
        max_dd = max(max_dd, dd)

    profit_factor = sum(wins) / max(abs(sum(losses)), 0.001) if wins or losses else 0.0
    win_rate = len(wins) / len(closed) * 100.0
    expectancy = float(np.mean(pnls))
    std = float(np.std(returns)) if len(returns) > 1 else 0.0
    sharpe = (float(np.mean(returns)) / std * np.sqrt(12)) if std > 0 else 0.0
    years = max(period_months / 12.0, 1 / 12.0)
    cagr = ((equity / 10_000.0) ** (1.0 / years) - 1.0) * 100.0 if equity > 0 else -100.0
    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown_pct": round(-max_dd, 1),
        "sharpe_ratio": round(sharpe, 2),
        "cagr_pct": round(cagr, 1),
        "total_return_pct": round((equity / 10_000.0 - 1.0) * 100.0, 1),
        "avg_duration_days": round(float(np.mean([t["duration_days"] for t in closed])), 1),
        "final_capital": round(equity, 2),
        "equity_curve": [round(v, 2) for v in curve],
    }


def evaluate_crypto_strategy_for_symbol(
    symbol: str,
    strategy_def: Dict[str, Any],
    period_months: int = 24,
    regime: str = "CRYPTO_BULL",
    ctx_maps: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    df = get_crypto_ohlcv(symbol, "1d")
    if df is None or len(df) < 220:
        return {
            "key": strategy_def["key"],
            "name": strategy_def["name"],
            "description": strategy_def["description"],
            "color": strategy_def["color"],
            "emoji": strategy_def["emoji"],
            "screener_signal": strategy_def["signal_filter"],
            "period_months": period_months,
            "error": "Données insuffisantes",
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "cagr_pct": 0.0,
            "avg_duration_days": 0.0,
            "final_capital": 10_000.0,
            "train_pf": 0.0,
            "test_pf": 0.0,
            "degradation_train_test": 0.0,
            "overfit_warning": False,
            "overfit_warnings": ["Données insuffisantes"],
            "trades": [],
        }

    ctx_maps = ctx_maps or build_context_maps(period_months)
    trades = backtest_crypto_strategy(symbol, df, strategy_def, regime, ctx_maps, period_months)
    closed = [t for t in trades if t.get("exit_reason") != "OPEN"]
    split = max(1, int(len(closed) * 0.75)) if closed else 1
    train = closed[:split]
    test = closed[split:]
    overall_m = _metrics(closed, period_months)
    train_m = _metrics(train, period_months)
    test_m = _metrics(test, period_months)
    degradation = round(((train_m["profit_factor"] - test_m["profit_factor"]) / max(train_m["profit_factor"], 0.01)) * 100.0, 1) if train_m["profit_factor"] else 0.0
    overfit_reasons: List[str] = []
    overfit = False
    if overall_m["total_trades"] < 12:
        overfit_reasons.append(f"Seulement {overall_m['total_trades']} trades")
    if train_m["profit_factor"] > 1.5 and test_m["profit_factor"] < 1.0 and test_m["total_trades"] > 0:
        overfit = True
        overfit_reasons.append("Train solide mais test fragile")
    if degradation > 35:
        overfit = True
        overfit_reasons.append(f"Dégradation train/test {degradation:.1f}%")

    score = round(
        min(25, overall_m["profit_factor"] * 12)
        + min(20, max(overall_m["expectancy"], 0) * 6)
        + min(15, overall_m["win_rate"] * 0.25)
        + min(15, max(0, 20 + overall_m["max_drawdown_pct"]) * 0.75)
        + min(15, overall_m["total_trades"] * 0.5)
        + min(10, max(test_m["profit_factor"], 0) * 6),
        100,
    )

    return {
        "key": strategy_def["key"],
        "name": strategy_def["name"],
        "description": strategy_def["description"],
        "color": strategy_def["color"],
        "emoji": strategy_def["emoji"],
        "screener_signal": strategy_def["signal_filter"],
        "period_months": period_months,
        "score": round(score, 1),
        **overall_m,
        "train_pf": train_m["profit_factor"],
        "test_pf": test_m["profit_factor"],
        "train_expectancy": train_m["expectancy"],
        "test_expectancy": test_m["expectancy"],
        "degradation_train_test": degradation,
        "overfit_warning": overfit,
        "overfit_warnings": overfit_reasons,
        "trades": closed,
    }


def compute_crypto_strategy_lab(period_months: int = 12) -> Dict[str, Any]:
    ctx_maps = build_context_maps(max(period_months, 24))
    strategies: List[Dict[str, Any]] = []
    for strategy_def in CRYPTO_LAB_STRATEGIES:
        per_symbol_results = []
        all_trades: List[Dict[str, Any]] = []
        for symbol in CRYPTO_SYMBOLS:
            result = evaluate_crypto_strategy_for_symbol(
                symbol,
                strategy_def,
                period_months=period_months,
                regime="CRYPTO_BULL",
                ctx_maps=ctx_maps,
            )
            if result["total_trades"] > 0:
                per_symbol_results.append(result)
                all_trades.extend(result["trades"])
        aggregate = _metrics(all_trades, period_months)
        avg_train_pf = round(float(np.mean([r["train_pf"] for r in per_symbol_results])), 2) if per_symbol_results else 0.0
        avg_test_pf = round(float(np.mean([r["test_pf"] for r in per_symbol_results])), 2) if per_symbol_results else 0.0
        avg_deg = round(float(np.mean([r["degradation_train_test"] for r in per_symbol_results])), 1) if per_symbol_results else 0.0
        overfits = [r for r in per_symbol_results if r["overfit_warning"]]
        tradable = (
            aggregate["total_trades"] >= 20
            and aggregate["profit_factor"] >= 1.15
            and avg_test_pf >= 1.0
            and aggregate["max_drawdown_pct"] >= -35
        )
        confirmed = (
            aggregate["total_trades"] >= 12
            and aggregate["profit_factor"] >= 1.0
        )
        score = round(
            min(30, aggregate["profit_factor"] * 14)
            + min(20, max(aggregate["expectancy"], 0) * 7)
            + min(15, aggregate["win_rate"] * 0.22)
            + min(15, max(0, 25 + aggregate["max_drawdown_pct"]) * 0.6)
            + min(10, aggregate["total_trades"] * 0.25)
            + min(10, avg_test_pf * 8),
            100,
        )
        strategies.append(
            {
                "key": strategy_def["key"],
                "name": strategy_def["name"],
                "description": strategy_def["description"],
                "color": strategy_def["color"],
                "emoji": strategy_def["emoji"],
                "screener_strategy": "standard",
                "screener_signal": strategy_def["signal_filter"],
                "period_months": period_months,
                "score": round(score, 1),
                **aggregate,
                "train_pf": avg_train_pf,
                "test_pf": avg_test_pf,
                "degradation_train_test": avg_deg,
                "overfitting_risk": len(overfits) > max(1, len(per_symbol_results) // 2),
                "overfitting_reasons": sorted({reason for row in overfits for reason in row["overfit_warnings"]}),
                "tradable_status": "TRADABLE" if tradable else ("À CONFIRMER" if confirmed else "NON TRADABLE"),
                "tradable_color": "#4ade80" if tradable else ("#f59e0b" if confirmed else "#ef4444"),
                "tradable_emoji": "✅" if tradable else ("⚠️" if confirmed else "⛔"),
                "eligible": aggregate["total_trades"] >= 12,
                "reliable_tickers": len(per_symbol_results),
                "per_symbol": per_symbol_results,
                "equity_curve": aggregate["equity_curve"],
            }
        )

    strategies.sort(key=lambda row: row["score"], reverse=True)
    keys = [row["key"] for row in strategies]
    return {
        "strategies": strategies,
        "best_overall": keys[0] if keys else "—",
        "best_win_rate": max(strategies, key=lambda row: row["win_rate"])["key"] if strategies else "—",
        "best_expectancy": max(strategies, key=lambda row: row["expectancy"])["key"] if strategies else "—",
        "best_pf": max(strategies, key=lambda row: row["profit_factor"])["key"] if strategies else "—",
        "best_low_dd": max(strategies, key=lambda row: row["max_drawdown_pct"])["key"] if strategies else "—",
        "has_robust_strategy": any(row["tradable_status"] == "TRADABLE" for row in strategies),
        "tradable_count": sum(1 for row in strategies if row["tradable_status"] == "TRADABLE"),
        "confirmed_count": sum(1 for row in strategies if row["tradable_status"] == "À CONFIRMER"),
        "period_months": period_months,
    }
