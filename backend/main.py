from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import time as _time

# Chargement .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd
import numpy as np
from typing import List, Optional, Dict
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed

from indicators import (
    sma, rsi, macd, atr, perf_pct,
    new_high_30d, volume_above_avg, atr_stable,
    avg_volume_30d, high_52w as _high_52w, support_level,
)
from backtest import run_backtest, BacktestResult
from strategy import (
    hard_filter, compute_dynamic_levels, compute_professional_score,
    classify_setup, compute_confidence, detect_signal_type,
    compute_quality_score, compute_final_decision,
    grade_to_category, grade_to_position,
    # rétrocompat
    classify_standard, classify_conservative,
    detect_buy_signal_standard, detect_buy_signal_conservative,
)
from fundamental_filters import compute_fundamental_risk
from tickers import ALL_TICKERS, TICKER_SECTOR, TICKERS
from strategy_lab import LAB_STRATEGIES, backtest_ticker_lab, aggregate_lab_result
from sentiment import get_sentiment
from optimizer import run_optimizer
from signal_tracker import (
    log_signal, update_outcomes, update_outcomes_ohlc,
    get_signals, get_signal_stats,
)
from portfolio_backtest import run_portfolio_backtest
from market_context import compute_market_context
from earnings import get_earnings_date
from setup_validator import validate_setup
from market_regime_engine import compute_regime_engine

app = FastAPI(title="Swing Trading Screener Pro")

import os as _os
_FRONTEND_URL = _os.environ.get("FRONTEND_URL", "http://localhost:3000")
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    _FRONTEND_URL,
    # Vercel preview URLs
    "https://*.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check (keep-alive pour Railway) ───────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── Market Status (ouvert / fermé) ────────────────────────────────────────────
@app.get("/api/market-status")
def market_status():
    """
    Retourne si le marché US est actuellement ouvert.
    Les setups swing sont basés sur OHLC daily → disponibles 24/7.
    Le statut marché sert uniquement à l'UI (mode Exécution vs Préparation).
    """
    from datetime import datetime, timezone, timedelta
    import pytz
    try:
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)
        weekday = now_et.weekday()  # 0=lundi, 6=dimanche
        hour    = now_et.hour
        minute  = now_et.minute
        # Marché ouvert lun-ven 9h30-16h00 ET
        is_open = (
            weekday < 5 and
            (hour > 9 or (hour == 9 and minute >= 30)) and
            hour < 16
        )
        return {
            "is_open":      is_open,
            "mode":         "EXECUTION" if is_open else "PREPARATION",
            "time_et":      now_et.strftime("%H:%M ET"),
            "day":          now_et.strftime("%A"),
            "message":      "Market Open — Execution Mode" if is_open else "Market Closed — Trade Plan Ready",
        }
    except Exception:
        return {"is_open": False, "mode": "PREPARATION", "time_et": "--:--", "day": "--",
                "message": "Market Closed — Trade Plan Ready"}

# ── Cache globals ─────────────────────────────────────────────────────────────
_cache: Dict[str, dict] = {}
_sp500_perf_3m: float = 0.0
_sp500_perf_6m: float = 0.0
_market_regime_cache: dict = {}
_opt_data_cache: Dict[str, object] = {}

# ── Cache OHLCV — TTL adaptatif selon l'heure de marché ──────────────────────
# Marché ouvert  → 15 min  (prix intraday qui bougent)
# Marché fermé   → 4h      (prix de clôture stables, mais on recharge quand même)
_ohlcv_cache: Dict[str, dict] = {}   # {ticker: {"df": DataFrame, "ts": float}}
_OHLCV_TTL_OPEN   =   900   # 15 min pendant les heures de marché
_OHLCV_TTL_CLOSED = 14_400  # 4h  en dehors des heures de marché

# ── Market context cache (VIX + sector strength pour les filtres fondamentaux) ─
_mkt_ctx_cache: dict = {}          # {"vix": float, "sector_strength": dict, "ts": float}
_MKT_CTX_TTL = 900                # 15 min (synchronisé avec OHLCV)


def _market_is_open() -> bool:
    """Retourne True si le marché US est actuellement ouvert (lun-ven 9h30-16h ET)."""
    try:
        import pytz
        from datetime import datetime
        et      = pytz.timezone("America/New_York")
        now_et  = datetime.now(et)
        wd, h, m = now_et.weekday(), now_et.hour, now_et.minute
        return wd < 5 and (h > 9 or (h == 9 and m >= 30)) and h < 16
    except Exception:
        return False


def _ohlcv_ttl() -> int:
    """TTL adaptatif : 15 min si marché ouvert, 4h sinon."""
    return _OHLCV_TTL_OPEN if _market_is_open() else _OHLCV_TTL_CLOSED


def _get_ohlcv(ticker: str) -> Optional[object]:
    """
    Retourne le DataFrame OHLCV du ticker.
    TTL : 15 min si marché ouvert (prix bouge), 4h si fermé.
    """
    now   = _time.time()
    entry = _ohlcv_cache.get(ticker)
    if entry and (now - entry["ts"]) < _ohlcv_ttl():
        return entry["df"]
    try:
        df = yf.download(ticker, period="26mo", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 210:
            return None
        _ohlcv_cache[ticker] = {"df": df, "ts": now}
        return df
    except Exception:
        return None


def _get_market_ctx() -> dict:
    """
    Retourne {vix, sector_strength} depuis le cache (TTL 1h).
    Utilisé par analyze_ticker pour les filtres fondamentaux.
    """
    now = _time.time()
    if _mkt_ctx_cache and (now - _mkt_ctx_cache.get("ts", 0)) < _MKT_CTX_TTL:
        return _mkt_ctx_cache

    try:
        ctx = compute_market_context()
        _mkt_ctx_cache.update({
            "vix":              ctx.get("vix", 20.0),
            "sector_strength":  ctx.get("sector_strength", {}),
            "ts":               now,
        })
    except Exception:
        _mkt_ctx_cache.setdefault("vix", 20.0)
        _mkt_ctx_cache.setdefault("sector_strength", {})
        _mkt_ctx_cache["ts"] = now

    return _mkt_ctx_cache


# ── S&P500 perf ──────────────────────────────────────────────────────────────

def fetch_sp500_perf():
    global _sp500_perf_3m, _sp500_perf_6m
    try:
        df = yf.download("^GSPC", period="8mo", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            close = df["Close"].squeeze()
            _sp500_perf_3m = perf_pct(close, 63)
            _sp500_perf_6m = perf_pct(close, 126)
    except Exception:
        pass


# ── Market Regime ─────────────────────────────────────────────────────────────

_REGIME_EMPTY = {
    "regime": "UNKNOWN", "spy_price": 0.0, "spy_sma50": 0.0,
    "spy_sma200": 0.0, "spy_rsi": 0.0, "spy_perf_1m": 0.0,
    "data_ok": False, "data_warning": "Données marché indisponibles",
}


def _compute_market_regime() -> dict:
    try:
        df = yf.download("SPY", period="14mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 210:
            return {**_REGIME_EMPTY, "data_warning": "SPY : historique insuffisant (< 210 barres)"}

        close     = df["Close"].squeeze()
        spy_price = float(close.iloc[-1])
        spy_sma50 = float(sma(close, 50).iloc[-1])
        spy_sma200= float(sma(close, 200).iloc[-1])
        spy_rsi_v = float(rsi(close, 14).iloc[-1])
        spy_p1m   = perf_pct(close, 21)

        # Validation des valeurs (jamais afficher des zéros silencieux)
        if spy_price <= 0 or spy_sma50 <= 0 or spy_sma200 <= 0:
            return {**_REGIME_EMPTY, "data_warning": "SPY : valeurs calculées invalides"}

        if spy_price > spy_sma200 and spy_price > spy_sma50 and spy_rsi_v > 50:
            regime = "BULL"
        elif spy_price < spy_sma200:
            regime = "BEAR"
        else:
            regime = "RANGE"

        return {
            "regime":       regime,
            "spy_price":    round(spy_price, 2),
            "spy_sma50":    round(spy_sma50, 2),
            "spy_sma200":   round(spy_sma200, 2),
            "spy_rsi":      round(spy_rsi_v, 1),
            "spy_perf_1m":  round(spy_p1m, 2),
            "data_ok":      True,
            "data_warning": None,
        }
    except Exception as e:
        return {**_REGIME_EMPTY, "data_warning": f"SPY fetch failed: {str(e)[:80]}"}


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScoreDetail(BaseModel):
    trend:             int   # /30
    momentum:          int   # /25
    risk_reward:       int   # /20
    relative_strength: int   # /15
    volume_quality:    int   # /10
    details:           Dict[str, bool]


class TickerResult(BaseModel):
    ticker:        str
    sector:        str
    price:         float
    score:         int
    # ── Système de grades ─────────────────────────────────────────────────
    setup_grade:   str      # "A+" | "A" | "B" | "REJECT"
    setup_reason:  str
    confidence:    int      # 0–100
    quality_score: int      # 0–100 — timing quality (distinct du score global)
    # ── Rétrocompat ───────────────────────────────────────────────────────
    category:      str
    signal_type:   str
    position_size: str
    # ── Niveaux dynamiques ─────────────────────────────────────────────────
    entry:         float
    stop_loss:     float
    sl_type:       str      # "ATR" | "Structure"
    tp1:           float
    tp2:           float
    take_profit:   float
    trailing_stop: float
    resistance:    float
    support:       float
    high_52w:      float
    rr_ratio:      float
    # ── Métriques ─────────────────────────────────────────────────────────
    risk_now_pct:   float
    dist_entry_pct: float
    trend_status:   str
    sma50:          float
    sma200:         float
    rsi_val:        float
    macd_val:       float
    atr_val:        float
    perf_3m:        float
    perf_6m:        float
    score_detail:   ScoreDetail
    # ── Earnings ──────────────────────────────────────────────────────────
    earnings_date:    Optional[str]  = None
    earnings_days:    Optional[int]  = None
    earnings_warning: bool           = False
    # ── Setup status (indépendant du marché ouvert/fermé) ─────────────────
    setup_status:     str            = "READY"   # READY | WAIT | INVALID
    # ── Strategy fit ──────────────────────────────────────────────────────
    strategy_fit:     str            = "PULLBACK" # BREAKOUT | PULLBACK | MEAN_REVERSION
    # ── Filtres fondamentaux ──────────────────────────────────────────────
    risk_filters_status: str         = "OK"      # OK | CAUTION | BLOCKED
    risk_filter_reasons: List[str]   = []
    fundamental_risk:    str         = "LOW"     # LOW | MEDIUM | HIGH
    news_risk:           str         = "LOW"     # LOW | MEDIUM | HIGH
    sector_rank:         str         = "NEUTRAL" # STRONG | NEUTRAL | WEAK
    vix_risk:            str         = "LOW"     # LOW | MEDIUM | HIGH
    final_decision:      str         = "WAIT"    # BUY | WAIT | SKIP
    # ── Tradabilité (qualité > quantité) ─────────────────────────────────
    tradable:            bool        = True
    rejection_reason:    str         = ""
    error:            Optional[str]  = None


# ── Analyse d'un ticker ───────────────────────────────────────────────────────

def analyze_ticker(
    ticker: str,
    strategy: str = "standard",
    exclude_earnings: bool = False,
) -> Optional[TickerResult]:
    try:
        # Utiliser le cache OHLCV (évite re-téléchargement à chaque scan)
        df = _get_ohlcv(ticker)
        if df is None:
            return None

        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        price       = float(close.iloc[-1])
        sma200_val  = float(sma(close, 200).iloc[-1])
        sma50_val   = float(sma(close, 50).iloc[-1])
        rsi_val     = float(rsi(close, 14).iloc[-1])
        macd_line, _, macd_hist_s = macd(close)
        macd_val    = float(macd_line.iloc[-1])
        macd_hist_v = float(macd_hist_s.iloc[-1])
        atr_series  = atr(high, low, close, 14)
        atr_val     = float(atr_series.iloc[-1])
        p3m         = perf_pct(close, 63)
        p6m         = perf_pct(close, 126)
        avg_vol     = avg_volume_30d(volume)

        # ── 1. Filtres éliminatoires ─────────────────────────────────────
        filtered, filter_reason = hard_filter(price, sma200_val, rsi_val, avg_vol, atr_val)
        if filtered:
            return None

        # ── 1b. Filtre earnings (configurable) ───────────────────────────
        # Récupérer les earnings en avance (best-effort, non bloquant)
        earnings_date    = None
        earnings_days    = None
        earnings_warning = False
        try:
            earn = get_earnings_date(ticker)
            earnings_date    = earn.get("date")
            earnings_days    = earn.get("days_until")
            earnings_warning = earn.get("warning", False)
            # Si filtre actif : exclure si earnings dans ≤ 5 jours
            if exclude_earnings and earnings_days is not None and 0 <= earnings_days <= 5:
                return None
        except Exception:
            pass

        # ── 2. Niveaux dynamiques ─────────────────────────────────────────
        levels        = compute_dynamic_levels(price, high, low, sma50_val, atr_val)
        entry         = levels["entry"]
        stop_loss     = levels["stop_loss"]
        tp1           = levels["tp1"]
        tp2           = levels["tp2"]
        trailing      = levels["trailing_stop"]
        sl_type       = levels["sl_type"]
        resistance    = levels["resistance"]
        rr_ratio      = levels["rr_ratio"]
        dist_entry    = levels["dist_entry_pct"]
        risk_now      = levels["risk_now_pct"]

        # ── 3. Score professionnel ────────────────────────────────────────
        score, breakdown, details = compute_professional_score(
            price, close, high, low, volume,
            sma50_val, sma200_val, rsi_val, macd_hist_v,
            p3m, p6m,
            entry, stop_loss, resistance,
            _sp500_perf_3m, _sp500_perf_6m,
        )

        # ── 4. Grade & confiance ─────────────────────────────────────────
        setup_grade, setup_reason = classify_setup(score, dist_entry, rr_ratio, rsi_val)

        # Exclure les REJECT du résultat (score < 50)
        if setup_grade == "REJECT":
            return None

        confidence    = compute_confidence(score, rr_ratio, rsi_val)
        quality_score = compute_quality_score(dist_entry, rsi_val, close, atr_val, price)
        signal_type, breakout_valid, breakout_issues = detect_signal_type(
            price, sma50_val, rsi_val, macd_hist_v, high, close, atr_val
        )

        # Support & 52w high
        h52 = _high_52w(high)
        sup = support_level(low, 20)

        # Rétrocompat
        category      = grade_to_category(setup_grade)
        position_size = grade_to_position(setup_grade)
        trend_status  = "En tendance" if price > sma200_val else "Hors tendance"

        score_detail = ScoreDetail(
            trend=breakdown["trend"],
            momentum=breakdown["momentum"],
            risk_reward=breakdown["risk_reward"],
            relative_strength=breakdown["relative_strength"],
            volume_quality=breakdown["volume_quality"],
            details=details,
        )

        # ── Setup status (basé sur qualité du setup, pas marché ouvert) ──────
        # READY   : prix proche de l'entrée (< 2%), bon R/R, grade A/A+
        # WAIT    : prix trop loin de l'entrée ou grade B
        # INVALID : R/R insuffisant ou conditions dégradées
        if rr_ratio < 1.5 or dist_entry > 8:
            setup_status = "INVALID"
        elif setup_grade in ("A+", "A") and dist_entry <= 2:
            setup_status = "READY"
        elif dist_entry <= 5:
            setup_status = "WAIT"
        else:
            setup_status = "WAIT"

        # ── 5. Strategy fit ───────────────────────────────────────────────
        _STRATEGY_FIT_MAP = {
            "Breakout":  "BREAKOUT",
            "Momentum":  "BREAKOUT",
            "Pullback":  "PULLBACK",
            "Neutral":   "MEAN_REVERSION",
        }
        strategy_fit = _STRATEGY_FIT_MAP.get(signal_type, "PULLBACK")

        # ── 6. Filtres fondamentaux ────────────────────────────────────────
        mkt_ctx         = _get_market_ctx()
        vix_val         = mkt_ctx.get("vix", 20.0)
        sector_strength = mkt_ctx.get("sector_strength", {})
        regime_str      = _market_regime_cache.get("regime", "UNKNOWN")
        ticker_sector   = TICKER_SECTOR.get(ticker, "Other")

        fund = compute_fundamental_risk(
            ticker           = ticker,
            sector           = ticker_sector,
            earnings_days    = earnings_days,
            earnings_warning = earnings_warning,
            sector_strength  = sector_strength,
            vix_val          = vix_val,
            regime           = regime_str,
            fetch_news       = True,
        )

        final_decision = compute_final_decision(
            setup_grade  = setup_grade,
            setup_status = setup_status,
            risk_status  = fund["risk_filters_status"],
            rr_ratio     = rr_ratio,
            regime       = regime_str,
            vix_val      = vix_val,
        )

        # ── Tradability (qualité > quantité) ──────────────────────────────
        # Un setup est tradable uniquement si TOUTES les conditions strictes
        # sont réunies. Sinon il reste visible avec sa rejection_reason.
        tradable = True
        rejection_reason = ""

        # 1. Régime de marché — hard filter : BULL_TREND only
        engine_result = compute_regime_engine()
        engine_regime = engine_result.get("regime", "UNKNOWN")
        if engine_regime != "BULL_TREND":
            tradable = False
            rejection_reason = f"Régime {engine_result.get('regime_label', engine_regime)} — seulement BULL_TREND"
        # Pénalité scoring si mauvais régime (déjà appliquée côté scoring si volume faible)
        elif score < 90:
            tradable = False
            rejection_reason = f"Score {score}/100 insuffisant (min 90 requis)"
        elif not (55 <= rsi_val <= 70):
            tradable = False
            rejection_reason = f"RSI {rsi_val:.0f} hors zone optimale (55–70)"
        elif dist_entry > 2.0:
            tradable = False
            rejection_reason = f"Prix {dist_entry:+.1f}% au-dessus de l'entrée (max +2%)"
        elif rr_ratio < 1.5:
            tradable = False
            rejection_reason = f"R/R {rr_ratio:.1f} insuffisant (min 1.5)"
        elif avg_vol < 1_000_000:
            tradable = False
            rejection_reason = f"Liquidité insuffisante ({avg_vol/1_000:.0f}k < 1M)"
        elif signal_type == "Breakout" and not breakout_valid:
            tradable = False
            main_issue = breakout_issues[0] if breakout_issues else "Breakout invalide"
            rejection_reason = f"Breakout non qualifié : {main_issue}"
        # Relative strength : outperformer S&P500 d'au moins 5% sur 3 mois
        elif p3m < _sp500_perf_3m + 5.0:
            tradable = False
            rejection_reason = (
                f"Force relative insuffisante : perf 3m {p3m:+.1f}% vs "
                f"S&P500 {_sp500_perf_3m:+.1f}% (besoin de +5% d'avance)"
            )

        return TickerResult(
            ticker=ticker,
            sector=TICKER_SECTOR.get(ticker, "Other"),
            price=round(price, 2),
            score=score,
            setup_grade=setup_grade,
            setup_reason=setup_reason,
            confidence=confidence,
            quality_score=quality_score,
            category=category,
            signal_type=signal_type,
            position_size=position_size,
            entry=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            sl_type=sl_type,
            tp1=tp1,
            tp2=tp2,
            take_profit=tp2,
            trailing_stop=trailing,
            resistance=round(resistance, 2),
            support=round(sup, 2),
            high_52w=round(h52, 2),
            rr_ratio=rr_ratio,
            risk_now_pct=round(risk_now, 2),
            dist_entry_pct=round(dist_entry, 2),
            trend_status=trend_status,
            sma50=round(sma50_val, 2),
            sma200=round(sma200_val, 2),
            rsi_val=round(rsi_val, 1),
            macd_val=round(macd_val, 4),
            atr_val=round(atr_val, 2),
            perf_3m=round(p3m, 2),
            perf_6m=round(p6m, 2),
            score_detail=score_detail,
            earnings_date=earnings_date,
            earnings_days=earnings_days,
            earnings_warning=earnings_warning,
            setup_status=setup_status,
            strategy_fit=strategy_fit,
            risk_filters_status=fund["risk_filters_status"],
            risk_filter_reasons=fund["risk_filter_reasons"],
            fundamental_risk=fund["fundamental_risk"],
            news_risk=fund["news_risk"],
            sector_rank=fund["sector_rank"],
            vix_risk=fund["vix_risk"],
            final_decision=final_decision,
            tradable=tradable,
            rejection_reason=rejection_reason,
        )
    except Exception:
        return None


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    fetch_sp500_perf()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/screener", response_model=List[TickerResult])
def screener(
    sector:           Optional[str] = Query(None),
    min_score:        int           = Query(0),
    signal:           Optional[str] = Query(None),
    strategy:         str           = Query("standard"),
    exclude_earnings: bool          = Query(False),
):
    fetch_sp500_perf()
    results = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {
            executor.submit(analyze_ticker, t, strategy, exclude_earnings): t
            for t in ALL_TICKERS
        }
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    if sector:
        results = [r for r in results if r.sector == sector]
    if min_score > 0:
        results = [r for r in results if r.score >= min_score]
    if signal:
        results = [r for r in results if r.signal_type == signal]

    results.sort(key=lambda x: (x.score, x.confidence), reverse=True)

    # ── Logging automatique des signaux ───────────────────────────────────────
    try:
        # Mise à jour des outcomes via OHLC (barre par barre, même logique que
        # le Portfolio Backtest Engine — pas de snapshot instantané)
        ohlc_map = {
            t: entry["df"]
            for t, entry in _ohlcv_cache.items()
            if entry.get("df") is not None
        }
        if ohlc_map:
            update_outcomes_ohlc(ohlc_map)
        else:
            # Fallback snapshot si le cache n'est pas encore rempli
            update_outcomes({r.ticker: r.price for r in results})

        for r in results:
            log_signal(
                ticker=r.ticker,
                price=r.price,
                entry=r.entry,
                stop_loss=r.stop_loss,
                tp1=r.tp1,
                tp2=r.tp2,
                grade=r.setup_grade,
                score=r.score,
                confidence=r.confidence,
                rr=r.rr_ratio,
                signal_type=r.signal_type,
                strategy=strategy,
            )
    except Exception:
        pass

    return results


@app.get("/api/screener/{ticker}", response_model=TickerResult)
def screener_single(ticker: str, strategy: str = Query("standard")):
    fetch_sp500_perf()
    res = analyze_ticker(ticker.upper(), strategy)
    if res is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ticker non trouvé ou filtré")
    return res


@app.get("/api/sectors")
def get_sectors():
    return {"sectors": list(TICKERS.keys())}


@app.get("/api/tickers")
def get_tickers():
    return {"tickers": ALL_TICKERS, "by_sector": TICKERS}


# ── Market Regime ─────────────────────────────────────────────────────────────

@app.get("/api/market-regime")
def market_regime():
    global _market_regime_cache
    now = _time.time()
    if _market_regime_cache and (now - _market_regime_cache.get("ts", 0)) < 3600:
        return _market_regime_cache["data"]
    data = _compute_market_regime()
    _market_regime_cache = {"ts": now, "data": data}
    return data



# ── Clear cache (force refresh immédiat de tous les prix) ────────────────────

@app.post("/api/clear-cache")
def clear_cache():
    """
    Vide le cache OHLCV + contexte marché.
    Le prochain appel au screener récupère les prix frais depuis yfinance.
    """
    _ohlcv_cache.clear()
    _mkt_ctx_cache.clear()
    _cache.clear()
    return {"cleared": True, "message": "Cache vidé — les prochains prix seront frais"}


# ── Regime Engine (5 états + stratégie active) ────────────────────────────────

@app.get("/api/regime-engine")
def regime_engine():
    """
    Retourne le régime de marché avancé (5 états) + la stratégie active unique.
    Cache 1h côté serveur.
    """
    return compute_regime_engine()


# ── Backtest ──────────────────────────────────────────────────────────────────

class BacktestResultModel(BaseModel):
    ticker:          str
    total_trades:    int
    wins:            int
    losses:          int
    win_rate:        float
    avg_gain_pct:    float
    avg_loss_pct:    float
    expectancy:      float
    max_drawdown_pct:float
    best_trade_pct:  float
    worst_trade_pct: float
    total_return_pct:float
    avg_duration_days:float
    reliable:        bool
    trades:          List[dict]
    error:           Optional[str] = None


class BacktestSummary(BaseModel):
    results:               List[BacktestResultModel]
    global_win_rate:       float
    global_expectancy:     float
    global_total_trades:   int
    global_reliable_count: int
    best_ticker:           str
    worst_ticker:          str
    # Simulation portfolio réaliste (même moteur que Strategy Lab)
    portfolio:             Optional[dict] = None


def _run_one_backtest(ticker: str, df, strategy: str = "standard") -> BacktestResultModel:
    """Lance run_backtest sur un DataFrame pré-téléchargé."""
    try:
        if df is None or df.empty or len(df) < 210:
            return BacktestResultModel(
                ticker=ticker, total_trades=0, wins=0, losses=0,
                win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
                expectancy=0, max_drawdown_pct=0,
                best_trade_pct=0, worst_trade_pct=0,
                total_return_pct=0, avg_duration_days=0,
                reliable=False, trades=[], error="Données insuffisantes",
            )
        res = run_backtest(ticker, df, strategy)
        return BacktestResultModel(
            ticker=res.ticker, total_trades=res.total_trades,
            wins=res.wins, losses=res.losses, win_rate=res.win_rate,
            avg_gain_pct=res.avg_gain_pct, avg_loss_pct=res.avg_loss_pct,
            expectancy=res.expectancy, max_drawdown_pct=res.max_drawdown_pct,
            best_trade_pct=res.best_trade_pct, worst_trade_pct=res.worst_trade_pct,
            total_return_pct=res.total_return_pct, avg_duration_days=res.avg_duration_days,
            reliable=res.reliable, trades=res.trades, error=res.error,
        )
    except Exception as e:
        return BacktestResultModel(
            ticker=ticker, total_trades=0, wins=0, losses=0,
            win_rate=0, avg_gain_pct=0, avg_loss_pct=0,
            expectancy=0, max_drawdown_pct=0,
            best_trade_pct=0, worst_trade_pct=0,
            total_return_pct=0, avg_duration_days=0,
            reliable=False, trades=[], error=str(e),
        )


@app.get("/api/backtest", response_model=BacktestSummary)
def backtest_all(strategy: str = Query("standard"), period: int = Query(12)):
    """
    Backtest sur tous les tickers.
    Utilise le cache OHLCV (2h) — relance un téléchargement si expiré.
    Les résultats passent dans run_portfolio_backtest pour des métriques réalistes.
    """
    # ── Téléchargement / cache ────────────────────────────────────────────────
    yf_period  = "26mo" if period >= 24 else "14mo"
    min_bars   = 420   if period >= 24 else 210

    data_map: Dict[str, object] = {}

    def _fetch(ticker: str):
        df = _get_ohlcv(ticker)
        # _get_ohlcv utilise period="26mo" ; pour le backtest 12 mois c'est suffisant
        return ticker, df

    with ThreadPoolExecutor(max_workers=16) as ex:
        for ticker, df in ex.map(_fetch, ALL_TICKERS):
            if df is not None and len(df) >= min_bars:
                data_map[ticker] = df

    # ── Backtest par ticker ───────────────────────────────────────────────────
    all_portfolio_trades: list = []
    results: List[BacktestResultModel] = []

    def _run(ticker: str):
        r = _run_one_backtest(ticker, data_map.get(ticker), strategy)
        # Enrichir les trade dicts avec le ticker pour le portfolio engine
        enriched = [
            {**t, "ticker": ticker}
            for t in (r.trades or [])
            if t.get("exit_reason") != "OPEN"   # exclure les trades encore ouverts
        ]
        return r, enriched

    with ThreadPoolExecutor(max_workers=16) as ex:
        for r, trades in ex.map(_run, list(data_map.keys())):
            results.append(r)
            all_portfolio_trades.extend(trades)

    results.sort(key=lambda x: x.total_return_pct, reverse=True)

    valid           = [r for r in results if r.total_trades > 0 and not r.error]
    global_trades   = sum(r.total_trades for r in valid)
    global_wins     = sum(r.wins for r in valid)
    global_win_rate = round(global_wins / global_trades * 100, 1) if global_trades else 0.0
    global_exp      = round(float(np.mean([r.expectancy for r in valid])), 2) if valid else 0.0
    reliable_count  = sum(1 for r in valid if r.reliable)

    # ── Simulation portfolio réaliste ─────────────────────────────────────────
    portfolio = run_portfolio_backtest(all_portfolio_trades, period_months=period)

    return BacktestSummary(
        results=results,
        global_win_rate=global_win_rate,
        global_expectancy=global_exp,
        global_total_trades=global_trades,
        global_reliable_count=reliable_count,
        best_ticker=results[0].ticker if results else "—",
        worst_ticker=results[-1].ticker if results else "—",
        portfolio=portfolio,
    )


@app.get("/api/backtest/{ticker}", response_model=BacktestResultModel)
def backtest_single(ticker: str, strategy: str = Query("standard")):
    df = _get_ohlcv(ticker.upper())
    return _run_one_backtest(ticker.upper(), df, strategy)


# ── API Status ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    import os
    from sentiment import _cache as sent_cache, CACHE_TTL

    r_id     = os.getenv("REDDIT_CLIENT_ID", "")
    r_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    r_agent  = os.getenv("REDDIT_USER_AGENT", "")
    x_token  = os.getenv("X_BEARER_TOKEN", "")

    reddit_missing  = [v for v, val in [
        ("REDDIT_CLIENT_ID", r_id), ("REDDIT_CLIENT_SECRET", r_secret), ("REDDIT_USER_AGENT", r_agent),
    ] if not val]
    twitter_missing = ["X_BEARER_TOKEN"] if not x_token else []

    now = _time.time()
    cache_info = [
        {"ticker": t, "age_minutes": round((now - v["ts"]) / 60, 1), "expires_in": round((CACHE_TTL - (now - v["ts"])) / 60, 1)}
        for t, v in sent_cache.items()
    ]

    return {
        "reddit":  {"configured": not reddit_missing,  "missing_vars": reddit_missing},
        "twitter": {"configured": not twitter_missing, "missing_vars": twitter_missing},
        "all_configured": not reddit_missing and not twitter_missing,
        "sentiment_cache": {"entries": len(sent_cache), "ttl_minutes": CACHE_TTL // 60, "tickers": cache_info},
    }


# ── Social Sentiment ──────────────────────────────────────────────────────────

@app.get("/api/social-sentiment")
def social_sentiment(ticker: str = Query(...)):
    return get_sentiment(ticker.upper())


# ── Strategy Lab ──────────────────────────────────────────────────────────────

@app.get("/api/strategy-lab")
def strategy_lab_endpoint(period: int = Query(12)):
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    data_cache: Dict[str, object] = {}

    def _download(ticker: str):
        try:
            df = yf.download(ticker, period=yf_period, interval="1d", progress=False, auto_adjust=True)
            if not df.empty and len(df) >= min_bars:
                return ticker, df
        except Exception:
            pass
        return ticker, None

    with ThreadPoolExecutor(max_workers=12) as ex:
        for ticker, df in ex.map(_download, ALL_TICKERS):
            if df is not None:
                data_cache[ticker] = df

    valid_tickers = list(data_cache.keys())
    lab_results = []

    for strat_def in LAB_STRATEGIES:
        all_trades = []

        def _run_ticker(ticker, _strat=strat_def):
            return backtest_ticker_lab(ticker, data_cache[ticker], _strat, period)

        with ThreadPoolExecutor(max_workers=12) as ex:
            for trades in ex.map(_run_ticker, valid_tickers):
                all_trades.extend(trades)

        result = aggregate_lab_result(strat_def, all_trades, period)
        lab_results.append(result)

    lab_results.sort(key=lambda r: r["score"], reverse=True)

    # ── Classement par critère ────────────────────────────────────────────────
    tradable  = [r for r in lab_results if r.get("tradable_status") == "TRADABLE"]
    confirmed = [r for r in lab_results if r.get("tradable_status") == "À CONFIRMER"]
    eligible  = [r for r in lab_results if r.get("eligible")]

    robust_pool  = tradable or confirmed or eligible or lab_results
    quality_pool = [r for r in robust_pool if not r.get("overfitting_risk", False)] or robust_pool

    def _best(lst, fn, default="—"):
        valid = [r for r in lst if r.get("total_trades", 0) > 0]
        return fn(valid)["key"] if valid else default

    return {
        "strategies":          lab_results,
        "best_overall":        _best(robust_pool,  lambda l: max(l, key=lambda r: r["score"])),
        "best_win_rate":       _best(quality_pool, lambda l: max(l, key=lambda r: r["win_rate"])),
        "best_expectancy":     _best(quality_pool, lambda l: max(l, key=lambda r: r["expectancy"])),
        "best_pf":             _best(quality_pool, lambda l: max(l, key=lambda r: r["profit_factor"])),
        "best_low_dd":         _best(quality_pool, lambda l: min(l, key=lambda r: r["max_drawdown_pct"])),
        "has_robust_strategy": len(tradable) > 0,
        "tradable_count":      len(tradable),
        "confirmed_count":     len(confirmed),
        "period_months":       period,
    }


# ── Market Context ────────────────────────────────────────────────────────────

@app.get("/api/market-context")
def market_context_endpoint():
    return compute_market_context()


# ── Signal Tracker ────────────────────────────────────────────────────────────

@app.get("/api/signals")
def signals_endpoint(limit: int = Query(200)):
    return {
        "signals": get_signals(limit),
        "stats":   get_signal_stats(),
    }


# ── Setup Stats (validation historique) ──────────────────────────────────────

@app.get("/api/setup-stats/{ticker}")
def setup_stats(
    ticker:  str,
    grade:   str = Query("A+"),
    period:  int = Query(24),
):
    """
    Valide historiquement le setup d'un ticker avec les EXACTES mêmes règles
    que le screener live.
    Télécharge les données si nécessaire (réponse peut prendre 3-5s).
    """
    t = ticker.upper()
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    try:
        df = yf.download(t, period=yf_period, interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < min_bars:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Données insuffisantes")

        return validate_setup(
            ticker=t,
            df=df,
            grade_filter=grade,
            sp500_perf_3m=_sp500_perf_3m,
            sp500_perf_6m=_sp500_perf_6m,
            period_months=period,
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# ── Earnings ──────────────────────────────────────────────────────────────────

@app.get("/api/earnings/{ticker}")
def earnings_endpoint(ticker: str):
    return get_earnings_date(ticker.upper())


# ── Parameter Optimizer ───────────────────────────────────────────────────────

@app.get("/api/optimizer")
def optimizer_endpoint(period: int = Query(12)):
    global _opt_data_cache
    yf_period = "26mo" if period >= 24 else "14mo"
    min_bars  = 420   if period >= 24 else 210

    if not _opt_data_cache:
        def _dl(ticker: str):
            try:
                df = yf.download(ticker, period=yf_period, interval="1d", progress=False, auto_adjust=True)
                if not df.empty and len(df) >= min_bars:
                    return ticker, df
            except Exception:
                pass
            return ticker, None

        with ThreadPoolExecutor(max_workers=12) as ex:
            for ticker, df in ex.map(_dl, ALL_TICKERS):
                if df is not None:
                    _opt_data_cache[ticker] = df

    return run_optimizer(_opt_data_cache, period_months=period)
