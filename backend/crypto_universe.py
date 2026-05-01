"""
Scope: CRYPTO

Univers crypto principal, séparé du module Actions.
"""

from typing import Dict, List


CRYPTO_UNIVERSE: List[Dict[str, str]] = [
    {"symbol": "BTC", "pair": "BTCUSDT", "coingecko_id": "bitcoin", "sector": "Store of Value"},
    {"symbol": "ETH", "pair": "ETHUSDT", "coingecko_id": "ethereum", "sector": "Smart Contracts"},
    {"symbol": "SOL", "pair": "SOLUSDT", "coingecko_id": "solana", "sector": "Layer 1"},
    {"symbol": "BNB", "pair": "BNBUSDT", "coingecko_id": "binancecoin", "sector": "Exchange"},
    {"symbol": "XRP", "pair": "XRPUSDT", "coingecko_id": "ripple", "sector": "Payments"},
    {"symbol": "ADA", "pair": "ADAUSDT", "coingecko_id": "cardano", "sector": "Layer 1"},
    {"symbol": "AVAX", "pair": "AVAXUSDT", "coingecko_id": "avalanche-2", "sector": "Layer 1"},
    {"symbol": "DOGE", "pair": "DOGEUSDT", "coingecko_id": "dogecoin", "sector": "Meme"},
    {"symbol": "TON", "pair": "TONUSDT", "coingecko_id": "the-open-network", "sector": "Layer 1"},
    {"symbol": "LINK", "pair": "LINKUSDT", "coingecko_id": "chainlink", "sector": "Oracle"},
    {"symbol": "DOT", "pair": "DOTUSDT", "coingecko_id": "polkadot", "sector": "Layer 0"},
    {"symbol": "POL", "pair": "POLUSDT", "coingecko_id": "polygon-ecosystem-token", "sector": "Layer 2"},
    {"symbol": "LTC", "pair": "LTCUSDT", "coingecko_id": "litecoin", "sector": "Payments"},
    {"symbol": "BCH", "pair": "BCHUSDT", "coingecko_id": "bitcoin-cash", "sector": "Payments"},
    {"symbol": "UNI", "pair": "UNIUSDT", "coingecko_id": "uniswap", "sector": "DeFi"},
    {"symbol": "APT", "pair": "APTUSDT", "coingecko_id": "aptos", "sector": "Layer 1"},
    {"symbol": "NEAR", "pair": "NEARUSDT", "coingecko_id": "near", "sector": "Layer 1"},
    {"symbol": "ICP", "pair": "ICPUSDT", "coingecko_id": "internet-computer", "sector": "Infra"},
    {"symbol": "FIL", "pair": "FILUSDT", "coingecko_id": "filecoin", "sector": "Storage"},
    {"symbol": "ATOM", "pair": "ATOMUSDT", "coingecko_id": "cosmos", "sector": "Layer 0"},
    {"symbol": "INJ", "pair": "INJUSDT", "coingecko_id": "injective-protocol", "sector": "DeFi"},
    {"symbol": "ARB", "pair": "ARBUSDT", "coingecko_id": "arbitrum", "sector": "Layer 2"},
    {"symbol": "OP", "pair": "OPUSDT", "coingecko_id": "optimism", "sector": "Layer 2"},
    {"symbol": "SUI", "pair": "SUIUSDT", "coingecko_id": "sui", "sector": "Layer 1"},
    {"symbol": "SEI", "pair": "SEIUSDT", "coingecko_id": "sei-network", "sector": "Layer 1"},
]

CRYPTO_SYMBOLS: List[str] = [item["symbol"] for item in CRYPTO_UNIVERSE]
CRYPTO_BY_SYMBOL: Dict[str, Dict[str, str]] = {item["symbol"]: item for item in CRYPTO_UNIVERSE}
CRYPTO_SECTORS: List[str] = sorted({item["sector"] for item in CRYPTO_UNIVERSE})
