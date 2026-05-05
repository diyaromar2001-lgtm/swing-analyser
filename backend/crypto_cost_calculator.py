"""
Cost Calculator for Crypto Scalp Paper Trading

Provides cost estimation for paper trades:
- Bid-ask spread per symbol
- Trading fees (entry + exit)
- Slippage by symbol tier
- Roundtrip cost calculation
"""

from typing import Dict, Optional

# Spread estimates in basis points (0.01% = 1 bp)
# Based on typical Binance spot market liquidity
SYMBOL_SPREAD_BPS = {
    # Tier 1: Ultra-liquid, tight spreads
    "BTC": 5,
    "ETH": 8,
    "SOL": 10,
    "BNB": 8,
    "XRP": 12,

    # Tier 2: Good liquidity, moderate spreads
    "MKR": 15,
    "DOGE": 12,
    "TON": 15,
    "INJ": 18,
    "AVAX": 15,
    "POL": 18,
    "UNI": 15,
    "LTC": 12,
    "DOT": 18,
    "OP": 18,
    "ARB": 18,
    "AEVO": 25,
    "SEI": 20,
    "APT": 18,
    "ONDO": 22,
    "JUP": 20,
    "PENDLE": 20,

    # Tier 3: Lower liquidity, wider spreads
    "RENDER": 30,
    "MANTA": 30,
    "CYBER": 35,
    "ETHFI": 35,
    "MORPHO": 30,
    "BOME": 40,
    "BEAM": 35,
    "LISTA": 35,
    "AI": 35,
    "GOAT": 45,
}

# Slippage estimates by tier (percentage)
# Represents adverse price movement for typical paper trade quantity
SLIPPAGE_BY_TIER = {
    1: 0.05,   # Tier 1 (BTC, ETH, SOL, BNB, XRP): 0.05% slippage
    2: 0.10,   # Tier 2 (22 alt-coins): 0.10% slippage
    3: 0.20,   # Tier 3 (10 watch-only): 0.20% slippage
}

# Fixed fees (per Binance standard rates)
ENTRY_FEE_PCT = 0.10    # 0.1% entry fee
EXIT_FEE_PCT = 0.10     # 0.1% exit fee


def calculate_spread_bps(symbol: str) -> int:
    """
    Calculate bid-ask spread in basis points for a symbol.

    Args:
        symbol: Crypto symbol (BTC, ETH, SOL, etc.)

    Returns:
        Spread in basis points (e.g., 8 = 0.08%)
    """
    symbol_upper = symbol.upper()
    # Default to 20 bps if symbol not found (safe overestimate)
    return SYMBOL_SPREAD_BPS.get(symbol_upper, 20)


def estimate_fees(entry_amount_usd: float, exit_amount_usd: float) -> Dict[str, float]:
    """
    Estimate total trading fees for entry and exit.

    Args:
        entry_amount_usd: USD value at entry
        exit_amount_usd: USD value at exit (approximate TP, or entry amount for estimation)

    Returns:
        {
            "entry_fee_usd": float,
            "exit_fee_usd": float,
            "total_fee_usd": float,
            "entry_fee_pct": float,
            "exit_fee_pct": float,
        }
    """
    entry_fee_usd = entry_amount_usd * (ENTRY_FEE_PCT / 100.0)
    exit_fee_usd = exit_amount_usd * (EXIT_FEE_PCT / 100.0)
    total_fee_usd = entry_fee_usd + exit_fee_usd

    return {
        "entry_fee_usd": round(entry_fee_usd, 4),
        "exit_fee_usd": round(exit_fee_usd, 4),
        "total_fee_usd": round(total_fee_usd, 4),
        "entry_fee_pct": ENTRY_FEE_PCT,
        "exit_fee_pct": EXIT_FEE_PCT,
    }


def estimate_slippage_pct(symbol: str, tier: int) -> float:
    """
    Estimate slippage percentage for a symbol based on tier.

    Args:
        symbol: Crypto symbol
        tier: Symbol tier (1, 2, or 3)

    Returns:
        Slippage as percentage (e.g., 0.05 = 0.05%)
    """
    # Use tier-based slippage, with minimum 0.05% even for Tier 1
    return max(0.05, SLIPPAGE_BY_TIER.get(tier, 0.20))


def compute_roundtrip_cost_pct(
    symbol: str,
    tier: int,
    include_spread: bool = True,
) -> Dict[str, float]:
    """
    Compute total roundtrip cost as percentage and in basis points.

    Roundtrip = Entry Fee + Exit Fee + Slippage + (Spread if included)

    Args:
        symbol: Crypto symbol
        tier: Symbol tier (1, 2, or 3)
        include_spread: Whether to include spread in cost calculation

    Returns:
        {
            "spread_bps": int,
            "slippage_pct": float,
            "entry_fee_pct": float,
            "exit_fee_pct": float,
            "estimated_roundtrip_cost_pct": float,
            "estimated_roundtrip_cost_bps": int,
        }
    """
    spread_bps = calculate_spread_bps(symbol)
    slippage_pct = estimate_slippage_pct(symbol, tier)

    # Convert spread from bps to percentage
    spread_pct = spread_bps / 100.0  # 8 bps = 0.08%

    # Roundtrip cost = entry fee + exit fee + slippage
    # Spread is additional cost but often quoted separately
    roundtrip_pct = ENTRY_FEE_PCT + EXIT_FEE_PCT + slippage_pct

    # If including spread, add it to roundtrip
    if include_spread:
        roundtrip_pct += spread_pct

    # Convert to basis points (1 bp = 0.01%)
    roundtrip_bps = int(roundtrip_pct * 100)

    return {
        "spread_bps": spread_bps,
        "spread_pct": round(spread_pct, 4),
        "slippage_pct": round(slippage_pct, 4),
        "entry_fee_pct": ENTRY_FEE_PCT,
        "exit_fee_pct": EXIT_FEE_PCT,
        "estimated_roundtrip_cost_pct": round(roundtrip_pct, 4),
        "estimated_roundtrip_cost_bps": roundtrip_bps,
    }


def estimate_net_rr(gross_rr: float, roundtrip_cost_pct: float) -> float:
    """
    Estimate net R/R after costs.

    Net R/R = Gross R/R - Roundtrip Cost %

    Example: Gross R/R = 1.5:1, Cost = 0.25% → Net R/R ≈ 1.475:1

    Args:
        gross_rr: Gross risk/reward ratio (e.g., 1.5 for 1.5:1)
        roundtrip_cost_pct: Total roundtrip cost as percentage

    Returns:
        Net R/R ratio
    """
    if gross_rr <= 0:
        return 0.0

    # Simple approximation: subtract cost % from RR
    # More precise: net_reward = gross_reward - cost, then divide by risk
    # Simplified: net_rr = gross_rr - (cost_pct / 100)
    net_rr = gross_rr - (roundtrip_cost_pct / 100.0)

    # Ensure non-negative
    return max(0.0, round(net_rr, 4))
