#!/usr/bin/env python
"""
Test Phase 1 Crypto Scalp endpoints.
"""

import asyncio
from crypto_scalp_service import analyze_crypto_scalp_symbol, crypto_scalp_screener


def test_analyze_btc():
    """Test single symbol analysis."""
    print("\n=== Test: analyze_crypto_scalp_symbol('BTC') ===")
    result = analyze_crypto_scalp_symbol("BTC")
    print(f"Symbol: {result['symbol']}")
    print(f"Tier: {result['tier']}")
    print(f"Side: {result['side']}")
    print(f"Scalp Score: {result['scalp_score']}/100")
    print(f"Grade: {result['scalp_grade']}")
    print(f"Paper Allowed: {result['paper_allowed']}")
    print(f"Data Status: {result['data_status']}")
    print(f"Execution Authorized (Phase 1): {result['scalp_execution_authorized']}")
    assert result["scalp_execution_authorized"] is False, "Phase 1: execution must always be False"
    assert result["symbol"] == "BTC"
    print("[OK] BTC analysis passed")


def test_screener():
    """Test screener."""
    print("\n=== Test: crypto_scalp_screener() ===")
    result = crypto_scalp_screener(limit=5)
    print(f"Symbols returned: {result['count']}")
    print(f"Timestamp: {result['timestamp']}")
    assert isinstance(result["symbols"], list), "symbols must be list"
    assert result["count"] <= 5, "count must respect limit"
    if result["count"] > 0:
        first = result["symbols"][0]
        print(f"Top: {first['symbol']} (score: {first['scalp_score']}, grade: {first['scalp_grade']})")
        assert first["scalp_execution_authorized"] is False, "Phase 1: execution always False"
    print(f"[OK] Screener test passed ({result['count']} symbols)")


def test_tier_filtering():
    """Test Tier 1 filtering."""
    print("\n=== Test: Tier 1 filter ===")
    result = crypto_scalp_screener(tier_filter=1, limit=10)
    print(f"Tier 1 results: {result['count']}")
    for sym in result["symbols"]:
        assert sym["tier"] == 1, f"Expected tier 1, got {sym['tier']}"
    print("[OK] Tier 1 filtering passed")


def test_score_filtering():
    """Test min_score filter."""
    print("\n=== Test: Min Score >=60 ===")
    result = crypto_scalp_screener(min_score=60, limit=20)
    print(f"Symbols with score >= 60: {result['count']}")
    for sym in result["symbols"]:
        assert sym["scalp_score"] >= 60, f"Expected score >=60, got {sym['scalp_score']}"
    print("[OK] Score filtering passed")


def test_long_short_signals():
    """Test that LONG/SHORT signals have entry/stop/TP."""
    print("\n=== Test: LONG/SHORT signals have entry/stop/TP ===")
    result = crypto_scalp_screener(limit=20)
    has_signals = False
    for sym in result["symbols"]:
        if sym["side"] in ("LONG", "SHORT"):
            has_signals = True
            assert sym["entry"] is not None, f"{sym['symbol']}: Missing entry"
            assert sym["stop_loss"] is not None, f"{sym['symbol']}: Missing stop_loss"
            assert sym["tp1"] is not None, f"{sym['symbol']}: Missing tp1"
            print(f"  {sym['symbol']} {sym['side']}: Entry {sym['entry']}, Stop {sym['stop_loss']}")
    if has_signals:
        print("[OK] Signal entry/stop/TP present")
    else:
        print("[WARN] No LONG/SHORT signals found (data might be stale)")


if __name__ == "__main__":
    print("=" * 60)
    print("CRYPTO SCALP PHASE 1 — BACKEND TESTS")
    print("=" * 60)

    try:
        test_analyze_btc()
        test_screener()
        test_tier_filtering()
        test_score_filtering()
        test_long_short_signals()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED [OK]")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
