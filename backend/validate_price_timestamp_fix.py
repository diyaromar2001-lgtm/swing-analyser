#!/usr/bin/env python3
"""
Validation script for price_timestamp JSON serialization fix
Tests that the Railway production endpoint returns proper price fields
"""

import sys
import json
import requests
from typing import Dict, Any, List, Tuple

PRODUCTION_URL = "https://swing-analyser-production.up.railway.app"
TEST_SYMBOLS = ["TON", "BTC", "ETH"]
REQUIRED_PRICE_FIELDS = [
    "price_source",
    "displayed_price",
    "intraday_last_close",
    "snapshot_price",
    "price_timestamp",
    "price_suspect",
    "price_difference_pct"
]

def test_endpoint(symbol: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Test a single symbol endpoint"""
    try:
        url = f"{PRODUCTION_URL}/api/crypto/scalp/analyze/{symbol}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}", {}

        data = response.json()
        return True, "OK", data

    except requests.exceptions.RequestException as e:
        return False, f"Request error: {str(e)}", {}
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {str(e)}", {}

def validate_price_timestamp(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that price_timestamp is present and numeric"""
    issues = []

    if "price_timestamp" not in data:
        issues.append("price_timestamp field missing")
        return False, issues

    ts_value = data["price_timestamp"]

    # Check it's numeric (int or float, not datetime)
    if not isinstance(ts_value, (int, float)) and ts_value is not None:
        issues.append(f"price_timestamp is {type(ts_value).__name__}, not numeric")
        return False, issues

    # Try to serialize it
    try:
        json.dumps({"ts": ts_value})
    except (TypeError, ValueError) as e:
        issues.append(f"price_timestamp not JSON serializable: {str(e)}")
        return False, issues

    return True, []

def validate_price_fields(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that all price fields are present and serializable"""
    issues = []
    missing = []

    for field in REQUIRED_PRICE_FIELDS:
        if field not in data:
            missing.append(field)

    if missing:
        issues.append(f"Missing fields: {', '.join(missing)}")

    # Try full JSON serialization
    try:
        json.dumps(data)
    except (TypeError, ValueError) as e:
        issues.append(f"Response not JSON serializable: {str(e)}")
        return False, issues

    return len(issues) == 0, issues

def main():
    print("=" * 70)
    print("VALIDATING PRICE TIMESTAMP FIX ON PRODUCTION")
    print("=" * 70)
    print()

    all_passed = True

    for symbol in TEST_SYMBOLS:
        print(f"\nTesting: {symbol}")
        print("-" * 70)

        # Test endpoint
        success, msg, data = test_endpoint(symbol)
        if not success:
            print(f"[FAIL] Endpoint error: {msg}")
            all_passed = False
            continue

        print(f"[OK] HTTP 200, valid JSON ({len(json.dumps(data))} bytes)")

        # Validate price_timestamp
        ts_ok, ts_issues = validate_price_timestamp(data)
        if ts_ok:
            ts_val = data.get("price_timestamp")
            print(f"[OK] price_timestamp: {ts_val} ({type(ts_val).__name__})")
        else:
            print(f"[FAIL] price_timestamp validation failed:")
            for issue in ts_issues:
                print(f"      - {issue}")
            all_passed = False

        # Validate all price fields
        fields_ok, field_issues = validate_price_fields(data)
        if fields_ok:
            print(f"[OK] All required price fields present and serializable")
        else:
            print(f"[FAIL] Price field validation failed:")
            for issue in field_issues:
                print(f"      - {issue}")
            all_passed = False

        # Show price field values
        print()
        print("Price field values:")
        for field in REQUIRED_PRICE_FIELDS:
            if field in data:
                val = data[field]
                print(f"  {field}: {val} ({type(val).__name__})")
            else:
                print(f"  {field}: MISSING")

    print()
    print("=" * 70)
    if all_passed:
        print("RESULT: [PASS] All validations passed - fix is working correctly")
        return 0
    else:
        print("RESULT: [FAIL] Some validations failed - fix needs adjustment")
        return 1

if __name__ == "__main__":
    sys.exit(main())
