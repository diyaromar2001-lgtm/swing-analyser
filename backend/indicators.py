import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def perf_pct(series: pd.Series, days: int) -> float:
    if len(series) < days + 1:
        return 0.0
    return float((series.iloc[-1] / series.iloc[-days] - 1) * 100)


def new_high_30d(high: pd.Series) -> bool:
    if len(high) < 30:
        return False
    return float(high.iloc[-1]) >= float(high.iloc[-30:].max())


def volume_above_avg(volume: pd.Series, period: int = 20) -> bool:
    if len(volume) < period:
        return False
    avg = float(volume.iloc[-period:].mean())
    current = float(volume.iloc[-1])
    return current > avg * 1.2


def atr_stable(atr_series: pd.Series, period: int = 20) -> bool:
    if len(atr_series) < period:
        return False
    recent = atr_series.iloc[-period:]
    std = float(recent.std())
    mean = float(recent.mean())
    if mean == 0:
        return False
    return (std / mean) < 0.25


# ── Nouveaux indicateurs professionnels ───────────────────────────────────────

def sma_slope(series: pd.Series, period: int, lookback: int = 10) -> bool:
    """Retourne True si la SMA[period] est en pente positive sur [lookback] barres."""
    s = sma(series, period)
    if len(s) < lookback + 1:
        return False
    v_now  = float(s.iloc[-1])
    v_then = float(s.iloc[-lookback])
    if np.isnan(v_now) or np.isnan(v_then):
        return False
    return v_now > v_then


def support_level(low: pd.Series, lookback: int = 20) -> float:
    """Support récent : plus bas des [lookback] dernières bougies."""
    n = min(lookback, len(low))
    return float(low.iloc[-n:].min())


def resistance_level(high: pd.Series, lookback: int = 60) -> float:
    """Résistance récente : plus haut des [lookback] dernières bougies."""
    n = min(lookback, len(high))
    return float(high.iloc[-n:].max())


def high_52w(high: pd.Series) -> float:
    """Plus haut sur 52 semaines (~252 séances)."""
    n = min(252, len(high))
    return float(high.iloc[-n:].max())


def avg_volume_30d(volume: pd.Series) -> float:
    """Volume moyen sur 30 jours."""
    n = min(30, len(volume))
    return float(volume.iloc[-n:].mean())
