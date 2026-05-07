#!/usr/bin/env python3
"""
Complete Railway validation test for data_quality protection
Tests 10 symbols: BTC, ETH, SOL, TON, MKR, NEAR, OP, ICP, FIL, ARB
"""

import httpx
import json
from typing import Dict, Any

RAILWAY_URL = "https://swing-analyser-production.up.railway.app"

TEST_SYMBOLS = [
    # Tier 1 (should be OK)
    "BTC",
    "ETH",
    "SOL",
    # Suspects (should be BLOCKED or WARNING)
    "TON",
    "MKR",
    "NEAR",
    "OP",
    "ICP",
    "FIL",
    "ARB",
]

def test_symbol(symbol: str) -> Dict[str, Any]:
    """Test a single symbol on Railway"""
    try:
        url = f"{RAILWAY_URL}/api/crypto/scalp/analyze/{symbol}"
        with httpx.Client(timeout=10) as client:
            r = client.get(url)

            result = {"http_status": r.status_code, "symbol": symbol}

            if r.status_code == 200:
                data = r.json()
                result["data_status"] = data.get("data_status", "MISSING")
                result["snapshot_price"] = data.get("snapshot_price", "MISSING")
                result["intraday_last_close"] = data.get("intraday_last_close", "MISSING")
                result["price_difference_pct"] = data.get("price_difference_pct", "MISSING")
                result["price_suspect"] = data.get("price_suspect", "MISSING")
                result["data_quality_status"] = data.get("data_quality_status", "MISSING")
                result["data_quality_blocked"] = data.get("data_quality_blocked", "MISSING")
                result["paper_allowed"] = data.get("paper_allowed", "MISSING")
                result["signal_strength"] = data.get("signal_strength", "MISSING")
                result["blocked_reasons"] = data.get("blocked_reasons", [])
                result["signal_warnings"] = data.get("signal_warnings", [])
                result["scalp_execution_authorized"] = data.get("scalp_execution_authorized", "MISSING")
            else:
                result["error"] = f"HTTP {r.status_code}"

            return result
    except Exception as e:
        return {"http_status": "EXCEPTION", "symbol": symbol, "error": str(e)[:50]}

def main():
    print("\n" + "=" * 160)
    print("RAILWAY VALIDATION - DATA QUALITY PROTECTION")
    print("=" * 160 + "\n")

    results = []
    print("Testing symbols...")
    for symbol in TEST_SYMBOLS:
        result = test_symbol(symbol)
        results.append(result)
        status = "[OK]" if result.get("http_status") == 200 else "[FAIL]"
        print(f"  {status} {symbol}")

    print("\n" + "=" * 160)
    print("SUMMARY TABLE")
    print("=" * 160 + "\n")

    print(f"{'Symbol':<8} {'HTTP':<6} {'Quality Status':<18} {'Blocked':<10} {'Paper':<10} {'Signal':<12}")
    print("-" * 160)

    for r in results:
        symbol = r.get("symbol", "?")
        http_status = str(r.get("http_status", "?"))
        quality = str(r.get("data_quality_status", "MISSING"))
        blocked = str(r.get("data_quality_blocked", "MISSING"))
        paper = str(r.get("paper_allowed", "MISSING"))
        signal = str(r.get("signal_strength", "MISSING"))

        print(f"{symbol:<8} {http_status:<6} {quality:<18} {blocked:<10} {paper:<10} {signal:<12}")

    print("\n" + "=" * 160)
    print("DETAILED RESULTS")
    print("=" * 160)

    for r in results:
        symbol = r.get("symbol")
        print(f"\n{symbol}:")
        print(f"  HTTP Status: {r.get('http_status')}")

        if r.get('http_status') == 200:
            print(f"  Prices:")
            print(f"    snapshot_price: {r.get('snapshot_price')}")
            print(f"    intraday_last_close: {r.get('intraday_last_close')}")
            print(f"    price_difference_pct: {r.get('price_difference_pct')}%")
            print(f"    price_suspect: {r.get('price_suspect')}")

            print(f"  Data Quality:")
            print(f"    data_quality_status: {r.get('data_quality_status')}")
            print(f"    data_quality_blocked: {r.get('data_quality_blocked')}")

            print(f"  Trading:")
            print(f"    paper_allowed: {r.get('paper_allowed')}")
            print(f"    signal_strength: {r.get('signal_strength')}")
            print(f"    scalp_execution_authorized: {r.get('scalp_execution_authorized')}")

            blocked = r.get('blocked_reasons', [])
            if blocked:
                print(f"  Blocked Reasons:")
                for reason in blocked:
                    print(f"    - {reason}")

            warnings = r.get('signal_warnings', [])
            if warnings:
                print(f"  Warnings:")
                for warning in warnings:
                    print(f"    - {warning}")
        else:
            print(f"  Error: {r.get('error')}")

    print("\n" + "=" * 160)
    print("VALIDATION CHECKS")
    print("=" * 160)

    successful = sum(1 for r in results if r.get("http_status") == 200)
    print(f"✓ HTTP 200 responses: {successful}/{len(TEST_SYMBOLS)}")

    # Check Tier 1
    tier1 = results[:3]
    tier1_ok = all(r.get("data_quality_status") == "OK" for r in tier1 if r.get("http_status") == 200)
    print(f"✓ Tier 1 (BTC/ETH/SOL) data_quality_status = OK: {tier1_ok}")

    # Check suspects
    suspects = results[3:5]  # TON, MKR
    suspects_blocked = all(r.get("data_quality_blocked") == True for r in suspects if r.get("http_status") == 200)
    print(f"✓ Suspects (TON/MKR) data_quality_blocked = true: {suspects_blocked}")

    # Check no Real execution
    all_not_real = all(r.get("scalp_execution_authorized") == False for r in results if r.get("http_status") == 200)
    print(f"✓ All symbols have scalp_execution_authorized = false: {all_not_real}")

    print("\n" + "=" * 160)

if __name__ == "__main__":
    main()
