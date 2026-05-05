"""
Scope: CRYPTO SCALP

Univers Scalp — Classification par Tier pour Phase 1 et au-delà.
Phase 1: Affichage des données sans edge complet (arrivera en Phase 2)
"""

from typing import Dict, List, FrozenSet

# ─── TIER 1: Ultra-Liquid, Real Trading Ready (5 cryptos) ────────────────────
SCALP_TIER1_SYMBOLS: List[str] = [
    "BTC", "ETH", "SOL", "BNB", "XRP"
]

# ─── TIER 2: Tradable, Good Liquidity (22 cryptos) ─────────────────────────
SCALP_TIER2_SYMBOLS: List[str] = [
    "LINK", "AVAX", "DOGE", "ADA", "LTC", "BCH", "DOT", "ATOM",
    "NEAR", "SUI", "APT", "INJ", "OP", "ARB", "UNI", "AAVE", "MKR",
    "FIL", "ICP", "SEI", "TON", "POL"
]

# ─── TIER 3: Paper/Watch Only (10 cryptos, optional lazy-load) ───────────────
SCALP_TIER3_SYMBOLS: List[str] = [
    "HBAR", "RENDER", "ONDO", "FET", "AR", "TIA", "JUP", "WIF", "PENDLE", "DYDX"
]

# ─── Univers combiné ─────────────────────────────────────────────────────
SCALP_WATCH_UNIVERSE: FrozenSet[str] = frozenset(
    SCALP_TIER1_SYMBOLS + SCALP_TIER2_SYMBOLS + SCALP_TIER3_SYMBOLS
)

SCALP_TRADABLE_UNIVERSE: FrozenSet[str] = frozenset(
    SCALP_TIER1_SYMBOLS + SCALP_TIER2_SYMBOLS
)

SCALP_TIER1_SET: FrozenSet[str] = frozenset(SCALP_TIER1_SYMBOLS)
SCALP_TIER2_SET: FrozenSet[str] = frozenset(SCALP_TIER2_SYMBOLS)
SCALP_TIER3_SET: FrozenSet[str] = frozenset(SCALP_TIER3_SYMBOLS)


def get_scalp_tier(symbol: str) -> int:
    """Return tier (1, 2, 3) for a symbol, or 0 if unknown."""
    symbol = symbol.upper()
    if symbol in SCALP_TIER1_SET:
        return 1
    if symbol in SCALP_TIER2_SET:
        return 2
    if symbol in SCALP_TIER3_SET:
        return 3
    return 0


def is_scalp_watchable(symbol: str) -> bool:
    """Check if symbol can be watched (all tiers)."""
    return symbol.upper() in SCALP_WATCH_UNIVERSE


def is_scalp_tradable_phase2(symbol: str) -> bool:
    """Check if symbol is in Tier 1/2 (will be tradable in Phase 2+)."""
    return symbol.upper() in SCALP_TRADABLE_UNIVERSE
