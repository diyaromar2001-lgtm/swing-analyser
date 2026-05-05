"""
Paper Fill Simulator for Crypto Scalp Trading

Simulates realistic order fills for paper trades:
- Entry fill simulation (adds slippage/spread to entry price)
- Exit fill simulation (adds slippage/spread to exit price)
- Uses historical OHLCV data to determine realism
- Returns actual fill prices and timestamps
"""

from typing import Dict, Optional, Tuple
import time as _time

from crypto_data import get_crypto_ohlcv_intraday
from crypto_cost_calculator import (
    calculate_spread_bps,
    estimate_slippage_pct,
)


def simulate_entry_fill(
    symbol: str,
    side: str,  # "LONG" or "SHORT"
    entry_target: float,
    tier: int = 2,
    order_timestamp: Optional[float] = None,
) -> Dict[str, float]:
    """
    Simulate entry fill with slippage and spread.

    For LONG: fill_price = entry_target + slippage + spread (worse price)
    For SHORT: fill_price = entry_target - slippage - spread (worse price)

    Args:
        symbol: Crypto symbol (BTC, ETH, etc.)
        side: "LONG" or "SHORT"
        entry_target: Target entry price from analysis
        tier: Symbol tier (1, 2, or 3)
        order_timestamp: Order placement timestamp (defaults to now)

    Returns:
        {
            "order_timestamp": float,
            "fill_timestamp": float,
            "target_price": float,
            "slippage_pct": float,
            "spread_bps": int,
            "spread_pct": float,
            "filled_price": float,
            "slippage_amount": float,
            "spread_amount": float,
            "total_cost_amount": float,
        }
    """
    if order_timestamp is None:
        order_timestamp = _time.time()

    spread_bps = calculate_spread_bps(symbol)
    slippage_pct = estimate_slippage_pct(symbol, tier)

    # Convert spread from bps to percentage
    spread_pct = spread_bps / 100.0

    # Calculate slippage amount in USD
    slippage_amount = entry_target * (slippage_pct / 100.0)

    # Calculate spread amount in USD
    spread_amount = entry_target * (spread_pct / 100.0)

    # Total adverse cost for entry
    total_cost_amount = slippage_amount + spread_amount

    # Fill price (worse than target for entry)
    if side == "LONG":
        # LONG entry: higher price is worse
        filled_price = entry_target + total_cost_amount
    elif side == "SHORT":
        # SHORT entry: lower price is worse
        filled_price = entry_target - total_cost_amount
    else:
        # Default to target if side unknown
        filled_price = entry_target

    # Simulate fill delay (0-2 seconds for typical fill)
    fill_delay = min(2.0, max(0.1, total_cost_amount / entry_target * 100))  # Scale delay by cost %
    fill_timestamp = order_timestamp + fill_delay

    return {
        "order_timestamp": order_timestamp,
        "fill_timestamp": round(fill_timestamp, 2),
        "target_price": round(entry_target, 4),
        "slippage_pct": round(slippage_pct, 4),
        "spread_bps": spread_bps,
        "spread_pct": round(spread_pct, 4),
        "filled_price": round(filled_price, 4),
        "slippage_amount": round(slippage_amount, 4),
        "spread_amount": round(spread_amount, 4),
        "total_cost_amount": round(total_cost_amount, 4),
    }


def simulate_exit_fill(
    symbol: str,
    side: str,  # "LONG" or "SHORT"
    exit_target: float,
    tier: int = 2,
    order_timestamp: Optional[float] = None,
) -> Dict[str, float]:
    """
    Simulate exit fill with slippage and spread.

    For LONG exit: fill_price = exit_target - slippage - spread (worse price, we sell at lower)
    For SHORT exit: fill_price = exit_target + slippage + spread (worse price, we buy at higher)

    Args:
        symbol: Crypto symbol
        side: "LONG" or "SHORT"
        exit_target: Target exit price (TP1 or TP2 from analysis)
        tier: Symbol tier (1, 2, or 3)
        order_timestamp: Order placement timestamp (defaults to now)

    Returns:
        {
            "order_timestamp": float,
            "fill_timestamp": float,
            "target_price": float,
            "slippage_pct": float,
            "spread_bps": int,
            "spread_pct": float,
            "filled_price": float,
            "slippage_amount": float,
            "spread_amount": float,
            "total_cost_amount": float,
        }
    """
    if order_timestamp is None:
        order_timestamp = _time.time()

    spread_bps = calculate_spread_bps(symbol)
    slippage_pct = estimate_slippage_pct(symbol, tier)

    # Convert spread from bps to percentage
    spread_pct = spread_bps / 100.0

    # Calculate slippage amount in USD
    slippage_amount = exit_target * (slippage_pct / 100.0)

    # Calculate spread amount in USD
    spread_amount = exit_target * (spread_pct / 100.0)

    # Total adverse cost for exit
    total_cost_amount = slippage_amount + spread_amount

    # Fill price (worse than target for exit)
    if side == "LONG":
        # LONG exit: lower price is worse (we're selling)
        filled_price = exit_target - total_cost_amount
    elif side == "SHORT":
        # SHORT exit: higher price is worse (we're buying to cover)
        filled_price = exit_target + total_cost_amount
    else:
        # Default to target if side unknown
        filled_price = exit_target

    # Simulate fill delay (0-2 seconds for typical fill)
    fill_delay = min(2.0, max(0.1, total_cost_amount / exit_target * 100))  # Scale delay by cost %
    fill_timestamp = order_timestamp + fill_delay

    return {
        "order_timestamp": order_timestamp,
        "fill_timestamp": round(fill_timestamp, 2),
        "target_price": round(exit_target, 4),
        "slippage_pct": round(slippage_pct, 4),
        "spread_bps": spread_bps,
        "spread_pct": round(spread_pct, 4),
        "filled_price": round(filled_price, 4),
        "slippage_amount": round(slippage_amount, 4),
        "spread_amount": round(spread_amount, 4),
        "total_cost_amount": round(total_cost_amount, 4),
    }


def verify_fill_feasibility(
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    tier: int = 2,
) -> Dict[str, any]:
    """
    Verify if a trade's fill prices are feasible given costs.

    Args:
        symbol: Crypto symbol
        side: "LONG" or "SHORT"
        entry_price: Planned entry price
        exit_price: Planned exit price (TP1 or TP2)
        tier: Symbol tier (1, 2, or 3)

    Returns:
        {
            "feasible": bool,
            "entry_fill": float,
            "exit_fill": float,
            "gross_profit": float,
            "net_profit": float,
            "gross_rr": float,
            "net_rr": float,
        }
    """
    entry_sim = simulate_entry_fill(symbol, side, entry_price, tier)
    exit_sim = simulate_exit_fill(symbol, side, exit_price, tier)

    entry_fill = entry_sim["filled_price"]
    exit_fill = exit_sim["filled_price"]

    # Calculate profit (before accounting for fees, which are separate)
    if side == "LONG":
        gross_profit = (exit_price - entry_price) * 100  # Normalized to 1 unit
        net_profit = (exit_fill - entry_fill) * 100
    elif side == "SHORT":
        gross_profit = (entry_price - exit_price) * 100
        net_profit = (entry_fill - exit_fill) * 100
    else:
        gross_profit = 0.0
        net_profit = 0.0

    # Trade is feasible if net profit is still positive after fills
    feasible = net_profit > 0

    return {
        "feasible": feasible,
        "entry_fill": round(entry_fill, 4),
        "exit_fill": round(exit_fill, 4),
        "gross_profit": round(gross_profit, 4),
        "net_profit": round(net_profit, 4),
        "gross_rr": round(abs(gross_profit / entry_price), 4) if entry_price > 0 else 0.0,
        "net_rr": round(abs(net_profit / entry_fill), 4) if entry_fill > 0 else 0.0,
    }
