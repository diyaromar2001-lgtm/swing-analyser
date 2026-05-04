#!/usr/bin/env python3
"""
GLOBAL PRODUCTION STABILITY AUDIT - EDGE COMPLETE FLOW TEST

Tests dynamiques (pas hardcodés) pour vérifier :
1. Persistance et cache integrity
2. Edge Actions warmup complet (utilise vraie liste de tickers)
3. Single ticker edge compute
4. Screener reread après calcul
5. Crypto edge (diagnostic)

Scope: WARMUP + EDGE AUTO FLOW VERIFICATION
"""

import requests
import json
import time
from typing import Dict, List, Any
from datetime import datetime

API_BASE_URL = "http://localhost:8000"
ADMIN_KEY = "test-admin-key"  # Remplacer par votre vraie clé
HEADERS = {"X-Admin-Key": ADMIN_KEY}

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 100}")
    print(f"{'█' * 3} {title}")
    print(f"{'=' * 100}\n")

def test_cache_integrity_before() -> Dict[str, Any]:
    """Step 0: Verify cache integrity before warmup."""
    print_section("STEP 0: CACHE INTEGRITY — BEFORE WARMUP")

    url = f"{API_BASE_URL}/api/debug/cache-integrity"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Cache Integrity Status Retrieved")
            print(f"\n📊 PERSISTENCE STATUS:")
            pers = data.get("persistence", {})
            print(f"   - Enabled: {pers.get('enabled')}")
            print(f"   - File exists: {pers.get('file_exists')}")
            print(f"   - Last save: {pers.get('last_save')}")
            print(f"   - Last load: {pers.get('last_load')}")
            print(f"   - Last save OK: {pers.get('last_save_ok')}")
            print(f"   - Save/Load attempts: {pers.get('save_attempts')}/{pers.get('load_attempts')}")

            caches = data.get("caches", {})
            actions = caches.get("actions", {})
            crypto = caches.get("crypto", {})

            print(f"\n📦 ACTIONS CACHES:")
            print(f"   - OHLCV count: {actions.get('ohlcv_count')}")
            print(f"   - Price count: {actions.get('price_count')}")
            print(f"   - Screener keys: {actions.get('screener_cache_keys')}")
            print(f"   - Screener results: {actions.get('screener_results')}")
            print(f"   - Edge cache count: {actions.get('edge_cache_count')}")

            print(f"\n🔐 CRYPTO CACHES:")
            print(f"   - OHLCV daily count: {crypto.get('ohlcv_daily_count')}")
            print(f"   - OHLCV 4h count: {crypto.get('ohlcv_4h_count')}")
            print(f"   - Price count: {crypto.get('price_count')}")
            print(f"   - Screener count: {crypto.get('screener_cache_count')}")
            print(f"   - Edge cache count: {crypto.get('edge_cache_count')}")

            warnings = data.get("warnings", [])
            if warnings:
                print(f"\n⚠️  WARNINGS:")
                for w in warnings[:5]:
                    print(f"   - {w}")

            return data
        else:
            print(f"❌ Error: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def test_warmup_edge_actions() -> Dict[str, Any]:
    """Step 1: Run edge actions warmup and get list of computed tickers."""
    print_section("STEP 1: WARMUP EDGE ACTIONS — COMPUTE FOR A+/A/B TICKERS")

    url = f"{API_BASE_URL}/api/warmup/edge-actions"
    params = {"grades": "A+,A,B"}

    try:
        response = requests.post(url, params=params, headers=HEADERS, timeout=120)
        if response.status_code == 200:
            data = response.json()

            count = data.get("edge_actions_count", 0)
            computed = data.get("edge_actions_computed", 0)
            tickers = data.get("edge_actions_tickers", [])
            failed = data.get("edge_actions_failed", 0)

            print(f"✅ Edge Actions Warmup Completed")
            print(f"\n📊 RESULTS:")
            print(f"   - Tickers filtered (A+/A/B): {count}")
            print(f"   - Successfully computed: {computed}")
            print(f"   - Failed: {failed}")
            print(f"   - Duration: {data.get('duration_ms', 0)}ms")

            print(f"\n📋 TICKERS COMPUTED ({len(tickers)}):")
            for i, ticker in enumerate(tickers, 1):
                print(f"   {i}. {ticker}")

            errors = data.get("errors", [])
            if errors:
                print(f"\n❌ ERRORS (showing first 5):")
                for e in errors[:5]:
                    print(f"   - {e}")

            warnings_list = data.get("warnings", [])
            if warnings_list:
                print(f"\n⚠️  WARNINGS (showing first 5):")
                for w in warnings_list[:5]:
                    print(f"   - {w}")

            return {"data": data, "tickers": tickers}
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return {"data": {}, "tickers": []}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {"data": {}, "tickers": []}


def test_single_ticker_edge(ticker: str) -> Dict[str, Any]:
    """Step 2b: Test single ticker edge compute."""
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
                "trades": data.get("trades", 0),
                "pf": data.get("pf", 0.0),
                "test_pf": data.get("test_pf", 0.0),
                "expectancy": data.get("expectancy", 0.0),
                "overfit": data.get("overfit", False),
                "duration_ms": data.get("duration_ms", 0),
            }
        else:
            return {
                "ticker": ticker,
                "status": "error",
                "edge_status": "EDGE_NOT_COMPUTED",
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "ticker": ticker,
            "status": "error",
            "edge_status": "EDGE_NOT_COMPUTED",
            "error": str(e),
        }


def test_screener_after_compute(ticker: str) -> Dict[str, Any]:
    """Step 2c: Check if screener reflects the computed edge."""
    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            # Find the ticker
            for result in results:
                if result.get("ticker") == ticker:
                    return {
                        "ticker": ticker,
                        "found": True,
                        "edge_status": result.get("ticker_edge_status"),
                        "setup_grade": result.get("setup_grade"),
                        "score": result.get("score"),
                        "tradable": result.get("tradable"),
                    }

            return {
                "ticker": ticker,
                "found": False,
                "edge_status": None,
                "message": "Ticker not found in screener results",
            }
        else:
            return {
                "ticker": ticker,
                "found": False,
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {
            "ticker": ticker,
            "found": False,
            "error": str(e),
        }


def test_edge_flow_for_tickers(tickers: List[str], test_count: int = 3) -> List[Dict]:
    """Step 2: Test edge compute + screener reread for sampled tickers."""
    print_section(f"STEP 2: SINGLE TICKER EDGE COMPUTE & SCREENER REREAD")
    print(f"Testing {min(test_count, len(tickers))} tickers from computed list...\n")

    # Sample tickers
    sample = tickers[:test_count]
    results = []

    for ticker in sample:
        print(f"Testing {ticker}...")

        # Compute edge
        compute_result = test_single_ticker_edge(ticker)
        print(f"   Edge compute: {compute_result.get('edge_status')} (status={compute_result.get('status')})")

        # Wait a moment for persistence
        time.sleep(0.5)

        # Check screener
        screener_result = test_screener_after_compute(ticker)
        print(f"   Screener check: {screener_result.get('edge_status')} (found={screener_result.get('found')})")

        results.append({
            "ticker": ticker,
            "compute": compute_result,
            "screener": screener_result,
        })
        print()

    return results


def test_cache_integrity_after() -> Dict[str, Any]:
    """Step 3: Verify cache integrity after edge operations."""
    print_section("STEP 3: CACHE INTEGRITY — AFTER WARMUP")

    url = f"{API_BASE_URL}/api/debug/cache-integrity"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()

            caches = data.get("caches", {})
            actions = caches.get("actions", {})

            print(f"✅ Cache Status After Warmup:")
            print(f"\n📦 ACTIONS CACHES:")
            print(f"   - Edge cache count: {actions.get('edge_cache_count')}")
            print(f"   - Edge tickers: {actions.get('edge_tickers', [])}")

            pers = data.get("persistence", {})
            print(f"\n💾 PERSISTENCE:")
            print(f"   - Last save: {pers.get('last_save')}")
            print(f"   - Last save OK: {pers.get('last_save_ok')}")

            return data
        else:
            print(f"❌ Error: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def test_crypto_edge_diagnostic() -> Dict[str, Any]:
    """Step 4: Diagnostic only - check if crypto edge exists and how it's computed."""
    print_section("STEP 4: CRYPTO EDGE DIAGNOSTIC")

    url = f"{API_BASE_URL}/api/debug/cache-integrity"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()

            crypto = data.get("caches", {}).get("crypto", {})
            edge_count = crypto.get("edge_cache_count", 0)
            edge_tickers = crypto.get("edge_tickers", [])

            print(f"📊 CRYPTO EDGE DIAGNOSTIC:")
            print(f"   - Edge cache count: {edge_count}")
            print(f"   - Edge tickers: {edge_tickers}")

            if edge_count == 0:
                print(f"\n✅ Status: NO CRYPTO EDGE IN CACHE (correct)")
                print(f"   → Crypto remains non-tradable by design")
            else:
                print(f"\n⚠️  Status: CRYPTO EDGE EXISTS IN CACHE")
                print(f"   → Need to verify crypto stays non-tradable")
                print(f"   → Check: CRYPTO_BEAR or NO_VALIDATED_CRYPTO_EDGE constraints")

            return {"crypto": crypto, "diagnostic": "ok"}
        else:
            print(f"❌ Error: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def main():
    print("\n" + "╔" + "═" * 98 + "╗")
    print("║" + " " * 25 + "GLOBAL PRODUCTION STABILITY AUDIT — EDGE FLOW" + " " * 29 + "║")
    print("╚" + "═" * 98 + "╝")

    print(f"\n🔧 Configuration:")
    print(f"   API: {API_BASE_URL}")
    print(f"   Admin Key: {'configured' if ADMIN_KEY != 'test-admin-key' else 'DEFAULT (needs replace)'}")
    print(f"   Timestamp: {datetime.now().isoformat()}")

    # Step 0: Cache integrity before
    before = test_cache_integrity_before()
    before_edge_count = before.get("caches", {}).get("actions", {}).get("edge_cache_count", 0)

    # Step 1: Warmup edge actions
    warmup_result = test_warmup_edge_actions()
    tickers = warmup_result.get("tickers", [])

    if not tickers:
        print("\n❌ FATAL: No tickers returned from edge actions warmup!")
        return

    # Step 2: Test single ticker edge + screener
    edge_flow_results = test_edge_flow_for_tickers(tickers, test_count=min(3, len(tickers)))

    # Step 3: Cache integrity after
    after = test_cache_integrity_after()
    after_edge_count = after.get("caches", {}).get("actions", {}).get("edge_cache_count", 0)

    # Step 4: Crypto edge diagnostic
    crypto_diag = test_crypto_edge_diagnostic()

    # ══════════════════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════════════════════════

    print_section("FINAL REPORT & CONCLUSIONS")

    print(f"✅ EDGE ACTIONS WORKFLOW:")
    print(f"   - Tickers computed: {len(tickers)} (A+/A/B grades)")
    print(f"   - Duration: {warmup_result.get('data', {}).get('duration_ms', 0)}ms")
    print(f"   - List: {tickers}")

    print(f"\n✅ CACHE STATE EVOLUTION:")
    print(f"   - Edge cache BEFORE warmup: {before_edge_count} tickers")
    print(f"   - Edge cache AFTER warmup: {after_edge_count} tickers")
    print(f"   - Increase: {after_edge_count - before_edge_count} tickers")

    print(f"\n✅ PERSISTENCE INTEGRITY:")
    pers_before = before.get("persistence", {})
    pers_after = after.get("persistence", {})
    print(f"   - Persistence enabled: {pers_after.get('enabled')}")
    print(f"   - File exists: {pers_after.get('file_exists')}")
    print(f"   - Last save status: {'OK' if pers_after.get('last_save_ok') else 'FAIL'}")
    print(f"   - Save operations: {pers_after.get('save_attempts')} total")

    print(f"\n✅ SINGLE TICKER EDGE:")
    success_count = sum(1 for r in edge_flow_results if r.get('compute', {}).get('status') == 'ok')
    print(f"   - Successfully computed: {success_count}/{len(edge_flow_results)}")
    for r in edge_flow_results:
        ticker = r.get('ticker')
        edge_status = r.get('compute', {}).get('edge_status')
        screener_found = r.get('screener', {}).get('found')
        screener_status = r.get('screener', {}).get('edge_status')
        print(f"     • {ticker}: edge={edge_status}, screener_found={screener_found}, screener_edge={screener_status}")

    print(f"\n✅ SCREENER REREAD:")
    reread_ok = all(r.get('screener', {}).get('found') for r in edge_flow_results)
    print(f"   - Screener reflects computed edge: {'YES' if reread_ok else 'PARTIAL/NO'}")

    print(f"\n✅ CRYPTO EDGE:")
    crypto_count = crypto_diag.get('crypto', {}).get('edge_cache_count', 0)
    print(f"   - Crypto edge cache count: {crypto_count}")
    print(f"   - Status: {'NO EDGE (correct)' if crypto_count == 0 else 'EDGE EXISTS (verify constraints)'}")

    warnings = after.get("warnings", [])
    print(f"\n⚠️  WARNINGS:")
    if warnings:
        for w in warnings[:5]:
            print(f"   - {w}")
    else:
        print(f"   - None (excellent)")

    print(f"\n" + "═" * 100)
    print(f"✨ TEST COMPLETED — See results above for details")
    print(f"═" * 100 + "\n")


if __name__ == "__main__":
    main()
