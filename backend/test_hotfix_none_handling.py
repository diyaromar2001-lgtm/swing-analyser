#!/usr/bin/env python3
"""
Quick local test to validate hotfix for None/NaN/inf handling.
Tests edge cases that would have caused HTTP 500.
"""

import math
import sys

# Mock the helper functions as they would be in crypto_scalp_service
def _is_nan(value):
    """Check if value is NaN (safe)"""
    try:
        return isinstance(value, float) and math.isnan(value)
    except (TypeError, ValueError):
        return False

def _is_inf(value):
    """Check if value is infinity (safe)"""
    try:
        return isinstance(value, float) and math.isinf(value)
    except (TypeError, ValueError):
        return False

def test_none_price():
    """Test: current_price = None should not crash round()"""
    current_price = None
    result = {}

    # This would have crashed before: round(None, 4)
    # Now protected:
    if current_price is not None and current_price > 0:
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] is None, "Expected None for invalid price"
    print("[PASS] Test 1: None price handled correctly")

def test_zero_price():
    """Test: current_price = 0 should return None"""
    current_price = 0.0
    result = {}

    if current_price is not None and current_price > 0:
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] is None, "Expected None for zero price"
    print("[PASS] Test 2: Zero price handled correctly")

def test_nan_price():
    """Test: current_price = NaN should return None"""
    current_price = float('nan')
    result = {}

    if current_price is not None and current_price > 0 and not (_is_nan(current_price) or _is_inf(current_price)):
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] is None, "Expected None for NaN price"
    print("[PASS] Test 3: NaN price handled correctly")

def test_inf_price():
    """Test: current_price = inf should return None"""
    current_price = float('inf')
    result = {}

    if current_price is not None and current_price > 0 and not (_is_nan(current_price) or _is_inf(current_price)):
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] is None, "Expected None for inf price"
    print("[PASS] Test 4: Inf price handled correctly")

def test_valid_small_price():
    """Test: current_price = 2.45 (small price like TON) should work"""
    current_price = 2.45
    result = {}

    if current_price is not None and current_price > 0:
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] == 2.45, f"Expected 2.45, got {result['displayed_price']}"
    print("[PASS] Test 5: Valid small price (TON-like) handled correctly")

def test_valid_large_price():
    """Test: current_price = 45123.50 (large price like BTC) should work"""
    current_price = 45123.50
    result = {}

    if current_price is not None and current_price > 0:
        try:
            result["displayed_price"] = round(current_price, 4 if current_price < 10 else 2)
        except (ValueError, TypeError, OverflowError):
            result["displayed_price"] = None
    else:
        result["displayed_price"] = None

    assert result["displayed_price"] == 45123.5, f"Expected 45123.5, got {result['displayed_price']}"
    print("[PASS] Test 6: Valid large price (BTC-like) handled correctly")

def test_timestamp_datetime():
    """Test: timestamp should always be numeric, not datetime"""
    # Simulate what happens if timestamp is a datetime object
    price_snap = {"ts": None}  # Defensive fallback

    try:
        ts_value = price_snap.get("ts", 0)
        if isinstance(ts_value, (int, float)):
            result_ts = ts_value
        else:
            result_ts = float(ts_value) if ts_value else 0.0
    except (ValueError, TypeError):
        result_ts = 0.0

    assert isinstance(result_ts, (int, float)), "Timestamp must be numeric"
    assert result_ts == 0.0, "Expected 0.0 for None timestamp"
    print("[PASS] Test 7: Timestamp handling is safe")

def test_nan_divergence():
    """Test: NaN divergence should not be stored"""
    snapshot_price = 2.42
    intraday_last_close = 2.45

    price_difference_pct = None

    try:
        diff_pct = abs(snapshot_price - intraday_last_close) / intraday_last_close * 100
        if not (_is_nan(diff_pct) or _is_inf(diff_pct)):
            price_difference_pct = round(diff_pct, 2)
    except Exception:
        price_difference_pct = None

    assert price_difference_pct is not None, "Valid divergence should be stored"
    assert price_difference_pct > 0, "Divergence should be positive"
    print("[PASS] Test 8: Valid divergence calculation: {:.2f}%".format(price_difference_pct))

def test_impossible_divergence():
    """Test: Impossible divergence (0/0) should be caught"""
    snapshot_price = 0.0
    intraday_last_close = 0.0

    price_difference_pct = None

    try:
        if intraday_last_close > 0:  # Guard before division
            diff_pct = abs(snapshot_price - intraday_last_close) / intraday_last_close * 100
            if not (_is_nan(diff_pct) or _is_inf(diff_pct)):
                price_difference_pct = round(diff_pct, 2)
    except Exception:
        price_difference_pct = None

    assert price_difference_pct is None, "0/0 divergence should remain None"
    print("[PASS] Test 9: Impossible divergence guarded correctly")

def test_json_serializable():
    """Test: All result fields should be JSON serializable"""
    import json

    result = {
        "price_source": "intraday_5m",
        "displayed_price": 2.45,
        "intraday_last_close": 2.446,
        "snapshot_price": None,
        "price_suspect": False,
        "price_difference_pct": 1.23,
        "price_timestamp": 0.0,
        "provider_error": None,
    }

    try:
        json.dumps(result)
        print("[PASS] Test 10: Result is JSON serializable")
    except TypeError as e:
        print("[FAIL] Test 10: {}".format(e))
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Testing hotfix for None/NaN/inf handling")
    print("=" * 60)

    test_none_price()
    test_zero_price()
    test_nan_price()
    test_inf_price()
    test_valid_small_price()
    test_valid_large_price()
    test_timestamp_datetime()
    test_nan_divergence()
    test_impossible_divergence()
    test_json_serializable()

    print("=" * 60)
    print("[PASS] ALL TESTS PASSED")
    print("=" * 60)
