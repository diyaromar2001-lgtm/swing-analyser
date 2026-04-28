"""
Market Context — VIX, Market Breadth, Sector Strength.
Fournit le contexte de marché avancé pour filtrer les mauvaises conditions.
Cache : 1h.
"""

import time
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from indicators import sma, rsi, perf_pct

# ── Cache ─────────────────────────────────────────────────────────────────────
_context_cache: dict = {}
_CACHE_TTL = 3_600   # 1h

# ── ETFs sectoriels ───────────────────────────────────────────────────────────
SECTOR_ETFS: dict[str, str] = {
    "Technology":             "XLK",
    "Healthcare":             "XLV",
    "Financials":             "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples":       "XLP",
    "Energy":                 "XLE",
    "Industrials":            "XLI",
    "Real Estate":            "XLRE",
    "Utilities":              "XLU",
    "Communication":          "XLC",
    "Materials":              "XLB",
}

# Sample de tickers pour la breadth (représentatif, pas exhaustif → rapide)
BREADTH_TICKERS = [
    "AAPL","MSFT","NVDA","AMD","GOOGL","META","AMZN","TSLA","JPM","V",
    "MA","BAC","UNH","JNJ","LLY","MRK","ABBV","XOM","CVX","COP",
    "CAT","DE","HON","RTX","GE","HD","NKE","SBUX","PG","KO",
    "COST","WMT","NEE","DUK","SO","PLD","AMT","EQIX","COIN","PLTR",
    "NFLX","ADBE","CRM","AVGO","QCOM","SLB","EOG","ETN","AMAT","MU",
    "MCO","SPGI","GS","MS","AXP","BKNG","ORLY","LRCX","PANW","CRWD",
]


def _fetch_vix() -> float:
    try:
        df = yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            return round(float(df["Close"].squeeze().iloc[-1]), 1)
    except Exception:
        pass
    return 18.0


def _check_above_sma50(ticker: str) -> bool | None:
    try:
        df = yf.download(ticker, period="4mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 55:
            return None
        c   = df["Close"].squeeze()
        s50 = float(sma(c, 50).iloc[-1])
        return float(c.iloc[-1]) > s50
    except Exception:
        return None


def _fetch_breadth() -> float:
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(_check_above_sma50, BREADTH_TICKERS))
    valid = [r for r in results if r is not None]
    return round(sum(valid) / len(valid) * 100, 1) if valid else 50.0


def _fetch_sector_strength() -> dict[str, dict]:
    strength: dict[str, dict] = {}

    def _fetch_etf(item):
        sector, etf = item
        try:
            df = yf.download(etf, period="3mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty or len(df) < 25:
                return sector, None
            c = df["Close"].squeeze()
            perf_1m  = round((float(c.iloc[-1]) / float(c.iloc[-21]) - 1) * 100, 2)
            perf_3m  = round((float(c.iloc[-1]) / float(c.iloc[0])  - 1) * 100, 2)
            rsi_val  = round(float(rsi(c, 14).iloc[-1]), 1)
            return sector, {"perf_1m": perf_1m, "perf_3m": perf_3m, "rsi": rsi_val, "etf": etf}
        except Exception:
            return sector, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        for sector, data in ex.map(_fetch_etf, SECTOR_ETFS.items()):
            if data is not None:
                strength[sector] = data

    return strength


def compute_market_context() -> dict:
    """Calcule et retourne le contexte de marché complet."""
    global _context_cache
    now = time.time()

    if _context_cache and (now - _context_cache.get("ts", 0)) < _CACHE_TTL:
        return _context_cache["data"]

    # Paralléliser VIX + breadth + secteurs
    from concurrent.futures import ThreadPoolExecutor as TPE
    with TPE(max_workers=3) as ex:
        f_vix      = ex.submit(_fetch_vix)
        f_breadth  = ex.submit(_fetch_breadth)
        f_sectors  = ex.submit(_fetch_sector_strength)

    vix_val        = f_vix.result()
    breadth_pct    = f_breadth.result()
    sector_strength = f_sectors.result()

    # ── Condition globale ─────────────────────────────────────────────────────
    vix_regime = (
        "LOW"     if vix_val < 15 else
        "NORMAL"  if vix_val < 22 else
        "ELEVATED" if vix_val < 30 else
        "HIGH"    if vix_val < 40 else
        "EXTREME"
    )

    score = 0
    if vix_val < 20:        score += 40
    elif vix_val < 28:      score += 20
    if breadth_pct > 65:    score += 40
    elif breadth_pct > 50:  score += 20
    # Secteurs en tendance positive
    positive_sectors = sum(1 for s in sector_strength.values() if s.get("perf_1m", 0) > 0)
    if positive_sectors >= 7: score += 20
    elif positive_sectors >= 4: score += 10

    if score >= 70:
        condition       = "FAVORABLE"
        condition_label = "Conditions Favorables"
        condition_emoji = "🟢"
    elif score <= 30:
        condition       = "DANGEROUS"
        condition_label = "Conditions Dangereuses"
        condition_emoji = "🔴"
    else:
        condition       = "NEUTRAL"
        condition_label = "Conditions Neutres"
        condition_emoji = "🟡"

    data = {
        "vix":              vix_val,
        "vix_regime":       vix_regime,
        "market_breadth_pct": breadth_pct,
        "sector_strength":  sector_strength,
        "condition":        condition,
        "condition_label":  condition_label,
        "condition_emoji":  condition_emoji,
        "condition_score":  score,
        "positive_sectors": positive_sectors,
        "total_sectors":    len(sector_strength),
    }

    _context_cache = {"ts": now, "data": data}
    return data
