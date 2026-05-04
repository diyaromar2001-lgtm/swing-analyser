"""
Crypto Edge Fallback Search System

When exact edge is INSUFFICIENT_SAMPLE, search hierarchically for context:
  Tier 1: Same ticker, target strategy, grades A/A+
  Tier 2: Same sector, target strategy, all 27 cryptos
  Tier 3: Market-wide target strategy (Phase 1 tradable universe only)
  Tier 4: Same sector, any strategy with VALID_EDGE+

Fallback returns only VALID_EDGE or STRONG_EDGE (no weak edges).
Cache: 1 hour TTL (lighter than 24h edge cache).
"""

from __future__ import annotations

import time as _time
from typing import Dict, Optional

from crypto_data import crypto_sector, available_crypto_symbols, CRYPTO_BY_SYMBOL
from crypto_edge import get_cached_crypto_edge
from crypto_universe import is_tradable_crypto

# Cache: 1 hour
_fallback_cache: Dict[str, dict] = {}
_FALLBACK_TTL = 3_600  # 1 hour


def find_edge_fallback(
    symbol: str,
    target_strategy_key: Optional[str] = None,
    period_months: int = 24,
) -> Optional[Dict]:
    """
    Search for edge in fallback tiers when exact edge is INSUFFICIENT_SAMPLE.
    Returns only VALID_EDGE or STRONG_EDGE fallbacks (no weak edges).

    Tier 1: Same ticker, target strategy, VALID_EDGE+
    Tier 2: Same sector, target strategy, all 27 cryptos
    Tier 3: Market-wide target strategy (Phase 1 universe only = 7 symbols)
    Tier 4: Same sector, any strategy with VALID_EDGE+ (all 27 cryptos)

    Args:
        symbol: Crypto symbol (BTC, ETH, SOL, etc.)
        target_strategy_key: Strategy key to search for (optional, tries all strategies if None)
        period_months: Backtest period (default 24)

    Returns:
        Dict with fallback tier, symbol, strategy, edge status, and explanation
        or None if no good fallback found
    """
    symbol = symbol.upper()
    now = _time.time()

    # Check cache first (1h TTL)
    cache_key = f"{symbol}:{target_strategy_key}:{period_months}"
    cached = _fallback_cache.get(cache_key)
    if cached and (now - cached.get("ts", 0)) < _FALLBACK_TTL:
        return cached.get("data")

    result = None

    # Tier 1: Same ticker, target strategy
    if target_strategy_key:
        edge = get_cached_crypto_edge(symbol)
        if edge and edge.get("all_strategies"):
            for strat in edge["all_strategies"]:
                if (
                    strat.get("key") == target_strategy_key
                    and strat.get("edge_status") in ("VALID_EDGE", "STRONG_EDGE")
                ):
                    result = {
                        "fallback_tier": 1,
                        "fallback_strategy_key": strat["key"],
                        "fallback_symbol": symbol,
                        "fallback_edge_status": strat["edge_status"],
                        "fallback_source": "exact_strategy",
                        "explanation": f"{symbol} has {strat['edge_status']} on same strategy {strat.get('name', '')}",
                    }
                    break

    # Tier 2: Same sector, target strategy (search all 27 cryptos)
    if not result and target_strategy_key:
        sector = crypto_sector(symbol)
        if sector:
            all_symbols = available_crypto_symbols()
            for sym in all_symbols:
                if sym == symbol:
                    continue  # Already checked in Tier 1
                if crypto_sector(sym) != sector:
                    continue  # Different sector
                edge = get_cached_crypto_edge(sym)
                if not edge or not edge.get("all_strategies"):
                    continue
                for strat in edge["all_strategies"]:
                    if (
                        strat.get("key") == target_strategy_key
                        and strat.get("edge_status") in ("VALID_EDGE", "STRONG_EDGE")
                    ):
                        result = {
                            "fallback_tier": 2,
                            "fallback_strategy_key": strat["key"],
                            "fallback_symbol": sym,
                            "fallback_edge_status": strat["edge_status"],
                            "fallback_source": f"sector_{sector}",
                            "explanation": f"Same strategy {strat.get('name', '')} shows {strat['edge_status']} in {sym} ({sector})",
                        }
                        break
                if result:
                    break

    # Tier 3: Market-wide target strategy (Phase 1 tradable universe only)
    if not result and target_strategy_key:
        tradable_symbols = [s for s in available_crypto_symbols() if is_tradable_crypto(s)]
        for sym in tradable_symbols:
            if sym == symbol:
                continue
            edge = get_cached_crypto_edge(sym)
            if not edge or not edge.get("all_strategies"):
                continue
            for strat in edge["all_strategies"]:
                if (
                    strat.get("key") == target_strategy_key
                    and strat.get("edge_status") in ("VALID_EDGE", "STRONG_EDGE")
                ):
                    result = {
                        "fallback_tier": 3,
                        "fallback_strategy_key": strat["key"],
                        "fallback_symbol": sym,
                        "fallback_edge_status": strat["edge_status"],
                        "fallback_source": "market_wide",
                        "explanation": f"Strategy {strat.get('name', '')} shows {strat['edge_status']} across Phase 1 universe in {sym}",
                    }
                    break
            if result:
                break

    # Tier 4: Same sector, any strategy with VALID_EDGE+ (all 27 cryptos)
    if not result:
        sector = crypto_sector(symbol)
        if sector:
            all_symbols = available_crypto_symbols()
            for sym in all_symbols:
                if sym == symbol:
                    continue
                if crypto_sector(sym) != sector:
                    continue
                edge = get_cached_crypto_edge(sym)
                if not edge or not edge.get("all_strategies"):
                    continue
                # Find first VALID_EDGE or STRONG_EDGE strategy
                for strat in edge["all_strategies"]:
                    if strat.get("edge_status") in ("VALID_EDGE", "STRONG_EDGE"):
                        result = {
                            "fallback_tier": 4,
                            "fallback_strategy_key": strat["key"],
                            "fallback_symbol": sym,
                            "fallback_edge_status": strat["edge_status"],
                            "fallback_source": f"sector_{sector}_any",
                            "explanation": f"{sym} ({sector}) shows {strat['edge_status']} with {strat.get('name', '')} — similar sector context",
                        }
                        break
                if result:
                    break

    # Cache the result (even if None, to avoid repeated searches)
    _fallback_cache[cache_key] = {
        "data": result,
        "ts": now,
    }

    return result


def clear_fallback_cache(symbol: Optional[str] = None) -> None:
    """Clear fallback cache (all or specific symbol)."""
    if symbol:
        symbol = symbol.upper()
        keys_to_remove = [k for k in _fallback_cache.keys() if k.startswith(symbol + ":")]
        for k in keys_to_remove:
            _fallback_cache.pop(k, None)
    else:
        _fallback_cache.clear()


def get_cached_fallback(
    symbol: str,
    target_strategy_key: Optional[str] = None,
    period_months: int = 24,
) -> Optional[Dict]:
    """Get fallback from cache only (no computation)."""
    cache_key = f"{symbol.upper()}:{target_strategy_key}:{period_months}"
    cached = _fallback_cache.get(cache_key)
    return cached.get("data") if cached else None
