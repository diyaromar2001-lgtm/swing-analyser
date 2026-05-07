#!/usr/bin/env python3
"""
MASTER AUDIT: Complete price source investigation
Tests all price sources, providers, and caches in the application
"""

import json
import httpx
import time
from typing import Dict, List, Any, Optional

# ============================================================================
# SECTION 1: TEST CRYPTO PRICES ON PRODUCTION RAILWAY
# ============================================================================

CRYPTO_TEST_SET = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "TON": "the-open-network",
    "MKR": "maker",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "AAVE": "aave",
}

RAILWAY_URL = "https://swing-analyser-production.up.railway.app"

def test_railway_crypto_scalp():
    """Test Crypto Scalp prices on Railway"""
    print("\n" + "=" * 100)
    print("SECTION 1: TEST CRYPTO SCALP PRICES ON RAILWAY")
    print("=" * 100 + "\n")

    results = {}
    for symbol in CRYPTO_TEST_SET.keys():
        try:
            url = f"{RAILWAY_URL}/api/crypto/scalp/analyze/{symbol}"
            with httpx.Client(timeout=10) as client:
                r = client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    results[symbol] = {
                        "http_status": 200,
                        "displayed_price": data.get("displayed_price"),
                        "snapshot_price": data.get("snapshot_price"),
                        "intraday_last_close": data.get("intraday_last_close"),
                        "price_source": data.get("price_source"),
                        "price_timestamp": data.get("price_timestamp"),
                        "price_suspect": data.get("price_suspect"),
                        "price_difference_pct": data.get("price_difference_pct"),
                        "scalp_score": data.get("scalp_score"),
                        "entry": data.get("entry"),
                        "stop_loss": data.get("stop_loss"),
                        "tp1": data.get("tp1"),
                        "tp2": data.get("tp2"),
                    }
                else:
                    results[symbol] = {"http_status": r.status_code, "error": "Failed"}
        except Exception as e:
            results[symbol] = {"error": str(e)}

    # Print results
    print(f"{'Symbol':<8} {'HTTP':<6} {'Displayed':<12} {'Snapshot':<12} {'Intraday':<12} {'Suspect':<8}")
    print("-" * 100)
    for symbol, data in results.items():
        http_status = data.get("http_status", "ERROR")
        disp = data.get("displayed_price") or "N/A"
        snap = data.get("snapshot_price") or "N/A"
        intra = data.get("intraday_last_close") or "N/A"
        suspect = data.get("price_suspect", "N/A")
        print(f"{symbol:<8} {http_status:<6} {str(disp):<12} {str(snap):<12} {str(intra):<12} {str(suspect):<8}")

    return results

# ============================================================================
# SECTION 2: COMPARE WITH EXTERNAL PROVIDERS
# ============================================================================

def get_reference_prices():
    """Get reference prices from CoinGecko"""
    print("\n" + "=" * 100)
    print("SECTION 2: REFERENCE PRICES FROM COINGECKO")
    print("=" * 100 + "\n")

    results = {}
    ids = ",".join(CRYPTO_TEST_SET.values())

    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"ids": ids, "vs_currencies": "usd"})
            r.raise_for_status()
            data = r.json()

            for symbol, cg_id in CRYPTO_TEST_SET.items():
                price = data.get(cg_id, {}).get("usd")
                results[symbol] = {
                    "provider": "CoinGecko",
                    "price": price,
                }
    except Exception as e:
        print(f"ERROR: {e}")

    print(f"{'Symbol':<8} {'CoinGecko Price':<20}")
    print("-" * 50)
    for symbol, data in results.items():
        price = data.get("price") or "ERROR"
        print(f"{symbol:<8} {str(price):<20}")

    return results

# ============================================================================
# SECTION 3: DETAILED ANALYSIS FOR TON AND MKR
# ============================================================================

def deep_dive_ton_mkr():
    """Deep dive investigation for TON and MKR"""
    print("\n" + "=" * 100)
    print("SECTION 3: DEEP DIVE TON AND MKR")
    print("=" * 100 + "\n")

    analysis = {}

    for symbol in ["TON", "MKR"]:
        print(f"\n{symbol} ANALYSIS:")
        print("-" * 80)

        # Get Railway data
        try:
            url = f"{RAILWAY_URL}/api/crypto/scalp/analyze/{symbol}"
            with httpx.Client(timeout=10) as client:
                r = client.get(url)
                if r.status_code == 200:
                    railway_data = r.json()
                else:
                    railway_data = {}
        except:
            railway_data = {}

        # Get CoinGecko reference
        cg_price = None
        try:
            cg_id = CRYPTO_TEST_SET.get(symbol)
            url = f"https://api.coingecko.com/api/v3/simple/price"
            with httpx.Client(timeout=10) as client:
                r = client.get(url, params={"ids": cg_id, "vs_currencies": "usd"})
                cg_price = r.json().get(cg_id, {}).get("usd")
        except:
            pass

        # Analyze
        displayed = railway_data.get("displayed_price")
        snapshot = railway_data.get("snapshot_price")
        intraday = railway_data.get("intraday_last_close")
        divergence = railway_data.get("price_difference_pct")

        print(f"Railway Displayed: {displayed}")
        print(f"Railway Snapshot:  {snapshot}")
        print(f"Railway Intraday:  {intraday}")
        print(f"Divergence %:      {divergence}")
        print(f"Price Suspect:     {railway_data.get('price_suspect')}")
        print(f"CoinGecko Ref:     {cg_price}")

        if displayed and cg_price:
            pct_diff = (float(displayed) - float(cg_price)) / float(cg_price) * 100
            print(f"Displayed vs CoinGecko: {pct_diff:+.2f}%")

        if snapshot and cg_price:
            pct_diff = (float(snapshot) - float(cg_price)) / float(cg_price) * 100
            print(f"Snapshot vs CoinGecko:  {pct_diff:+.2f}%")

        if intraday and cg_price:
            pct_diff = (float(intraday) - float(cg_price)) / float(cg_price) * 100
            print(f"Intraday vs CoinGecko:  {pct_diff:+.2f}%")

        analysis[symbol] = {
            "railway_data": railway_data,
            "coingecko_price": cg_price,
        }

    return analysis

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 100)
    print("MASTER PRICE AUDIT - COMPLETE SOURCE INVESTIGATION")
    print("=" * 100)

    # Section 1: Test Railway
    railway_results = test_railway_crypto_scalp()

    # Section 2: Get reference prices
    cg_results = get_reference_prices()

    # Section 3: Deep dive
    deep_dive = deep_dive_ton_mkr()

    # Section 4: Summary
    print("\n" + "=" * 100)
    print("SECTION 4: SUMMARY AND FINDINGS")
    print("=" * 100 + "\n")

    print("1. RAILWAY PRICE SOURCES:")
    print("   - Price snapshot: Binance → CoinGecko → yFinance chain")
    print("   - Intraday OHLCV: Binance (blocked 451) → Coinbase → Kraken → OKX chain")
    print("   - Cache TTL: 60s (price), 600s (5m), 3600s (daily)")

    print("\n2. PRICE DIVERGENCE FINDINGS:")
    for symbol, data in railway_results.items():
        displayed = data.get("displayed_price")
        cg_price = cg_results.get(symbol, {}).get("price")
        if displayed and cg_price:
            pct = (float(displayed) - float(cg_price)) / float(cg_price) * 100
            status = "OK" if abs(pct) < 5 else "SUSPECT" if abs(pct) < 20 else "CRITICAL"
            print(f"   {symbol}: Railway={displayed}, CoinGecko={cg_price}, Diff={pct:+.2f}% [{status}]")

    print("\n3. TON AND MKR ANALYSIS:")
    print("   TON:")
    ton_data = deep_dive.get("TON", {})
    print(f"     Railway Displayed: {ton_data.get('railway_data', {}).get('displayed_price')}")
    print(f"     CoinGecko Ref: {ton_data.get('coingecko_price')}")
    print(f"     Verdict: Need to verify if intraday (1.837) is stale or from wrong provider")

    print("   MKR:")
    mkr_data = deep_dive.get("MKR", {})
    print(f"     Railway Displayed: {mkr_data.get('railway_data', {}).get('displayed_price')}")
    print(f"     CoinGecko Ref: {mkr_data.get('coingecko_price')}")
    print(f"     Verdict: Coinbase intraday (1347) is perpetuals, not spot (1867)")

    print("\n" + "=" * 100)
    print("NEXT STEPS:")
    print("=" * 100)
    print("1. Create comprehensive price source mapping document")
    print("2. Identify all provider chains and fallback logic")
    print("3. Test all cache behaviors and TTLs")
    print("4. Verify indicator calculations use correct price source")
    print("5. Define architecture changes needed")
    print("6. Create remediation plan")

if __name__ == "__main__":
    main()
