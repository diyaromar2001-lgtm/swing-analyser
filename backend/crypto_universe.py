"""
Scope: CRYPTO

Univers crypto principal, séparé du module Actions.
"""

from typing import Dict, List


CRYPTO_UNIVERSE: List[Dict[str, str]] = [
    {"symbol": "BTC", "pair": "BTCUSDT", "coingecko_id": "bitcoin", "yahoo_symbol": "BTC-USD", "sector": "Store of Value"},
    {"symbol": "ETH", "pair": "ETHUSDT", "coingecko_id": "ethereum", "yahoo_symbol": "ETH-USD", "sector": "Smart Contracts"},
    {"symbol": "SOL", "pair": "SOLUSDT", "coingecko_id": "solana", "yahoo_symbol": "SOL-USD", "sector": "Layer 1"},
    {"symbol": "BNB", "pair": "BNBUSDT", "coingecko_id": "binancecoin", "yahoo_symbol": "BNB-USD", "sector": "Exchange"},
    {"symbol": "XRP", "pair": "XRPUSDT", "coingecko_id": "ripple", "yahoo_symbol": "XRP-USD", "sector": "Payments"},
    {"symbol": "ADA", "pair": "ADAUSDT", "coingecko_id": "cardano", "yahoo_symbol": "ADA-USD", "sector": "Layer 1"},
    {"symbol": "AVAX", "pair": "AVAXUSDT", "coingecko_id": "avalanche-2", "yahoo_symbol": "AVAX-USD", "sector": "Layer 1"},
    {"symbol": "DOGE", "pair": "DOGEUSDT", "coingecko_id": "dogecoin", "yahoo_symbol": "DOGE-USD", "sector": "Meme"},
    {"symbol": "TON", "pair": "TONUSDT", "coingecko_id": "the-open-network", "yahoo_symbol": "TON11419-USD", "sector": "Layer 1"},
    {"symbol": "LINK", "pair": "LINKUSDT", "coingecko_id": "chainlink", "yahoo_symbol": "LINK-USD", "sector": "Oracle"},
    {"symbol": "DOT", "pair": "DOTUSDT", "coingecko_id": "polkadot", "yahoo_symbol": "DOT-USD", "sector": "Layer 0"},
    {"symbol": "POL", "pair": "POLUSDT", "coingecko_id": "polygon-ecosystem-token", "yahoo_symbol": "POL-USD", "sector": "Layer 2"},
    {"symbol": "LTC", "pair": "LTCUSDT", "coingecko_id": "litecoin", "yahoo_symbol": "LTC-USD", "sector": "Payments"},
    {"symbol": "BCH", "pair": "BCHUSDT", "coingecko_id": "bitcoin-cash", "yahoo_symbol": "BCH-USD", "sector": "Payments"},
    {"symbol": "UNI", "pair": "UNIUSDT", "coingecko_id": "uniswap", "yahoo_symbol": "UNI7083-USD", "sector": "DeFi"},
    {"symbol": "APT", "pair": "APTUSDT", "coingecko_id": "aptos", "yahoo_symbol": "APT21794-USD", "sector": "Layer 1"},
    {"symbol": "NEAR", "pair": "NEARUSDT", "coingecko_id": "near", "yahoo_symbol": "NEAR-USD", "sector": "Layer 1"},
    {"symbol": "ICP", "pair": "ICPUSDT", "coingecko_id": "internet-computer", "yahoo_symbol": "ICP-USD", "sector": "Infra"},
    {"symbol": "FIL", "pair": "FILUSDT", "coingecko_id": "filecoin", "yahoo_symbol": "FIL-USD", "sector": "Storage"},
    {"symbol": "ATOM", "pair": "ATOMUSDT", "coingecko_id": "cosmos", "yahoo_symbol": "ATOM-USD", "sector": "Layer 0"},
    {"symbol": "INJ", "pair": "INJUSDT", "coingecko_id": "injective-protocol", "yahoo_symbol": "INJ-USD", "sector": "DeFi"},
    {"symbol": "ARB", "pair": "ARBUSDT", "coingecko_id": "arbitrum", "yahoo_symbol": "ARB11841-USD", "sector": "Layer 2"},
    {"symbol": "OP", "pair": "OPUSDT", "coingecko_id": "optimism", "yahoo_symbol": "OP-USD", "sector": "Layer 2"},
    {"symbol": "SUI", "pair": "SUIUSDT", "coingecko_id": "sui", "yahoo_symbol": "SUI20947-USD", "sector": "Layer 1"},
    {"symbol": "SEI", "pair": "SEIUSDT", "coingecko_id": "sei-network", "yahoo_symbol": "SEI-USD", "sector": "Layer 1"},
    {"symbol": "AAVE", "pair": "AAVEUSDT", "coingecko_id": "aave", "yahoo_symbol": "AAVE-USD", "sector": "DeFi"},
    {"symbol": "MKR", "pair": "MKRUSDT", "coingecko_id": "maker", "yahoo_symbol": "MKR-USD", "sector": "DeFi"},
]

CRYPTO_SYMBOLS: List[str] = [item["symbol"] for item in CRYPTO_UNIVERSE]
CRYPTO_BY_SYMBOL: Dict[str, Dict[str, str]] = {item["symbol"]: item for item in CRYPTO_UNIVERSE}
CRYPTO_SECTORS: List[str] = sorted({item["sector"] for item in CRYPTO_UNIVERSE})

# ── Crypto Tradable V1 ───────────────────────────────────────────────────────────
# Phase 1 tradable universe: BTC, ETH, SOL, BNB, LINK, AAVE, MKR
# Only these 7 symbols can be executed (PLANNED/OPEN) in Crypto Tradable V1.
# WATCHLIST remains available for all crypto symbols regardless of this universe.
CRYPTO_TRADABLE_UNIVERSE_V1: frozenset = frozenset({
    "BTC", "ETH", "SOL", "BNB", "LINK", "AAVE", "MKR"
})


def is_tradable_crypto(symbol: str) -> bool:
    """Check if symbol is in Phase 1 tradable universe.

    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH")

    Returns:
        True if symbol can be traded, False otherwise
    """
    return symbol.upper() in CRYPTO_TRADABLE_UNIVERSE_V1
