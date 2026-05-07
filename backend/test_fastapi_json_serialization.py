#!/usr/bin/env python3
"""
Test FastAPI JSON serialization for analyze/TON endpoint.
Reproduces the Railway HTTP 500 issue locally.
"""

import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_analyze_endpoints():
    """Test all analyze endpoints return valid JSON"""

    symbols = ["TON", "BTC", "ETH"]

    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"Testing: /api/crypto/scalp/analyze/{symbol}")
        print(f"{'='*60}")

        response = client.get(f"/api/crypto/scalp/analyze/{symbol}")

        print(f"HTTP Status: {response.status_code}")

        if response.status_code != 200:
            print(f"ERROR: Expected 200, got {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

        # Try to parse JSON
        try:
            data = response.json()
            print("[OK] JSON parsed successfully")
        except json.JSONDecodeError as e:
            print("[FAIL] JSON decode failed: {}".format(e))
            print("Response: {}".format(response.text[:200]))
            return False

        # Check required fields
        required_fields = [
            "symbol", "tier", "side", "scalp_score", "scalp_grade",
            "long_score", "short_score", "data_status",
            "scalp_execution_authorized", "paper_allowed"
        ]

        for field in required_fields:
            if field not in data:
                print("[FAIL] Missing field: {}".format(field))
                return False

        print("[OK] All required fields present")

        # Check new price fields if present
        price_fields = [
            "price_source", "displayed_price", "intraday_last_close",
            "snapshot_price", "price_suspect", "price_difference_pct",
            "price_timestamp"
        ]

        print("\nPrice fields:")
        for field in price_fields:
            if field in data:
                value = data[field]
                # Verify it's JSON serializable
                try:
                    json.dumps({field: value})
                    print("  [OK] {}: {} = {}".format(field, type(value).__name__, value))
                except (TypeError, ValueError) as e:
                    print("  [FAIL] {}: NOT JSON SERIALIZABLE - {}".format(field, e))
                    print("    Value type: {}".format(type(value)))
                    print("    Value: {}".format(value))
                    return False

        # Print some data for inspection
        print("\nData status: {}".format(data.get('data_status')))
        print("Grade: {}".format(data.get('scalp_grade')))
        print("Side: {}".format(data.get('side')))

        # Verify entire response is serializable
        try:
            json_str = json.dumps(data)
            print("\n[OK] Full response is JSON serializable ({} bytes)".format(len(json_str)))
        except TypeError as e:
            print("\n[FAIL] Full response is NOT JSON serializable: {}".format(e))
            # Find the problematic field
            for key, value in data.items():
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    print("  Problematic field: {} = {} (type: {})".format(key, value, type(value)))
            return False

    return True

if __name__ == "__main__":
    print("Testing FastAPI JSON serialization for Crypto Scalp analyze endpoint")
    print("=" * 60)

    success = test_analyze_endpoints()

    print("\n" + "=" * 60)
    if success:
        print("[PASS] All endpoints return valid JSON")
        sys.exit(0)
    else:
        print("[FAIL] Some endpoints have serialization issues")
        sys.exit(1)
