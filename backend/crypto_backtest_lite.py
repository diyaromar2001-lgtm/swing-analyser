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
