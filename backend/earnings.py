"""
Earnings — Prochaines dates de résultats financiers via yfinance.
Cache : 6h par ticker.
"""

import time
from datetime import datetime
import pandas as pd
import yfinance as yf

_cache: dict[str, dict] = {}
_CACHE_TTL = 21_600   # 6h


def get_earnings_date(ticker: str) -> dict:
    """
    Retourne la prochaine date de résultats pour un ticker.
    {
        "date":        "2025-05-01" | null,
        "days_until":  3 | null,
        "warning":     True   # si earnings dans ≤ 7 jours
    }
    """
    cached = _cache.get(ticker)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    result = {"date": None, "days_until": None, "warning": False}

    try:
        t = yf.Ticker(ticker)
        cal = t.calendar

        # yfinance retourne un DataFrame ou un dict selon la version
        if cal is None:
            pass
        elif isinstance(cal, pd.DataFrame):
            # Format DataFrame : colonnes = tickers, index = métriques
            if "Earnings Date" in cal.index:
                row = cal.loc["Earnings Date"]
                # Peut contenir plusieurs dates (range)
                dates = row.dropna().tolist() if hasattr(row, "tolist") else [row]
                if dates:
                    ed = pd.Timestamp(dates[0])
                    days_until = (ed.date() - datetime.now().date()).days
                    if days_until >= -1:   # inclure le jour même
                        result = {
                            "date":       ed.strftime("%Y-%m-%d"),
                            "days_until": days_until,
                            "warning":    0 <= days_until <= 7,
                        }
        elif isinstance(cal, dict):
            ed_raw = cal.get("Earnings Date")
            if ed_raw:
                ed = pd.Timestamp(ed_raw[0] if isinstance(ed_raw, list) else ed_raw)
                days_until = (ed.date() - datetime.now().date()).days
                if days_until >= -1:
                    result = {
                        "date":       ed.strftime("%Y-%m-%d"),
                        "days_until": days_until,
                        "warning":    0 <= days_until <= 7,
                    }
    except Exception:
        pass

    _cache[ticker] = {"ts": time.time(), "data": result}
    return result
