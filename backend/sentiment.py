"""
Social Sentiment Service
Sources : Reddit (PRAW) + Twitter/X API v2
Cache   : 45 minutes en mémoire

Aucune clé API dans ce fichier — tout via .env / variables d'environnement.
"""

import os
import re
import time
import math
import logging
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ── Env vars ──────────────────────────────────────────────────────────────────

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "SwingScreenerBot/1.0")
X_BEARER_TOKEN       = os.getenv("X_BEARER_TOKEN", "")

# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: Dict[str, dict] = {}
CACHE_TTL = 45 * 60  # 45 minutes


def _cache_get(ticker: str) -> Optional[dict]:
    entry = _cache.get(ticker)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(ticker: str, data: dict):
    _cache[ticker] = {"ts": time.time(), "data": data}


# ── Mapping ticker → nom entreprise ──────────────────────────────────────────

COMPANY_NAMES: Dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "GOOGL": "Google",
    "GOOG": "Google", "META": "Meta", "AMZN": "Amazon", "TSLA": "Tesla",
    "AMD": "AMD Advanced Micro Devices", "NFLX": "Netflix", "ORCL": "Oracle",
    "CRM": "Salesforce", "ADBE": "Adobe", "QCOM": "Qualcomm", "INTC": "Intel",
    "TXN": "Texas Instruments", "AMAT": "Applied Materials", "LRCX": "Lam Research",
    "SNPS": "Synopsys", "KLAC": "KLA Corporation",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "V": "Visa", "MA": "Mastercard",
    "JNJ": "Johnson Johnson", "UNH": "UnitedHealth", "PFE": "Pfizer",
    "ABBV": "AbbVie", "MRK": "Merck", "LLY": "Eli Lilly", "TMO": "Thermo Fisher",
    "DHR": "Danaher", "ISRG": "Intuitive Surgical",
    "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot", "NKE": "Nike",
    "SBUX": "Starbucks", "MCD": "McDonald",
    "XOM": "ExxonMobil", "CVX": "Chevron",
    "AMT": "American Tower", "NEE": "NextEra Energy",
}

SUBREDDITS = ["stocks", "investing", "wallstreetbets", "SecurityAnalysis", "options"]

# ── Filtrage qualité ──────────────────────────────────────────────────────────

HYPE_WORDS = {
    "moon", "rocket", "100x", "1000x", "yolo", "ape", "apes",
    "diamond hands", "diamond", "squeeze", "short squeeze", "gamma squeeze",
    "lambo", "tendies", "to the moon", "buy now", "pump", "pumping",
    "get in", "last chance", "guaranteed", "easy money", "free money",
    "🚀", "💎", "🦍",
}

_SPAM_PATTERNS = re.compile(
    r"(to the moon|guaranteed profit|easy money|"
    r"join my discord|join my telegram|dm me|follow me|"
    r"\b(100x|1000x|50x)\b|"
    r"free stock|free money)",
    re.IGNORECASE,
)

MIN_TEXT_LENGTH = 25


def _is_spam(text: str) -> bool:
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return True
    return bool(_SPAM_PATTERNS.search(text))


def _hype_ratio(text: str) -> float:
    """Fraction de mots de hype dans le texte (0-1)."""
    words = set(text.lower().split())
    hits = sum(1 for w in HYPE_WORDS if w in text.lower())
    return hits / max(len(words), 1)


# ── Analyse de sentiment (lexique financier) ──────────────────────────────────

# Essaie d'importer VADER ; fallback sur lexique maison si absent
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()

    # Boost des termes financiers spécifiques
    _FIN_LEXICON = {
        "bullish": 2.5, "bearish": -2.5, "breakout": 1.8, "breakdown": -1.8,
        "uptrend": 2.0, "downtrend": -2.0, "oversold": 1.2, "overbought": -1.2,
        "beat": 1.5, "miss": -1.5, "outperform": 2.0, "underperform": -2.0,
        "upgrade": 2.0, "downgrade": -2.0, "buy": 1.2, "sell": -1.2,
        "surge": 2.0, "plunge": -2.0, "rally": 1.8, "crash": -2.5,
        "growth": 1.5, "decline": -1.5, "strong": 1.5, "weak": -1.5,
        "conviction": 1.5, "avoid": -1.5, "opportunity": 1.5, "risk": -0.5,
        "overvalued": -1.5, "undervalued": 1.5, "squeeze": -0.5,
        "dump": -2.0, "short": -0.8, "puts": -0.8, "calls": 0.8,
    }
    _vader.lexicon.update(_FIN_LEXICON)
    VADER_AVAILABLE = True

    def _compound(text: str) -> float:
        return _vader.polarity_scores(text)["compound"]

except ImportError:
    VADER_AVAILABLE = False
    _POS = {
        "bull", "bullish", "buy", "strong", "beat", "outperform", "surge",
        "rally", "growth", "upgrade", "breakout", "uptrend", "opportunity",
        "positive", "good", "great", "excellent", "profit", "gain", "up",
        "higher", "rise", "rising", "strength", "conviction", "undervalued",
    }
    _NEG = {
        "bear", "bearish", "sell", "weak", "miss", "underperform", "crash",
        "plunge", "decline", "downgrade", "breakdown", "downtrend", "risk",
        "negative", "bad", "poor", "loss", "down", "lower", "fall", "falling",
        "weakness", "overvalued", "dump", "avoid", "concern", "warning",
    }

    def _compound(text: str) -> float:
        words = set(text.lower().split())
        pos = len(words & _POS)
        neg = len(words & _NEG)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total


def _score_posts(items: List[Tuple[str, float]]) -> Tuple[float, int, int]:
    """
    items : liste de (text, weight)
    Retourne (score_0_10, hype_count, valid_count)
    """
    weighted_compound = 0.0
    total_weight      = 0.0
    hype_count        = 0
    valid_count       = 0

    for text, weight in items:
        if _is_spam(text):
            continue
        hr = _hype_ratio(text)
        if hr > 0.12:           # > 12 % de mots hype
            hype_count += 1
            weight *= 0.25      # pénalité forte

        c = _compound(text)
        weighted_compound += c * weight
        total_weight      += weight
        valid_count       += 1

    if total_weight == 0 or valid_count == 0:
        return 5.0, hype_count, valid_count

    avg = weighted_compound / total_weight
    # Normalisation [-1, 1] → [0, 10]
    score = (avg + 1) / 2 * 10
    return max(0.0, min(10.0, score)), hype_count, valid_count


def _recency_weight(created_utc: float, now: float) -> float:
    """Poids décroissant selon l'âge. 24h = 1.0, 7j = 0.3."""
    age_h = (now - created_utc) / 3600
    return max(0.1, math.exp(-age_h / 48))   # demi-vie ≈ 48h


# ── Reddit ────────────────────────────────────────────────────────────────────

def _fetch_reddit(ticker: str) -> Tuple[float, int, int, str]:
    """
    Retourne (reddit_score 0-10, hype_count, mention_count, error_msg)
    """
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return 5.0, 0, 0, "Reddit API not configured"

    try:
        import praw  # type: ignore
    except ImportError:
        return 5.0, 0, 0, "praw not installed (pip install praw)"

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )

        company = COMPANY_NAMES.get(ticker, "")
        queries = [f"${ticker}", ticker]
        if company:
            queries.append(company.split()[0])  # premier mot du nom

        now = time.time()
        items: List[Tuple[str, float]] = []
        seen: set = set()

        for sub_name in SUBREDDITS:
            sub = reddit.subreddit(sub_name)
            for q in queries[:2]:           # max 2 requêtes par sub
                try:
                    for post in sub.search(q, time_filter="week", limit=20):
                        if post.id in seen:
                            continue
                        seen.add(post.id)

                        body = (post.title or "") + " " + (post.selftext or "")
                        upvotes = max(1, post.score)
                        rec = _recency_weight(post.created_utc, now)
                        w = math.log1p(upvotes) * rec
                        items.append((body, w))

                        # Top commentaires
                        post.comments.replace_more(limit=0)
                        for c in list(post.comments)[:5]:
                            if hasattr(c, "body") and len(c.body) > MIN_TEXT_LENGTH:
                                cw = math.log1p(max(1, c.score)) * rec * 0.5
                                items.append((c.body, cw))
                except Exception:
                    continue

        if not items:
            return 5.0, 0, 0, ""

        score, hype, count = _score_posts(items)
        return score, hype, count, ""

    except Exception as e:
        logger.warning(f"Reddit error for {ticker}: {e}")
        return 5.0, 0, 0, str(e)


# ── Twitter / X API v2 ───────────────────────────────────────────────────────

_X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def _fetch_twitter(ticker: str) -> Tuple[float, int, int, str]:
    """
    Retourne (twitter_score 0-10, hype_count, mention_count, error_msg)
    """
    if not X_BEARER_TOKEN:
        return 5.0, 0, 0, "X API not configured (missing X_BEARER_TOKEN)"

    company = COMPANY_NAMES.get(ticker, "")
    cashtag  = f"${ticker}"
    # Requête principale : cashtag + langue anglaise, sans retweets
    query = f'({cashtag} OR "{ticker}") lang:en -is:retweet'
    if company:
        first_word = company.split()[0]
        if len(first_word) > 3:
            query = f'({cashtag} OR "{first_word}") lang:en -is:retweet'

    params = {
        "query":        query,
        "max_results":  100,
        "tweet.fields": "created_at,public_metrics,lang",
    }
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        resp = requests.get(_X_SEARCH_URL, params=params, headers=headers, timeout=10)

        if resp.status_code == 401:
            return 5.0, 0, 0, "X API unauthorized — check X_BEARER_TOKEN"
        if resp.status_code == 403:
            return 5.0, 0, 0, "X API unavailable — plan insuffisant (Basic requis)"
        if resp.status_code == 429:
            return 5.0, 0, 0, "X API rate limited — réessayez plus tard"
        if resp.status_code != 200:
            return 5.0, 0, 0, f"X API error {resp.status_code}"

        data   = resp.json()
        tweets = data.get("data", [])
        if not tweets:
            return 5.0, 0, 0, ""

        now = time.time()
        items: List[Tuple[str, float]] = []

        for tw in tweets:
            text    = tw.get("text", "")
            metrics = tw.get("public_metrics", {})
            likes   = metrics.get("like_count", 0)
            rts     = metrics.get("retweet_count", 0)

            # Poids : engagement + récence (tweets récents par défaut dans l'API)
            w = math.log1p(likes + rts * 2 + 1)
            items.append((text, w))

        score, hype, count = _score_posts(items)
        return score, hype, count, ""

    except requests.exceptions.Timeout:
        return 5.0, 0, 0, "X API timeout"
    except Exception as e:
        logger.warning(f"Twitter error for {ticker}: {e}")
        return 5.0, 0, 0, str(e)


# ── Score final & labels ──────────────────────────────────────────────────────

def _sentiment_label(score: float) -> str:
    if score >= 8.0:  return "Very Bullish"
    if score >= 6.5:  return "Bullish"
    if score >= 4.5:  return "Neutral"
    if score >= 3.0:  return "Bearish"
    return "Very Bearish"


def _hype_risk(hype_reddit: int, hype_twitter: int, total: int) -> str:
    if total == 0:
        return "Low"
    ratio = (hype_reddit + hype_twitter) / max(total, 1)
    if ratio > 0.35:  return "High"
    if ratio > 0.18:  return "Medium"
    return "Low"


def _impact(score: float, hype: str) -> str:
    if hype == "High":
        return "⚠️ Hype détectée — ne pas acheter sur sentiment seul"
    if score >= 7.5:
        return "✅ Sentiment confirme un signal haussier"
    if score >= 5.5:
        return "🔵 Sentiment neutre — se fier à l'analyse technique"
    if score >= 4.0:
        return "🟡 Sentiment légèrement négatif — prudence"
    return "🔴 Sentiment contredit le signal technique — caution"


def _auto_summary(
    ticker: str,
    tw_score: float, rd_score: float,
    final: float,
    tw_err: str, rd_err: str,
    mentions: int, hype: str,
) -> str:
    parts = []
    if tw_err:
        parts.append(f"X: {tw_err}.")
    else:
        tw_lbl = _sentiment_label(tw_score)
        parts.append(f"X/Twitter ({tw_score:.1f}/10) : {tw_lbl}.")
    if rd_err:
        parts.append(f"Reddit: {rd_err}.")
    else:
        rd_lbl = _sentiment_label(rd_score)
        parts.append(f"Reddit ({rd_score:.1f}/10) : {rd_lbl}.")
    parts.append(f"{mentions} mentions analysées.")
    if hype == "High":
        parts.append("⚠️ Volume de hype élevé détecté — signal peu fiable.")
    return " ".join(parts)


# ── Point d'entrée principal ──────────────────────────────────────────────────

def get_sentiment(ticker: str) -> dict:
    """
    Retourne le sentiment social complet pour un ticker.
    Résultat mis en cache 45 minutes.
    """
    cached = _cache_get(ticker)
    if cached:
        return {**cached, "cached": True}

    tw_score, tw_hype, tw_count, tw_err = _fetch_twitter(ticker)
    rd_score, rd_hype, rd_count, rd_err = _fetch_reddit(ticker)

    # Score final pondéré (Twitter 60 %, Reddit 40 %)
    tw_available = not tw_err or "not configured" not in tw_err.lower()
    rd_available = not rd_err or "not configured" not in rd_err.lower()

    if tw_available and rd_available:
        final = tw_score * 0.6 + rd_score * 0.4
    elif tw_available:
        final = tw_score
    elif rd_available:
        final = rd_score
    else:
        final = 5.0   # neutre par défaut si les deux APIs sont indisponibles

    total_mentions = tw_count + rd_count
    total_hype     = tw_hype + rd_hype
    hype           = _hype_risk(rd_hype, tw_hype, total_mentions)

    # Tendance grossière : si les deux sources concordent → stable
    if abs(tw_score - rd_score) < 1.5:
        trend = "Stable"
    elif tw_score > rd_score + 1.5:
        trend = "Improving"   # Twitter (plus réactif) plus positif
    else:
        trend = "Declining"

    result = {
        "ticker":                ticker,
        "twitter_score":         round(tw_score, 1),
        "reddit_score":          round(rd_score, 1),
        "sentiment_score":       round(final, 1),
        "sentiment_label":       _sentiment_label(final),
        "hype_risk":             hype,
        "mention_volume":        total_mentions,
        "sentiment_trend":       trend,
        "divergence":            total_hype > total_mentions * 0.3,
        "summary":               _auto_summary(ticker, tw_score, rd_score, final, tw_err, rd_err, total_mentions, hype),
        "impact_on_trade_signal": _impact(final, hype),
        "twitter_error":         tw_err or None,
        "reddit_error":          rd_err or None,
        "cached":                False,
        "vader_available":       VADER_AVAILABLE,
    }

    _cache_set(ticker, result)
    return result
