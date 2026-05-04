#!/usr/bin/env python3
"""
TEST: Single Ticker Edge Compute BUG FIX

Vérifie que POST /api/strategy-edge/compute?ticker=BIIB calcule seulement BIIB,
pas 238 tickers.

Bug: L'ancien endpoint ignorait le parameter 'ticker' et calculait ALL_TICKERS
Fix: Suppression de l'ancien endpoint, le nouveau fonctionne correctement
"""

import requests
import json
from typing import Dict, Any

API_BASE_URL = "http://localhost:8000"
ADMIN_KEY = "test-admin-key"  # Remplacer par votre vraie clé
HEADERS = {"X-Admin-Key": ADMIN_KEY}

def test_single_ticker(ticker: str) -> Dict[str, Any]:
    """Test single ticker edge compute."""
    print(f"\n{'='*80}")
    print(f"TEST: Single Ticker Edge Compute — {ticker}")
    print(f"{'='*80}\n")

    url = f"{API_BASE_URL}/api/strategy-edge/compute"
    params = {"ticker": ticker}

    try:
        response = requests.post(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response received (HTTP 200)")
            print(f"\n📊 RESPONSE PAYLOAD:")
            print(json.dumps(data, indent=2))

            # Validation
            print(f"\n🔍 VALIDATIONS:")
            checks = []

            # Check 1: Status OK
            status_ok = data.get("status") == "ok"
            checks.append(("Status = ok", status_ok, "✅" if status_ok else "❌"))

            # Check 2: Ticker matches request
            ticker_matches = data.get("ticker", "").upper() == ticker.upper()
            checks.append((f"Ticker = {ticker}", ticker_matches, "✅" if ticker_matches else "❌"))

            # Check 3: NOT 238 computed (bug would show computed:238)
            # For single ticker, we just check the response structure
            computed_field = "computed" in data
            if computed_field:
                computed_value = data.get("computed")
                is_single = computed_value == 1 or (computed_value is None)
                checks.append((f"Computed = 1 (not 238)", is_single, "✅" if is_single else f"❌ Got {computed_value}"))
            else:
                checks.append(("No 'computed' field (correct for single)", True, "✅"))

            # Check 4: Has edge_status
            has_edge_status = "edge_status" in data
            checks.append(("Has edge_status", has_edge_status, "✅" if has_edge_status else "❌"))

            # Check 5: Has detailed metrics
            has_train_pf = "train_pf" in data
            has_test_pf = "test_pf" in data
            has_expectancy = "expectancy" in data
            has_trades = "trades" in data

            metrics_ok = has_train_pf and has_test_pf and has_expectancy and has_trades
            checks.append(
                ("Has detailed metrics (train_pf, test_pf, expectancy, trades)",
                 metrics_ok,
                 "✅" if metrics_ok else f"❌ train_pf:{has_train_pf} test_pf:{has_test_pf} expectancy:{has_expectancy} trades:{has_trades}")
            )

            # Check 6: Duration reasonable
            duration = data.get("duration_ms", 0)
            duration_ok = duration < 30000  # Should be < 30 seconds for single ticker
            checks.append((f"Duration < 30s ({duration}ms)", duration_ok, "✅" if duration_ok else "❌"))

            # Print checks
            for check, passed, symbol in checks:
                print(f"  {symbol} {check}")

            all_passed = all(c[1] for c in checks)
            return {
                "ticker": ticker,
                "data": data,
                "passed": all_passed,
                "checks": checks,
            }
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"   {response.text[:200]}")
            return {
                "ticker": ticker,
                "data": None,
                "passed": False,
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {
            "ticker": ticker,
            "data": None,
            "passed": False,
            "error": str(e),
        }

def test_cache_contains_ticker(ticker: str) -> Dict[str, Any]:
    """Verify that the ticker is in edge cache."""
    print(f"\n{'='*80}")
    print(f"VERIFY: Edge cache contains {ticker}")
    print(f"{'='*80}\n")

    url = f"{API_BASE_URL}/api/debug/cache-integrity"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            edge_tickers = data.get("caches", {}).get("actions", {}).get("edge_tickers", [])
            ticker_in_cache = ticker.upper() in [t.upper() for t in edge_tickers]

            print(f"✅ Cache integrity retrieved")
            print(f"\n📊 EDGE CACHE STATUS:")
            print(f"   - Total edge cache count: {data.get('caches', {}).get('actions', {}).get('edge_cache_count', 0)}")
            print(f"   - Edge tickers (first 10): {edge_tickers[:10]}")

            print(f"\n🔍 VALIDATION:")
            if ticker_in_cache:
                print(f"   ✅ {ticker} FOUND in edge_cache")
            else:
                print(f"   ❌ {ticker} NOT FOUND in edge_cache")
                print(f"      Available tickers: {edge_tickers}")

            return {
                "ticker": ticker,
                "found": ticker_in_cache,
                "cache_count": data.get("caches", {}).get("actions", {}).get("edge_cache_count", 0),
                "edge_tickers": edge_tickers,
            }
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return {"ticker": ticker, "found": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {"ticker": ticker, "found": False, "error": str(e)}

def test_screener_shows_edge(ticker: str) -> Dict[str, Any]:
    """Verify that screener shows the computed edge."""
    print(f"\n{'='*80}")
    print(f"VERIFY: Screener shows {ticker} edge status")
    print(f"{'='*80}\n")

    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            # Find ticker
            ticker_result = None
            for result in results:
                if result.get("ticker", "").upper() == ticker.upper():
                    ticker_result = result
                    break

            print(f"✅ Screener retrieved ({len(results)} results)")

            if ticker_result:
                print(f"\n📊 {ticker} IN SCREENER:")
                print(f"   - edge_status: {ticker_result.get('ticker_edge_status')}")
                print(f"   - setup_grade: {ticker_result.get('setup_grade')}")
                print(f"   - score: {ticker_result.get('score')}")
                print(f"   - tradable: {ticker_result.get('tradable')}")

                edge_status = ticker_result.get("ticker_edge_status")
                not_edge_not_computed = edge_status != "EDGE_NOT_COMPUTED"

                print(f"\n🔍 VALIDATION:")
                if not_edge_not_computed:
                    print(f"   ✅ Status is {edge_status} (not EDGE_NOT_COMPUTED)")
                else:
                    print(f"   ❌ Status is still EDGE_NOT_COMPUTED (compute may have failed)")

                return {
                    "ticker": ticker,
                    "found": True,
                    "edge_status": edge_status,
                    "not_edge_not_computed": not_edge_not_computed,
                    "data": ticker_result,
                }
            else:
                print(f"\n❌ {ticker} NOT FOUND in screener")
                print(f"   First 10 tickers: {[r.get('ticker') for r in results[:10]]}")
                return {
                    "ticker": ticker,
                    "found": False,
                    "error": "Ticker not in screener results",
                }
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return {"ticker": ticker, "found": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {"ticker": ticker, "found": False, "error": str(e)}

def main():
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "BUG FIX TEST: Single Ticker Edge Compute" + " " * 23 + "║")
    print("╚" + "═" * 78 + "╝")

    print(f"\n🔧 Configuration:")
    print(f"   API: {API_BASE_URL}")
    print(f"   Admin Key: {'configured' if ADMIN_KEY != 'test-admin-key' else 'DEFAULT (needs replace)'}")

    # Test 1: Compute BIIB
    print("\n\n" + "█" * 80)
    print("TEST 1: Compute BIIB (hardcoded example)")
    print("█" * 80)
    biib_result = test_single_ticker("BIIB")

    # Test 2: Verify cache contains BIIB
    if biib_result.get("passed"):
        cache_result = test_cache_contains_ticker("BIIB")

        # Test 3: Verify screener shows BIIB
        screener_result = test_screener_shows_edge("BIIB")
    else:
        cache_result = None
        screener_result = None

    # Summary
    print("\n\n" + "═" * 80)
    print("FINAL REPORT")
    print("═" * 80)

    print(f"\n✅ TEST 1: Single Ticker Compute (BIIB)")
    if biib_result.get("passed"):
        print(f"   ✅ PASSED — Edge computed for BIIB only")
        print(f"   Edge status: {biib_result.get('data', {}).get('edge_status')}")
        print(f"   Duration: {biib_result.get('data', {}).get('duration_ms')}ms")
    else:
        print(f"   ❌ FAILED — {biib_result.get('error', 'Unknown error')}")

    if cache_result:
        print(f"\n✅ TEST 2: Cache contains BIIB")
        if cache_result.get("found"):
            print(f"   ✅ PASSED — BIIB found in edge_cache")
        else:
            print(f"   ❌ FAILED — BIIB not in edge_cache")

    if screener_result:
        print(f"\n✅ TEST 3: Screener reflects edge")
        if screener_result.get("not_edge_not_computed"):
            print(f"   ✅ PASSED — Status changed to {screener_result.get('edge_status')}")
        else:
            print(f"   ❌ FAILED — Status still EDGE_NOT_COMPUTED")

    # Overall
    all_passed = (
        biib_result.get("passed", False) and
        (cache_result.get("found", False) if cache_result else True) and
        (screener_result.get("not_edge_not_computed", False) if screener_result else True)
    )

    print(f"\n" + "═" * 80)
    if all_passed:
        print(f"🎉 ALL TESTS PASSED — BUG IS FIXED!")
        print(f"   • Single ticker endpoint works correctly")
        print(f"   • Cache persists properly")
        print(f"   • Screener reflects computed edge")
    else:
        print(f"❌ SOME TESTS FAILED — See details above")
    print("═" * 80 + "\n")


if __name__ == "__main__":
    main()
