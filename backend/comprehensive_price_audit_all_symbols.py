#!/usr/bin/env python3
"""
COMPREHENSIVE PRICE AUDIT: ALL CRYPTO SCALP SYMBOLS
Tests all 37 symbols in the Crypto Scalp universe against multiple providers.
Creates detailed comparison tables for all data.
"""

import json
import httpx
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# ============================================================================
# SETUP
# ============================================================================

RAILWAY_URL = "https://swing-analyser-production.up.railway.app"

# All Crypto Scalp symbols
SCALP_TIER1 = ["BTC", "ETH", "SOL", "BNB", "XRP"]
SCALP_TIER2 = ["LINK", "AVAX", "DOGE", "ADA", "LTC", "BCH", "DOT", "ATOM",
               "NEAR", "SUI", "APT", "INJ", "OP", "ARB", "UNI", "AAVE", "MKR",
               "FIL", "ICP", "SEI", "TON", "POL"]
SCALP_TIER3 = ["HBAR", "RENDER", "ONDO", "FET", "AR", "TIA", "JUP", "WIF", "PENDLE", "DYDX"]

ALL_SYMBOLS = SCALP_TIER1 + SCALP_TIER2 + SCALP_TIER3

# Crypto universe (official symbols available in system)
CRYPTO_UNIVERSE_SYMBOLS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE", "TON", "LINK",
    "DOT", "POL", "LTC", "BCH", "UNI", "APT", "NEAR", "ICP", "FIL", "ATOM",
    "INJ", "ARB", "OP", "SUI", "SEI", "AAVE", "MKR"
]

# Test symbols: Start with all in CRYPTO_UNIVERSE, plus any Tier 3 if available
TEST_SYMBOLS = CRYPTO_UNIVERSE_SYMBOLS.copy()

print(f"[AUDIT] Total Crypto Scalp universe: 37 symbols (Tier 1:{len(SCALP_TIER1)} + Tier 2:{len(SCALP_TIER2)} + Tier 3:{len(SCALP_TIER3)})")
print(f"[AUDIT] Testing: {len(TEST_SYMBOLS)} symbols from official CRYPTO_UNIVERSE")
print(f"[AUDIT] Not in universe yet: {set(ALL_SYMBOLS) - set(TEST_SYMBOLS)}")

# ============================================================================
# SECTION 1: TEST ALL SYMBOLS ON RAILWAY
# ============================================================================

def test_railway_all_symbols():
    """Test all symbols on Railway Crypto Scalp API"""
    print("\n" + "=" * 140)
    print("SECTION 1: RAILWAY CRYPTO SCALP - ALL SYMBOLS")
    print("=" * 140 + "\n")

    results = {}
    successful = 0
    failed = 0

    for i, symbol in enumerate(TEST_SYMBOLS, 1):
        try:
            url = f"{RAILWAY_URL}/api/crypto/scalp/analyze/{symbol}"
            with httpx.Client(timeout=10) as client:
                r = client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    results[symbol] = {
                        "tier": get_tier(symbol),
                        "http_status": 200,
                        "displayed_price": data.get("displayed_price"),
                        "snapshot_price": data.get("snapshot_price"),
                        "intraday_last_close": data.get("intraday_last_close"),
                        "price_source": data.get("price_source"),
                        "price_timestamp": data.get("price_timestamp"),
                        "price_suspect": data.get("price_suspect"),
                        "price_difference_pct": data.get("price_difference_pct"),
                        "data_status": data.get("data_status"),
                        "long_score": data.get("long_score"),
                        "short_score": data.get("short_score"),
                        "scalp_grade": data.get("scalp_grade"),
                    }
                    successful += 1
                else:
                    results[symbol] = {"http_status": r.status_code, "error": "Failed"}
                    failed += 1
        except Exception as e:
            results[symbol] = {"error": str(e)}
            failed += 1

        # Progress indicator
        if i % 5 == 0:
            print(f"[Progress] {i}/{len(TEST_SYMBOLS)} symbols tested")
            time.sleep(0.2)

    # Print summary
    print(f"\n[Summary] Successful: {successful}/{len(TEST_SYMBOLS)}")
    print(f"[Summary] Failed: {failed}/{len(TEST_SYMBOLS)}")

    # Print detailed table
    print("\n" + "=" * 140)
    print("DETAILED RESULTS TABLE")
    print("=" * 140)

    print(f"{'Symbol':<8} {'Tier':<6} {'Status':<12} {'Snapshot':<15} {'Intraday':<15} {'Diverge %':<12} {'Suspect':<8} {'Grade':<10}")
    print("-" * 140)

    for symbol in sorted(TEST_SYMBOLS):
        data = results.get(symbol, {})
        if data.get("http_status") == 200:
            snapshot = data.get("displayed_price") or "N/A"
            intraday = data.get("intraday_last_close") or "N/A"
            diverge = data.get("price_difference_pct") or "N/A"
            suspect = "YES" if data.get("price_suspect") else "NO"
            grade = data.get("scalp_grade") or "N/A"
            status = data.get("data_status", "UNKNOWN")

            print(f"{symbol:<8} {get_tier(symbol):<6} {status:<12} {str(snapshot):<15} {str(intraday):<15} {str(diverge):<12} {suspect:<8} {str(grade):<10}")
        else:
            print(f"{symbol:<8} {get_tier(symbol):<6} ERROR")

    return results

# ============================================================================
# SECTION 2: IDENTIFY SUSPECT SYMBOLS
# ============================================================================

def identify_suspects(results):
    """Identify all symbols with price issues"""
    print("\n" + "=" * 140)
    print("SECTION 2: SUSPECT SYMBOLS ANALYSIS")
    print("=" * 140 + "\n")

    suspects = []
    for symbol, data in results.items():
        if data.get("http_status") == 200:
            diverge = data.get("price_difference_pct")
            suspect = data.get("price_suspect")
            if suspect or (diverge and diverge > 5):
                suspects.append({
                    "symbol": symbol,
                    "tier": get_tier(symbol),
                    "divergence_pct": diverge,
                    "price_suspect_flag": suspect,
                    "snapshot": data.get("displayed_price"),
                    "intraday": data.get("intraday_last_close"),
                })

    if suspects:
        print(f"[FOUND] {len(suspects)} symbols with price divergence > 5%\n")
        print(f"{'Symbol':<8} {'Tier':<6} {'Divergence %':<15} {'Snapshot':<15} {'Intraday':<15} {'Suspect Flag':<12}")
        print("-" * 140)

        for s in sorted(suspects, key=lambda x: x["divergence_pct"] or 0, reverse=True):
            print(f"{s['symbol']:<8} {s['tier']:<6} {str(s['divergence_pct']):<15} {str(s['snapshot']):<15} {str(s['intraday']):<15} {str(s['price_suspect_flag']):<12}")
    else:
        print("[INFO] No suspect symbols found (all within 5% divergence)")

    return suspects

# ============================================================================
# SECTION 3: DETAILED ANALYSIS OF SUSPECTS
# ============================================================================

def deep_dive_suspects(suspects, results):
    """Detailed analysis of each suspect symbol"""
    if not suspects:
        return

    print("\n" + "=" * 140)
    print("SECTION 3: DEEP DIVE ANALYSIS OF SUSPECT SYMBOLS")
    print("=" * 140 + "\n")

    for suspect in suspects:
        symbol = suspect["symbol"]
        data = results[symbol]

        print(f"\n{symbol} (Tier {suspect['tier']}):")
        print("-" * 80)
        print(f"  Snapshot (Displayed):    {suspect['snapshot']}")
        print(f"  Intraday (Last Close):   {suspect['intraday']}")
        print(f"  Divergence:              {suspect['divergence_pct']}%")
        print(f"  Price Suspect Flag:      {suspect['price_suspect_flag']}")
        print(f"  Data Status:             {data.get('data_status')}")
        print(f"  Price Source:            {data.get('price_source')}")
        print(f"  Timestamp:               {data.get('price_timestamp')}")
        print(f"  Long Score:              {data.get('long_score')}")
        print(f"  Short Score:             {data.get('short_score')}")
        print(f"  Grade:                   {data.get('scalp_grade')}")

# ============================================================================
# SECTION 4: COINGECKO REFERENCE COMPARISON
# ============================================================================

def get_coingecko_references():
    """Get reference prices from CoinGecko for all symbols"""
    print("\n" + "=" * 140)
    print("SECTION 4: COINGECKO REFERENCE PRICES")
    print("=" * 140 + "\n")

    # CoinGecko IDs mapping
    cg_mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "AVAX": "avalanche-2",
        "DOGE": "dogecoin",
        "TON": "the-open-network",
        "LINK": "chainlink",
        "DOT": "polkadot",
        "POL": "polygon-ecosystem-token",
        "LTC": "litecoin",
        "BCH": "bitcoin-cash",
        "UNI": "uniswap",
        "APT": "aptos",
        "NEAR": "near",
        "ICP": "internet-computer",
        "FIL": "filecoin",
        "ATOM": "cosmos",
        "INJ": "injective-protocol",
        "ARB": "arbitrum",
        "OP": "optimism",
        "SUI": "sui",
        "SEI": "sei-network",
        "AAVE": "aave",
        "MKR": "maker",
    }

    results = {}
    ids = ",".join([cg_mapping[s] for s in TEST_SYMBOLS if s in cg_mapping])

    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"ids": ids, "vs_currencies": "usd"})
            r.raise_for_status()
            data = r.json()

            for symbol in TEST_SYMBOLS:
                if symbol in cg_mapping:
                    cg_id = cg_mapping[symbol]
                    price = data.get(cg_id, {}).get("usd")
                    results[symbol] = {"coingecko_price": price}

        print(f"{'Symbol':<8} {'CoinGecko Price':<20} {'Status':<20}")
        print("-" * 60)
        for symbol in sorted(TEST_SYMBOLS):
            if symbol in results:
                price = results[symbol].get("coingecko_price") or "ERROR"
                status = "OK" if price != "ERROR" else "FAILED"
                print(f"{symbol:<8} {str(price):<20} {status:<20}")

    except Exception as e:
        print(f"[ERROR] CoinGecko fetch failed: {e}")

    return results

# ============================================================================
# SECTION 5: COMPARISON TABLE
# ============================================================================

def create_comparison_table(railway_results, cg_results):
    """Create comprehensive comparison table"""
    print("\n" + "=" * 140)
    print("SECTION 5: COMPREHENSIVE COMPARISON TABLE")
    print("=" * 140 + "\n")

    print(f"{'Symbol':<8} {'Tier':<6} {'Railway Snap':<15} {'Railway Intra':<15} {'CoinGecko':<15} {'Div %':<12} {'Status':<15}")
    print("-" * 140)

    for symbol in sorted(TEST_SYMBOLS):
        data = railway_results.get(symbol, {})
        cg_data = cg_results.get(symbol, {})

        if data.get("http_status") == 200:
            snapshot = data.get("displayed_price") or "N/A"
            intraday = data.get("intraday_last_close") or "N/A"
            coingecko = cg_data.get("coingecko_price") or "N/A"
            diverge = data.get("price_difference_pct") or 0
            tier = get_tier(symbol)

            # Determine status
            if data.get("price_suspect"):
                status = "SUSPECT"
            elif isinstance(diverge, (int, float)) and diverge > 5:
                status = "WARN"
            else:
                status = "OK"

            print(f"{symbol:<8} {tier:<6} {str(snapshot):<15} {str(intraday):<15} {str(coingecko):<15} {str(diverge):<12} {status:<15}")

# ============================================================================
# HELPERS
# ============================================================================

def get_tier(symbol):
    """Get tier for symbol"""
    if symbol in SCALP_TIER1:
        return 1
    elif symbol in SCALP_TIER2:
        return 2
    elif symbol in SCALP_TIER3:
        return 3
    else:
        return 0

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 140)
    print("COMPREHENSIVE PRICE AUDIT: ALL CRYPTO SCALP SYMBOLS")
    print("=" * 140)
    print(f"[START] {datetime.now(timezone.utc).isoformat()}")

    # Section 1: Test all symbols
    railway_results = test_railway_all_symbols()

    # Section 2: Identify suspects
    suspects = identify_suspects(railway_results)

    # Section 3: Deep dive
    deep_dive_suspects(suspects, railway_results)

    # Section 4: Get CoinGecko reference
    time.sleep(1)  # Rate limit
    cg_results = get_coingecko_references()

    # Section 5: Comparison table
    create_comparison_table(railway_results, cg_results)

    # Summary
    print("\n" + "=" * 140)
    print("AUDIT SUMMARY")
    print("=" * 140)
    successful = sum(1 for d in railway_results.values() if d.get("http_status") == 200)
    print(f"[TOTAL] {successful}/{len(TEST_SYMBOLS)} symbols successfully analyzed")
    print(f"[SUSPECTS] {len(suspects)} symbols with divergence > 5%")
    if suspects:
        suspect_names = ", ".join([s["symbol"] for s in suspects])
        print(f"[PROBLEM SYMBOLS] {suspect_names}")

    print(f"\n[END] {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()
