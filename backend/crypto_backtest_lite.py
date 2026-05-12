"""
Phase 3B.1: Backtest Preview Ultra-Léger pour Crypto Scalp

Simulation historique basée sur données Binance 5m (Crypto Scalp standard).
Aucune exécution réelle, aucun Real trading, aucun levier.
Simulation only.

IMPORTANT: This is Phase 3B.1 only. No Phase 3B.2, no 30/60/90j, no Kelly, no sizing.
"""

import pandas as pd
import numpy as np
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def fetch_ohlcv_lite(symbol: str, days: int = 7) -> Tuple[Optional[pd.DataFrame], int, float]:
    """
    Récupérer candles OHLCV en timeframe 5m via Binance (même source que Crypto Scalp).

    Returns:
        Tuple: (DataFrame with OHLCV data, candles_count, effective_period_days)
               Returns (None, 0, 0) if failed
    """
    try:
        # Utiliser la même source que Crypto Scalp : get_crypto_ohlcv_intraday()
        from crypto_data import get_crypto_ohlcv_intraday

        df = get_crypto_ohlcv_intraday(symbol, interval="5m", allow_download=True)

        if df is None or len(df) == 0:
            logger.warning(f"[BACKTEST] No intraday data for {symbol}")
            return None, 0, 0.0

        # Calculer la période effective couverte par les candles
        candles_count = len(df)
        # 5m * candles / (24h * 60 min) = période en jours
        effective_period_days = (candles_count * 5) / (24 * 60)

        logger.info(f"[BACKTEST] {symbol}: {candles_count} candles (~{effective_period_days:.1f} days)")

        return df, candles_count, effective_period_days

    except Exception as e:
        logger.error(f"[BACKTEST] Failed to fetch data for {symbol}: {str(e)}")
        return None, 0, 0.0


def compute_long_score_lite(df_history: pd.DataFrame) -> float:
    """
    Calcul simplifié du score LONG basé sur dernières candles.
    Version ultra-légère pour backtest.
    """
    if len(df_history) < 5:
        return 0.0

    recent = df_history.tail(5)
    closes = recent["Close"].values

    # Score simple: trend up = score élevé
    price_diff = (closes[-1] - closes[0]) / closes[0] * 100
    momentum = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])

    # Score 0-100
    score = min(100, max(0, 50 + price_diff * 5 + momentum * 10))

    return float(score)


def compute_short_score_lite(df_history: pd.DataFrame) -> float:
    """
    Calcul simplifié du score SHORT basé sur dernières candles.
    Version ultra-légère pour backtest.
    """
    if len(df_history) < 5:
        return 0.0

    recent = df_history.tail(5)
    closes = recent["Close"].values

    # Score simple: trend down = score élevé
    price_diff = (closes[0] - closes[-1]) / closes[0] * 100
    momentum = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])

    # Score 0-100
    score = min(100, max(0, 50 + price_diff * 5 + momentum * 10))

    return float(score)


def determine_side_lite(long_score: float, short_score: float) -> str:
    """
    Déterminer LONG / SHORT / NONE avec règles simples.
    Même logique que Crypto Scalp.
    """
    if long_score >= 50 and long_score >= short_score + 10:
        return "LONG"
    elif short_score >= 50 and short_score >= long_score + 10:
        return "SHORT"
    else:
        return "NONE"


def backtest_crypto_scalp_lite(
    symbol: str,
    days: int = 7,
    max_candles_per_trade: int = 50
) -> Dict[str, Any]:
    """
    Backtest ultra-léger Crypto Scalp.

    Utilise get_crypto_ohlcv_intraday() pour données Binance 5m.
    Objectif: Valider architecture, pas produire un backtest parfait.

    Parameters:
        symbol: Crypto symbol (e.g., "BTC")
        days: Fixe à 7 pour Phase 3B.1 (mais retourne effective_period_days réel)
        max_candles_per_trade: Limiter recherche TP/SL à 50 candles

    Returns:
        {
            "symbol": "BTC",
            "requested_period_days": 7,
            "effective_period_days": 1.04,
            "candles_used": 300,
            "timeframe": "5m",
            "signals_detected": 5,
            "win_count": 3,
            "loss_count": 1,
            "expired_count": 1,
            "win_rate": 60.0,
            "loss_rate": 20.0,
            "avg_r": 0.5,
            "tp_touched": 3,
            "sl_touched": 1,
            "expired": 1,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
            "no_execution": True,
            "simulation_only": True,
            "timestamp": 1715421234000
        }

    IMPORTANT: Simulation ONLY. No real trading, no execution, no Real buttons.
    """

    start_time = time.time()

    try:
        # Valider days
        if days != 7:
            return {
                "error": f"Phase 3B.1 supports only 7 days. Got {days}.",
                "simulation_only": True
            }

        # Récupérer données (utilise Binance via get_crypto_ohlcv_intraday)
        logger.info(f"[BACKTEST] Fetching {symbol} intraday 5m...")
        df, candles_count, effective_period_days = fetch_ohlcv_lite(symbol, days=days)

        if df is None or len(df) < 50:
            return {
                "error": f"Insufficient data for {symbol}",
                "symbol": symbol,
                "requested_period_days": days,
                "effective_period_days": effective_period_days,
                "candles_used": candles_count,
                "signals_detected": 0,
                "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
                "simulation_only": True,
                "no_execution": True
            }

        df_len = len(df)
        logger.info(f"[BACKTEST] {symbol}: {df_len} candles (~{effective_period_days:.1f} days)")

        # Détecter signaux
        trades = []

        for i in range(20, len(df) - max_candles_per_trade):
            df_history = df.iloc[max(0, i-20):i]
            row = df.iloc[i]
            df_future = df.iloc[i:min(len(df), i + max_candles_per_trade)]

            # Calculs scores
            long_score = compute_long_score_lite(df_history)
            short_score = compute_short_score_lite(df_history)
            side = determine_side_lite(long_score, short_score)

            if side == "NONE":
                continue  # Pas de signal clair

            # Calculer TP/SL (simplifié comme Crypto Scalp)
            high_10 = df_history["High"].max()
            low_10 = df_history["Low"].min()
            atr = (high_10 - low_10) / 2

            if atr < 0.001:  # Éviter division par zéro
                continue

            entry = float(row["Close"])

            if side == "LONG":
                stop_loss = low_10 - atr
                tp = entry + atr  # Simplifié: TP = Entry + ATR (pas TP1/TP2)
            else:  # SHORT
                stop_loss = high_10 + atr
                tp = entry - atr

            # Simuler TP/SL
            result = None
            exit_price = None
            exit_candle = None

            for j, (idx, future_row) in enumerate(df_future.iterrows()):
                if side == "LONG":
                    if future_row["High"] >= tp:
                        result = "TP"
                        exit_price = tp
                        exit_candle = j
                        break
                    elif future_row["Low"] <= stop_loss:
                        result = "SL"
                        exit_price = stop_loss
                        exit_candle = j
                        break
                else:  # SHORT
                    if future_row["Low"] <= tp:
                        result = "TP"
                        exit_price = tp
                        exit_candle = j
                        break
                    elif future_row["High"] >= stop_loss:
                        result = "SL"
                        exit_price = stop_loss
                        exit_candle = j
                        break

            if result is None:
                result = "EXPIRED"
                exit_price = df_future.iloc[-1]["Close"]
                exit_candle = len(df_future) - 1

            # Calculer R
            risk = abs(entry - stop_loss)
            if result == "TP":
                reward = abs(tp - entry)
            elif result == "SL":
                reward = -risk
            else:
                reward = 0

            r_value = reward / risk if risk > 0 else 0

            trade = {
                "entry": entry,
                "stop_loss": stop_loss,
                "tp": tp,
                "side": side,
                "result": result,
                "exit_price": exit_price,
                "exit_candle": exit_candle,
                "r_value": r_value
            }
            trades.append(trade)

        # Calculer stats
        wins = [t for t in trades if t["result"] == "TP"]
        losses = [t for t in trades if t["result"] == "SL"]
        expires = [t for t in trades if t["result"] == "EXPIRED"]

        win_count = len(wins)
        loss_count = len(losses)
        expired_count = len(expires)
        total = len(trades)

        win_rate = (win_count / total * 100) if total > 0 else 0
        loss_rate = (loss_count / total * 100) if total > 0 else 0

        avg_r = (sum(t["r_value"] for t in trades) / total) if total > 0 else 0

        elapsed = time.time() - start_time
        logger.info(f"[BACKTEST] {symbol}: {total} trades in {elapsed:.2f}s, "
                   f"WR={win_rate:.1f}%, Avg R={avg_r:.2f}")

        # Réponse
        return {
            "symbol": symbol,
            "requested_period_days": days,
            "effective_period_days": round(effective_period_days, 2),
            "candles_used": df_len,
            "timeframe": "5m",
            "data_source": "Binance (via Crypto Scalp standard)",
            "signals_detected": total,
            "win_count": win_count,
            "loss_count": loss_count,
            "expired_count": expired_count,
            "win_rate": round(win_rate, 1),
            "loss_rate": round(loss_rate, 1),
            "avg_r": round(avg_r, 2),
            "tp_touched": win_count,
            "sl_touched": loss_count,
            "expired": expired_count,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
            "no_execution": True,
            "simulation_only": True,
            "timestamp": int(time.time() * 1000)
        }

    except Exception as e:
        logger.error(f"[BACKTEST] Exception for {symbol}: {str(e)}")
        return {
            "error": f"Backtest failed: {str(e)}",
            "symbol": symbol,
            "requested_period_days": days,
            "effective_period_days": 0,
            "candles_used": 0,
            "signals_detected": 0,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
            "simulation_only": True,
            "no_execution": True
        }


def backtest_crypto_scalp_extended(
    symbol: str,
    days: int = 7,
    max_candles_per_trade: int = 50
) -> Dict[str, Any]:
    """
    Phase 3B.2a: Extended Backtest Preview with trade-by-trade details (7 days only).

    Uses get_crypto_ohlcv_extended() for paginated 7-day Binance 5m data.
    Returns: symbol, period coverage, trades array (max 20 latest), summary stats.

    Parameters:
        symbol: Crypto symbol (e.g., "BTC")
        days: Fixed to 7 for Phase 3B.2a
        max_candles_per_trade: Limit TP/SL search to 50 candles

    Returns:
        Dict with trades[], summary stats, metadata
        Always includes: simulation_only=true, no_execution=true, disclaimer

    IMPORTANT: Simulation ONLY. Paper trading mode. No real execution.
    """

    start_time = time.time()

    try:
        # Validate days (Phase 3B.2a constraint: 7 days ONLY)
        if days != 7:
            return {
                "error": f"Phase 3B.2a supports only 7 days. Got {days}. (14/30 coming in Phase 3B.2b)",
                "simulation_only": True,
                "no_execution": True,
                "disclaimer": "Historical simulation only. Not a prediction. No real execution."
            }

        # Fetch extended data (7 days with pagination)
        logger.info(f"[EXTENDED_BACKTEST] Fetching {symbol} extended 5m (7 days)...")
        from crypto_data import get_crypto_ohlcv_extended

        df, candles_count, effective_period_days, metadata = get_crypto_ohlcv_extended(symbol, interval="5m", days=7)

        if df is None or len(df) < 50:
            # Proper error response with provider diagnostics
            error_msg = "Extended backtest unavailable"
            if metadata.get("provider_errors"):
                error_msg += f": providers failed (see provider_errors)"
            else:
                error_msg += f": insufficient data ({candles_count} candles)"

            return {
                "error": error_msg,
                "symbol": symbol,
                "requested_period_days": days,
                "effective_period_days": effective_period_days,
                "candles_used": candles_count,
                "data_source": metadata.get("data_source"),
                "provider_attempts": metadata.get("provider_attempts", []),
                "provider_errors": metadata.get("provider_errors", {}),
                "trades_count": 0,
                "trades": [],
                "win_count": 0,
                "loss_count": 0,
                "expired_count": 0,
                "win_rate": 0,
                "loss_rate": 0,
                "avg_r": 0,
                "best_trade_r": 0,
                "worst_trade_r": 0,
                "tp_touched": 0,
                "sl_touched": 0,
                "expired": 0,
                "incomplete": True,
                "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
                "simulation_only": True,
                "no_execution": True
            }

        df_len = len(df)
        logger.info(f"[EXTENDED_BACKTEST] {symbol}: {df_len} candles (~{effective_period_days:.2f} days)")

        # Detect trades with detailed logging
        trades = []

        for i in range(20, len(df) - max_candles_per_trade):
            df_history = df.iloc[max(0, i-20):i]
            row = df.iloc[i]
            df_future = df.iloc[i:min(len(df), i + max_candles_per_trade)]

            # Score calculations
            long_score = compute_long_score_lite(df_history)
            short_score = compute_short_score_lite(df_history)
            side = determine_side_lite(long_score, short_score)

            if side == "NONE":
                continue

            # Calculate TP/SL
            high_10 = df_history["High"].max()
            low_10 = df_history["Low"].min()
            atr = (high_10 - low_10) / 2

            if atr < 0.001:
                continue

            entry = float(row["Close"])
            entry_time = row.name.isoformat() + "Z"  # Entry time from index

            if side == "LONG":
                stop_loss = low_10 - atr
                tp = entry + atr
            else:  # SHORT
                stop_loss = high_10 + atr
                tp = entry - atr

            # Simulate TP/SL exit
            result = None
            exit_price = None
            exit_candle = None
            exit_time = None

            for j, (idx, future_row) in enumerate(df_future.iterrows()):
                if side == "LONG":
                    if future_row["High"] >= tp:
                        result = "TP"
                        exit_price = tp
                        exit_candle = j
                        exit_time = idx.isoformat() + "Z"
                        break
                    elif future_row["Low"] <= stop_loss:
                        result = "SL"
                        exit_price = stop_loss
                        exit_candle = j
                        exit_time = idx.isoformat() + "Z"
                        break
                else:  # SHORT
                    if future_row["Low"] <= tp:
                        result = "TP"
                        exit_price = tp
                        exit_candle = j
                        exit_time = idx.isoformat() + "Z"
                        break
                    elif future_row["High"] >= stop_loss:
                        result = "SL"
                        exit_price = stop_loss
                        exit_candle = j
                        exit_time = idx.isoformat() + "Z"
                        break

            if result is None:
                result = "EXPIRED"
                exit_price = df_future.iloc[-1]["Close"]
                exit_candle = len(df_future) - 1
                exit_time = df_future.index[-1].isoformat() + "Z"

            # Calculate R value
            risk = abs(entry - stop_loss)
            if result == "TP":
                reward = abs(tp - entry)
            elif result == "SL":
                reward = -risk
            else:
                reward = 0

            r_value = reward / risk if risk > 0 else 0

            # Calculate PnL %
            pnl_pct = (exit_price - entry) / entry

            # Create trade object
            trade = {
                "entry_time": entry_time,
                "exit_time": exit_time,
                "side": side,
                "entry_price": round(float(entry), 2),
                "exit_price": round(float(exit_price), 2),
                "exit_reason": result,
                "r_value": round(r_value, 2),
                "pnl_pct": round(pnl_pct, 4),
                "candles_held": exit_candle
            }
            trades.append(trade)

        # Calculate summary stats
        wins = [t for t in trades if t["exit_reason"] == "TP"]
        losses = [t for t in trades if t["exit_reason"] == "SL"]
        expires = [t for t in trades if t["exit_reason"] == "EXPIRED"]

        win_count = len(wins)
        loss_count = len(losses)
        expired_count = len(expires)
        total = len(trades)

        win_rate = (win_count / total * 100) if total > 0 else 0
        loss_rate = (loss_count / total * 100) if total > 0 else 0
        avg_r = (sum(t["r_value"] for t in trades) / total) if total > 0 else 0

        # Best and worst trade R values
        all_r_values = [t["r_value"] for t in trades]
        best_trade_r = max(all_r_values) if all_r_values else 0
        worst_trade_r = min(all_r_values) if all_r_values else 0

        elapsed = time.time() - start_time
        logger.info(f"[EXTENDED_BACKTEST] {symbol}: {total} trades in {elapsed:.2f}s, "
                   f"WR={win_rate:.1f}%, Avg R={avg_r:.2f}")

        # Limit trades to 20 latest trades max for response
        trades_to_return = trades[-20:] if len(trades) > 20 else trades

        # Response
        return {
            "symbol": symbol,
            "requested_period_days": days,
            "effective_period_days": round(effective_period_days, 2),
            "candles_used": df_len,
            "data_source": metadata.get("data_source", "unknown"),
            "provider_attempts": metadata.get("provider_attempts", []),
            "trades_count": total,
            "win_count": win_count,
            "loss_count": loss_count,
            "expired_count": expired_count,
            "win_rate": round(win_rate, 1),
            "loss_rate": round(loss_rate, 1),
            "avg_r": round(avg_r, 2),
            "best_trade_r": round(best_trade_r, 2),
            "worst_trade_r": round(worst_trade_r, 2),
            "tp_touched": win_count,
            "sl_touched": loss_count,
            "expired": expired_count,
            "trades": trades_to_return,
            "incomplete": False,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
            "no_execution": True,
            "simulation_only": True,
            "timestamp": int(time.time() * 1000)
        }

    except Exception as e:
        logger.error(f"[EXTENDED_BACKTEST] Exception for {symbol}: {str(e)}")
        return {
            "error": f"Extended backtest failed: {str(e)}",
            "symbol": symbol,
            "requested_period_days": days,
            "effective_period_days": 0,
            "candles_used": 0,
            "trades_count": 0,
            "trades": [],
            "win_count": 0,
            "loss_count": 0,
            "expired_count": 0,
            "win_rate": 0,
            "loss_rate": 0,
            "avg_r": 0,
            "best_trade_r": 0,
            "worst_trade_r": 0,
            "tp_touched": 0,
            "sl_touched": 0,
            "expired": 0,
            "incomplete": True,
            "disclaimer": "Historical simulation only. Not a prediction. No real execution.",
            "simulation_only": True,
            "no_execution": True
        }
