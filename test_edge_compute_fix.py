#!/usr/bin/env python3
"""
Verification test for edge compute fix.
Tests the fixed /api/warmup/edge-actions endpoint to ensure:
1. Multi-key cache lookup works
2. Non-existent function is replaced with actual screener call
3. Returns actual tickers instead of 0
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
ADMIN_KEY_HEADER = {"X-Admin-Key": "test-admin-key"}  # If needed in production

def test_single_ticker_compute(ticker: str) -> Dict[str, Any]:
    """Test single-ticker edge computation endpoint"""
    print(f"\n{'='*70}")
    print(f"Testing: POST /api/strategy-edge/compute?ticker={ticker}")
    print(f"{'='*70}")

    url = f"{API_BASE_URL}/api/strategy-edge/compute"
    params = {"ticker": ticker}

    try:
        start = time.time()
        response = requests.post(url, params=params, headers=ADMIN_KEY_HEADER, timeout=30)
        duration = time.time() - start

        print(f"Status Code: {response.status_code}")
        print(f"Duration: {duration:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Response:")
            print(json.dumps(data, indent=2))

            # Verify key fields
            assert "status" in data, "Missing 'status' field"
            assert "ticker" in data, "Missing 'ticker' field"
            assert "edge_status" in data, "Missing 'edge_status' field"
            assert data["ticker"] == ticker, f"Ticker mismatch: expected {ticker}, got {data['ticker']}"

            return data
        else:
            print(f"❌ Error: {response.text}")
            return {}

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def test_bulk_edge_actions() -> Dict[str, Any]:
    """Test bulk edge actions endpoint (the one we fixed)"""
    print(f"\n{'='*70}")
    print(f"Testing: POST /api/warmup/edge-actions?grades=A+,A,B")
    print(f"{'='*70}")

    url = f"{API_BASE_URL}/api/warmup/edge-actions"
    params = {"grades": "A+,A,B"}

    try:
        start = time.time()
        response = requests.post(url, params=params, headers=ADMIN_KEY_HEADER, timeout=60)
        duration = time.time() - start

        print(f"Status Code: {response.status_code}")
        print(f"Duration: {duration:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Response:")
            print(json.dumps(data, indent=2))

            # Verify key fields
            assert "status" in data, "Missing 'status' field"
            assert "edge_actions_count" in data, "Missing 'edge_actions_count' field"
            assert "edge_actions_computed" in data, "Missing 'edge_actions_computed' field"
            assert "edge_actions_tickers" in data, "Missing 'edge_actions_tickers' field"

            # Verify the fix worked
            count = data.get("edge_actions_count", 0)
            if count == 0:
                print(f"\n⚠️  WARNING: edge_actions_count is 0 — fix may not be working")
                print(f"   Check if screener cache is populated")
                print(f"   Warnings: {data.get('warnings', [])}")
                print(f"   Errors: {data.get('errors', [])}")
            else:
                print(f"\n✅ SUCCESS: Found {count} eligible tickers")
                print(f"   Computed: {data.get('edge_actions_computed', 0)}")
                print(f"   Tickers: {data.get('edge_actions_tickers', [])[:10]}")  # Show first 10

            return data
        else:
            print(f"❌ Error: {response.text}")
            return {}

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def test_screener_cache_status() -> Dict[str, Any]:
    """Check current screener cache status"""
    print(f"\n{'='*70}")
    print(f"Testing: GET /api/cache-status?scope=screener")
    print(f"{'='*70}")

    url = f"{API_BASE_URL}/api/cache-status"
    params = {"scope": "screener"}

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Screener Cache Status:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"ℹ️  Endpoint not available or error: {response.status_code}")
            return {}

    except Exception as e:
        print(f"ℹ️  Exception (cache endpoint may not exist): {str(e)}")
        return {}


def main():
    print("\n" + "="*70)
    print("EDGE COMPUTE FIX VERIFICATION TEST")
    print("="*70)
    print(f"API Base URL: {API_BASE_URL}")

    # Step 1: Check screener cache status
    print("\n[STEP 1] Checking screener cache status...")
    cache_status = test_screener_cache_status()

    # Step 2: Test single-ticker computation for Actions
    print("\n[STEP 2] Testing single-ticker edge computation for Actions...")
    tickers_to_test = ["LLY", "CL", "LIN", "HOLX"]
    single_results = {}

    for ticker in tickers_to_test:
        result = test_single_ticker_compute(ticker)
        single_results[ticker] = result
        if result and result.get("edge_status") not in ["EDGE_NOT_COMPUTED", "error"]:
            print(f"✅ {ticker}: edge_status = {result.get('edge_status')}")
        time.sleep(0.5)  # Small delay between requests

    # Step 3: Test bulk edge actions (the fixed endpoint)
    print("\n[STEP 3] Testing bulk edge actions (FIXED ENDPOINT)...")
    bulk_result = test_bulk_edge_actions()

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    successful_singles = sum(1 for r in single_results.values() if r and r.get("status") == "ok")
    print(f"\n✅ Single-ticker computations successful: {successful_singles}/{len(tickers_to_test)}")

    if bulk_result:
        count = bulk_result.get("edge_actions_count", 0)
        computed = bulk_result.get("edge_actions_computed", 0)
        print(f"✅ Bulk edge actions:")
        print(f"   - Eligible tickers: {count}")
        print(f"   - Successfully computed: {computed}")

        if count > 0:
            print(f"\n🎉 FIX VERIFIED: Bulk endpoint now returns actual tickers (not 0)")
        else:
            print(f"\n⚠️  FIX NOT YET VERIFIED: Bulk endpoint still returns 0 tickers")
            print(f"   This could mean:")
            print(f"   1. Screener cache is empty (needs population first)")
            print(f"   2. No A+/A/B grades in current cache")
            print(f"   3. Fix not yet deployed")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
