"""
Fundamental Risk Filters — couche de filtrage externe au signal technique.

Règle absolue :
  Les fondamentaux NE génèrent PAS de signaux d'achat.
  Ils BLOQUENT ou RÉDUISENT des signaux déjà positifs techniquement.

Pipeline :
  1. Earnings filter   → BLOCKED si earnings ≤ 5 jours
  2. News risk filter  → BLOCKED si news très négatives / HIGH si négatives
  3. Sector strength   → STRONG / NEUTRAL / WEAK
  4. VIX regime        → penalise quand VIX élevé
  5. Market regime     → réduit sélectivité en marché baissier

Sortie :
  {
    "risk_filters_status": "OK" | "CAUTION" | "BLOCKED",
    "risk_filter_reasons": [...],
    "fundamental_risk":    "LOW" | "MEDIUM" | "HIGH",
    "news_risk":           "LOW" | "MEDIUM" | "HIGH",
    "sector_rank":         "STRONG" | "NEUTRAL" | "WEAK",
    "vix_risk":            "LOW" | "MEDIUM" | "HIGH",
  }
"""

import time
import threading
from typing import Optional, Dict, List

# ── News risk cache ────────────────────────────────────────────────────────────
_news_cache: Dict[str, dict] = {}
_news_lock  = threading.Lock()
_NEWS_TTL   = 4 * 3600   # 4 heures — news stable sur la journée

# ── Mots-clés négatifs ─────────────────────────────────────────────────────────
_SEVERE = [
    "sec fraud", "securities fraud", "bankruptcy", "chapter 11", "chapter11",
    "delisted", "delisting", "class action", "criminal charges", "indicted",
    "accounting fraud", "restatement", "going concern",
]

_NEGATIVE = [
    "downgrade", "downgraded", "price target cut", "target cut",
    "guidance cut", "guidance lowered", "guidance reduced", "lowers guidance",
    "cuts guidance", "cuts forecast", "lowered outlook",
    "lawsuit", "sued", "litigation", "investigation", "probe", "subpoena",
    "sec investigation", "doj", "recall", "safety concern",
    "miss", "revenue miss", "earnings miss", "shortfall",
    "layoffs", "layoff", "job cuts", "workforce reduction", "restructuring",
    "warning", "profit warning", "revenue warning",
    "halted", "trading halted",
]


def _scan_headlines(headlines: List[str]) -> str:
    """Retourne 'HIGH', 'MEDIUM' ou 'LOW' selon les headlines scannées."""
    text = " ".join(h.lower() for h in headlines)

    severe_hits   = sum(1 for kw in _SEVERE    if kw in text)
    negative_hits = sum(1 for kw in _NEGATIVE  if kw in text)

    if severe_hits >= 1 or negative_hits >= 3:
        return "HIGH"
    if negative_hits >= 1:
        return "MEDIUM"
    return "LOW"


def get_news_risk(ticker: str) -> dict:
    """
    Analyse les actualités récentes d'un ticker via yfinance.
    Retourne {"risk": "LOW"|"MEDIUM"|"HIGH", "headline_count": int, "cached": bool}
    Timeout 3 s — retourne LOW en cas d'erreur (ne bloque pas le screener).
    """
    now = time.time()

    with _news_lock:
        cached = _news_cache.get(ticker)
        if cached and (now - cached["ts"]) < _NEWS_TTL:
            return {**cached["data"], "cached": True}

    try:
        import yfinance as yf
        import signal as _sig

        # Timeout via thread — yf.Ticker().news peut bloquer
        result: dict = {"risk": "LOW", "headline_count": 0}

        def _fetch():
            try:
                t_obj = yf.Ticker(ticker)
                news  = t_obj.news or []
                headlines = [
                    n.get("content", {}).get("title", "") or n.get("title", "")
                    for n in news[:15]          # 15 derniers articles max
                ]
                risk = _scan_headlines(headlines)
                result.update({"risk": risk, "headline_count": len(headlines)})
            except Exception:
                pass

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=3.0)            # 3 s max par ticker

        data = {"risk": result["risk"], "headline_count": result["headline_count"], "cached": False}

    except Exception:
        data = {"risk": "LOW", "headline_count": 0, "cached": False}

    with _news_lock:
        _news_cache[ticker] = {"ts": now, "data": {k: v for k, v in data.items() if k != "cached"}}

    return data


# ── Sector rank ────────────────────────────────────────────────────────────────

def get_sector_rank(sector: str, sector_strength: Dict[str, dict]) -> str:
    """
    STRONG  : perf_1m > +1%  ET perf_3m > +3%
    NEUTRAL : perf_1m > -1%
    WEAK    : perf_1m < -1%  OU perf_3m < -3%
    """
    if not sector_strength or sector not in sector_strength:
        return "NEUTRAL"

    s     = sector_strength[sector]
    p1m   = s.get("perf_1m", 0.0)
    p3m   = s.get("perf_3m", 0.0)
    rsi_v = s.get("rsi", 50.0)

    if p1m > 1.0 and p3m > 3.0:
        return "STRONG"
    if p1m < -1.5 or p3m < -5.0:
        return "WEAK"
    return "NEUTRAL"


# ── VIX risk ───────────────────────────────────────────────────────────────────

def get_vix_risk(vix: float) -> str:
    if vix < 18:
        return "LOW"
    if vix < 28:
        return "MEDIUM"
    return "HIGH"


# ── Composite fundamental risk ─────────────────────────────────────────────────

def compute_fundamental_risk(
    ticker:           str,
    sector:           str,
    earnings_days:    Optional[int],
    earnings_warning: bool,
    sector_strength:  Dict[str, dict],
    vix_val:          float,
    regime:           str,             # "BULL" | "RANGE" | "BEAR" | "UNKNOWN"
    fetch_news:       bool = True,
) -> dict:
    """
    Combine tous les filtres fondamentaux.

    Priorité des BLOCKED (dans l'ordre) :
      1. Earnings ≤ 5 jours
      2. News HIGH
      3. Régime BEAR + VIX HIGH (double condition bearish)

    CAUTION si :
      - Earnings 6-14 jours
      - News MEDIUM
      - Secteur WEAK
      - VIX MEDIUM (18-28)
      - Régime RANGE + VIX élevé

    OK sinon.
    """
    reasons: List[str] = []

    # ── 1. Earnings filter ────────────────────────────────────────────────────
    earnings_blocked = False
    if earnings_warning or (earnings_days is not None and 0 <= earnings_days <= 5):
        earnings_blocked = True
        days_str = f"{earnings_days}j" if earnings_days is not None else "?"
        reasons.append(f"Earnings dans {days_str} — risque de gap violent")

    earnings_caution = (
        not earnings_blocked
        and earnings_days is not None
        and 6 <= earnings_days <= 14
    )
    if earnings_caution:
        reasons.append(f"Earnings dans {earnings_days}j — réduire la taille")

    # ── 2. News risk ──────────────────────────────────────────────────────────
    if fetch_news:
        news_data = get_news_risk(ticker)
    else:
        news_data = {"risk": "LOW", "headline_count": 0, "cached": True}

    news_risk    = news_data["risk"]
    news_blocked = (news_risk == "HIGH")
    news_caution = (news_risk == "MEDIUM")

    if news_blocked:
        reasons.append("Actualités très négatives (downgrade / lawsuit / fraude)")
    elif news_caution:
        reasons.append("Actualités négatives récentes — surveiller")

    # ── 3. Sector strength ────────────────────────────────────────────────────
    sector_rank = get_sector_rank(sector, sector_strength)
    if sector_rank == "WEAK":
        reasons.append(f"Secteur {sector} faible (perf_1m négative)")

    # ── 4. VIX risk ───────────────────────────────────────────────────────────
    vix_risk = get_vix_risk(vix_val)
    if vix_risk == "HIGH":
        reasons.append(f"VIX élevé ({vix_val:.1f}) — volatilité excessive")
    elif vix_risk == "MEDIUM" and regime in ("BEAR", "RANGE"):
        reasons.append(f"VIX modéré ({vix_val:.1f}) en marché incertain")

    # ── 5. Market regime ──────────────────────────────────────────────────────
    regime_blocked = (regime == "BEAR" and vix_risk == "HIGH")
    regime_caution = (regime == "BEAR" or (regime == "RANGE" and vix_risk != "LOW"))

    if regime_blocked:
        reasons.append("Marché baissier + VIX élevé — stop tout trading")
    elif regime == "BEAR":
        reasons.append("Marché baissier (SPY < SMA200) — sélectivité maximale")
    elif regime == "RANGE" and vix_risk != "LOW":
        reasons.append("Marché en range + VIX modéré — réduire l'exposition")

    # ── Décision finale du filtre ─────────────────────────────────────────────
    is_blocked = earnings_blocked or news_blocked or regime_blocked

    n_cautions = sum([
        bool(earnings_caution),
        bool(news_caution),
        sector_rank == "WEAK",
        vix_risk == "HIGH",
        regime_caution and not regime_blocked,
    ])
    is_caution = not is_blocked and n_cautions >= 1

    if is_blocked:
        status = "BLOCKED"
    elif is_caution:
        status = "CAUTION"
    else:
        status = "OK"

    # ── Risque fondamental global ─────────────────────────────────────────────
    if is_blocked:
        fundamental_risk = "HIGH"
    elif is_caution:
        fundamental_risk = "MEDIUM"
    elif sector_rank == "STRONG" and vix_risk == "LOW" and news_risk == "LOW":
        fundamental_risk = "LOW"
    else:
        fundamental_risk = "LOW"

    return {
        "risk_filters_status":  status,            # OK | CAUTION | BLOCKED
        "risk_filter_reasons":  reasons,
        "fundamental_risk":     fundamental_risk,  # LOW | MEDIUM | HIGH
        "news_risk":            news_risk,          # LOW | MEDIUM | HIGH
        "sector_rank":          sector_rank,        # STRONG | NEUTRAL | WEAK
        "vix_risk":             vix_risk,           # LOW | MEDIUM | HIGH
    }
