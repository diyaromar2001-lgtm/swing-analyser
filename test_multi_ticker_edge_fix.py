#!/usr/bin/env python3
"""
TEST MULTI-TICKER: Vérifier que single ticker edge fonctionne pour N'IMPORTE QUEL ticker

Le bug partiel: BIIB fonctionne mais pas les autres tickers.
Cause probable: Frontend/Screener cache pas refresh après compute.

Ce test:
1. Récupère dynamiquement 5 tickers du screener qui ont EDGE_NOT_COMPUTED
2. Pour chaque ticker: POST compute + vérifier cache + vérifier screener
3. Détecte le problème: "Edge non calculé" persiste après compute
"""

import requests
import json
import time
from typing import Dict, List, Any
from datetime import datetime

API_BASE_URL = "http://localhost:8000"
ADMIN_KEY = "test-admin-key"
HEADERS = {"X-Admin-Key": ADMIN_KEY}

def get_screener_tickers_with_edge_not_computed() -> List[str]:
    """Récupère les tickers du screener avec EDGE_NOT_COMPUTED."""
    print(f"\n{'='*80}")
    print("STEP 0: Get screener tickers with EDGE_NOT_COMPUTED")
    print(f"{'='*80}\n")

    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # API returns list directly, not wrapped in object
            results = data if isinstance(data, list) else data.get("results", [])

            print(f"✅ Screener retrieved {len(results)} tickers")

            # Filter for EDGE_NOT_COMPUTED tickers (any grade - test single ticker for all statuses)
            edge_not_computed = []
            for result in results:
                if result.get("ticker_edge_status") == "EDGE_NOT_COMPUTED":
                    edge_not_computed.append(result.get("ticker"))

            print(f"\n📋 Tickers with EDGE_NOT_COMPUTED (all grades):")
            print(f"   Found: {len(edge_not_computed)} tickers")

            # Take first 5 (or all if less than 5)
            selected = edge_not_computed[:5]
            for i, ticker in enumerate(selected, 1):
                print(f"   {i}. {ticker}")

            return selected
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return []

def test_single_ticker_compute(ticker: str) -> Dict[str, Any]:
    """Test compute pour un ticker unique."""
    url = f"{API_BASE_URL}/api/strategy-edge/compute"
    params = {"ticker": ticker}

    try:
        response = requests.post(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                "ticker": ticker,
                "status": data.get("status"),
                "edge_status": data.get("edge_status"),
                "trades": data.get("trades"),
                "train_pf": data.get("train_pf"),
                "test_pf": data.get("test_pf"),
                "expectancy": data.get("expectancy"),
                "overfit_warning": data.get("overfit_warning"),
                "sample_status": data.get("sample_status"),
                "raw_response": data,
            }
        else:
            return {
                "ticker": ticker,
                "status": "error",
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "ticker": ticker,
            "status": "error",
            "error": str(e),
        }

def check_cache_contains_ticker(ticker: str) -> Dict[str, Any]:
    """Vérifier que le ticker est dans _edge_cache."""
    url = f"{API_BASE_URL}/api/debug/cache-integrity"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            edge_tickers = data.get("caches", {}).get("actions", {}).get("edge_tickers", [])
            ticker_in_cache = ticker.upper() in [t.upper() for t in edge_tickers]

            return {
                "ticker": ticker,
                "found_in_cache": ticker_in_cache,
                "edge_tickers": edge_tickers,
                "cache_count": data.get("caches", {}).get("actions", {}).get("edge_cache_count", 0),
            }
        else:
            return {"ticker": ticker, "found_in_cache": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"ticker": ticker, "found_in_cache": False, "error": str(e)}

def check_screener_after_compute(ticker: str) -> Dict[str, Any]:
    """Vérifier le statut du ticker dans le screener APRÈS compute."""
    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # API returns list directly, not wrapped in object
            results = data if isinstance(data, list) else data.get("results", [])

            for result in results:
                if result.get("ticker", "").upper() == ticker.upper():
                    edge_status = result.get("ticker_edge_status")
                    still_edge_not_computed = (edge_status == "EDGE_NOT_COMPUTED")

                    return {
                        "ticker": ticker,
                        "found": True,
                        "edge_status": edge_status,
                        "still_edge_not_computed": still_edge_not_computed,
                        "grade": result.get("setup_grade"),
                        "score": result.get("score"),
                    }

            return {
                "ticker": ticker,
                "found": False,
                "error": "Ticker not in screener",
            }
        else:
            return {"ticker": ticker, "found": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"ticker": ticker, "found": False, "error": str(e)}

def main():
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "MULTI-TICKER EDGE COMPUTE TEST — Bug Partiel" + " " * 19 + "║")
    print("╚" + "═" * 78 + "╝")

    print(f"\n🔧 Configuration:")
    print(f"   API: {API_BASE_URL}")
    print(f"   Timestamp: {datetime.now().isoformat()}")

    # Step 0: Get tickers with EDGE_NOT_COMPUTED
    tickers_to_test = get_screener_tickers_with_edge_not_computed()

    if not tickers_to_test:
        print("\n❌ No tickers with EDGE_NOT_COMPUTED found in screener")
        return

    # Test each ticker
    results = []
    for i, ticker in enumerate(tickers_to_test, 1):
        print(f"\n\n{'█'*80}")
        print(f"TEST {i}/{len(tickers_to_test)}: {ticker}")
        print(f"{'█'*80}\n")

        # Step 1: Compute
        print(f"Step 1: Compute edge for {ticker}")
        compute_result = test_single_ticker_compute(ticker)
        print(f"  Status: {compute_result.get('status')}")
        if compute_result.get('status') == 'ok':
            print(f"  Edge status: {compute_result.get('edge_status')}")
            print(f"  Trades: {compute_result.get('trades')}")
            print(f"  Train PF: {compute_result.get('train_pf')}")
        else:
            print(f"  Error: {compute_result.get('error')}")

        # Small delay to ensure backend write
        time.sleep(0.5)

        # Step 2: Check cache
        print(f"\nStep 2: Check cache")
        cache_result = check_cache_contains_ticker(ticker)
        print(f"  Found in cache: {cache_result.get('found_in_cache')}")
        if not cache_result.get('found_in_cache'):
            print(f"  ❌ PROBLEM: {ticker} NOT in cache!")
            print(f"     Available: {cache_result.get('edge_tickers', [])[:5]}")

        # Step 3: Check screener
        print(f"\nStep 3: Check screener after compute")
        screener_result = check_screener_after_compute(ticker)
        print(f"  Found in screener: {screener_result.get('found')}")
        print(f"  Edge status: {screener_result.get('edge_status')}")
        if screener_result.get('still_edge_not_computed'):
            print(f"  ❌ CRITICAL BUG: Still EDGE_NOT_COMPUTED after compute!")
            print(f"     (This is the partial bug)")
        else:
            print(f"  ✅ Status changed from EDGE_NOT_COMPUTED")

        # Summary for this ticker
        results.append({
            "ticker": ticker,
            "compute": compute_result,
            "cache": cache_result,
            "screener": screener_result,
        })

    # Final Report
    print(f"\n\n{'='*80}")
    print("FINAL REPORT")
    print(f"{'='*80}\n")

    success_count = 0
    cache_count = 0
    screener_ok_count = 0

    for result in results:
        ticker = result["ticker"]
        compute_ok = result["compute"].get("status") == "ok"
        cache_ok = result["cache"].get("found_in_cache")
        screener_ok = not result["screener"].get("still_edge_not_computed", True)

        print(f"\n{ticker}:")
        print(f"  Compute: {'✅' if compute_ok else '❌'}")
        print(f"  Cache: {'✅' if cache_ok else '❌'}")
        print(f"  Screener: {'✅' if screener_ok else '❌'}")

        if compute_ok:
            success_count += 1
        if cache_ok:
            cache_count += 1
        if screener_ok:
            screener_ok_count += 1

    print(f"\n\n📊 SUMMARY:")
    print(f"  Tickers tested: {len(results)}")
    print(f"  Compute success: {success_count}/{len(results)}")
    print(f"  In cache: {cache_count}/{len(results)}")
    print(f"  Screener updated: {screener_ok_count}/{len(results)}")

    if screener_ok_count == 0:
        print(f"\n🔴 CRITICAL BUG CONFIRMED:")
        print(f"   All {len(results)} tickers still show EDGE_NOT_COMPUTED in screener")
        print(f"   even though compute succeeded and cache updated.")
        print(f"\n   Root cause: Frontend/Screener cache not refreshing after compute")
        print(f"   Fix needed: TradePlan must refresh screener after success")
    elif screener_ok_count < len(results):
        print(f"\n🟡 PARTIAL BUG:")
        print(f"   Only {screener_ok_count}/{len(results)} tickers show updated status")
        print(f"   This is the bug user reported")
    else:
        print(f"\n🟢 NO BUG:")
        print(f"   All tickers properly updated in screener")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
