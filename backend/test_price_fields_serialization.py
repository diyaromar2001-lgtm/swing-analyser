#!/usr/bin/env python3
"""
Test JSON serialization of price fix response fields.
Simulates what price fix adds to the response.
"""

import json
import math
from datetime import datetime

def test_price_fields_serialization():
    """Test if new price fields are JSON serializable"""

    # Simulate what price fix ADDS to response
    test_cases = [
        {
            "name": "Valid case: all prices as float",
            "price_source": "intraday_5m",
            "displayed_price": 2.446,
            "intraday_last_close": 2.446,
            "snapshot_price": 2.42,
            "price_suspect": False,
            "price_difference_pct": 1.23,
            "price_timestamp": 1778101234.5,
        },
        {
            "name": "Edge case: None values",
            "price_source": "unknown",
            "displayed_price": None,
            "intraday_last_close": None,
            "snapshot_price": None,
            "price_suspect": False,
            "price_difference_pct": None,
            "price_timestamp": 0.0,
        },
        {
            "name": "CRASH RISK: timestamp as datetime object",
            "price_source": "snapshot",
            "displayed_price": 45123.5,
            "intraday_last_close": None,
            "snapshot_price": 45123.5,
            "price_suspect": False,
            "price_difference_pct": None,
            "price_timestamp": datetime.now(),  # <-- PROBLEMATIC!
        },
        {
            "name": "CRASH RISK: NaN in price_difference_pct",
            "price_source": "intraday_5m",
            "displayed_price": 2.5,
            "intraday_last_close": 2.5,
            "snapshot_price": 2.5,
            "price_suspect": True,
            "price_difference_pct": float('nan'),  # <-- PROBLEMATIC!
            "price_timestamp": 1778101234.5,
        },
        {
            "name": "CRASH RISK: Infinity in price_difference_pct",
            "price_source": "intraday_5m",
            "displayed_price": 0.0001,
            "intraday_last_close": 0.0001,
            "snapshot_price": 100000.0,
            "price_suspect": True,
            "price_difference_pct": float('inf'),  # <-- PROBLEMATIC!
            "price_timestamp": 1778101234.5,
        },
    ]

    results = []

    for test_case in test_cases:
        case_name = test_case.pop("name")
        print("[TEST] {}".format(case_name))

        try:
            json_str = json.dumps(test_case)
            print("  [PASS] JSON serializable ({} bytes)".format(len(json_str)))
            results.append(True)
        except (TypeError, ValueError) as e:
            error_msg = str(e)
            print("  [FAIL] JSON serialization error: {}".format(error_msg))

            # Identify which field caused the problem
            for key, value in test_case.items():
                try:
                    json.dumps({key: value})
                except (TypeError, ValueError):
                    print("    -> Problematic field: {} = {} (type: {})".format(
                        key, value, type(value).__name__
                    ))

            results.append(False)

        print()

    return all(results)

if __name__ == "__main__":
    print("=" * 70)
    print("Testing JSON serialization of price fix response fields")
    print("=" * 70)
    print()

    success = test_price_fields_serialization()

    print("=" * 70)
    if success:
        print("[PASS] All price field combinations are JSON serializable")
        print("\nConclusion: Price fix should work if all fields are properly typed.")
    else:
        print("[FAIL] Some price field combinations are NOT JSON serializable")
        print("\nConclusion: These edge cases could cause HTTP 500 in production.")
        print("Mitigation: Add defensive type checking and NaN/Inf protection.")

    print("=" * 70)
