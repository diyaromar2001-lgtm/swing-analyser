"""
Crypto Universe Data Validation Script
Scope: DATA VALIDATION ONLY - No modifications to official scanner
Tests 33 candidate cryptos for real data availability
"""

import json
import time
from datetime import datetime
import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional
from crypto_universe import CRYPTO_BY_SYMBOL, CRYPTO_SYMBOLS

# Core candidate cryptos (15)
CORE_CANDIDATES = [
    "BTC", "ETH", "SOL", "DOGE", "XRP",
    "ADA", "BNB", "AVAX", "BCH", "LINK",
    "XMR", "ZEC", "TRX", "LTC", "NEAR"
]

# Research candidates (18)
RESEARCH_CANDIDATES = [
    "ATOM", "AAVE", "UNI", "SUI", "ARB", "OP", "APT", "ONDO", "SHIB",
    "INJ", "RENDER", "CRV", "MKR", "ICP", "HBAR", "FLOKI", "BONK", "WIF"
]

ALL_CANDIDATES = CORE_CANDIDATES + RESEARCH_CANDIDATES


def test_crypto(symbol: str) -> Dict:
    """
    Test a single crypto for:
    - Yahoo symbol existence
    - Daily data availability
    - 4H data availability (via hourly aggregation)
    - Last data date
    - Price & volume
    """
    result = {
        "symbol": symbol,
        "yahoo_symbol": None,
        "daily_data_ok": False,
        "daily_bars": 0,
        "daily_last_date": None,
        "4h_data_ok": False,
        "4h_bars": 0,
        "4h_last_date": None,
        "price_ok": False,
        "price": None,
        "volume_24h": None,
        "errors": [],
        "status": "UNKNOWN"
    }

    # Get Yahoo symbol from crypto_universe
    meta = CRYPTO_BY_SYMBOL.get(symbol)
    if not meta:
        result["errors"].append(f"Symbol {symbol} not in CRYPTO_UNIVERSE")
        result["status"] = "NOT_FOUND"
        return result

    yahoo_symbol = meta.get("yahoo_symbol")
    result["yahoo_symbol"] = yahoo_symbol

    if not yahoo_symbol:
        result["errors"].append(f"No yahoo_symbol configured for {symbol}")
        result["status"] = "CONFIG_ERROR"
        return result

    # Test 1: Daily data (730d)
    try:
        ticker = yf.Ticker(yahoo_symbol)
        daily_hist = ticker.history(period="730d", interval="1d", auto_adjust=False)

        if daily_hist is None or daily_hist.empty:
            result["errors"].append("Daily history returned empty")
        else:
            result["daily_bars"] = len(daily_hist)
            result["daily_last_date"] = str(daily_hist.index[-1].date())
            result["daily_data_ok"] = len(daily_hist) >= 220  # ~1 year of daily bars

            # Get last close and volume for price check
            if "Close" in daily_hist.columns:
                result["price"] = round(float(daily_hist["Close"].iloc[-1]), 4)
                result["price_ok"] = result["price"] > 0

            if "Volume" in daily_hist.columns:
                result["volume_24h"] = float(daily_hist["Volume"].iloc[-1])

    except Exception as e:
        result["errors"].append(f"Daily data error: {type(e).__name__}: {str(e)[:50]}")

    # Test 2: 4H data (via 1h aggregation - 60d)
    try:
        ticker = yf.Ticker(yahoo_symbol)
        hourly_hist = ticker.history(period="60d", interval="1h", auto_adjust=False)

        if hourly_hist is None or hourly_hist.empty:
            result["errors"].append("Hourly history returned empty (needed for 4h)")
        else:
            # Aggregate to 4h
            if isinstance(hourly_hist.columns, pd.MultiIndex):
                hourly_hist.columns = hourly_hist.columns.get_level_values(0)

            hourly_hist = hourly_hist.rename(columns=str.title)

            # Need these columns
            if all(col in hourly_hist.columns for col in ["Open", "High", "Low", "Close", "Volume"]):
                ohlc_4h = hourly_hist[["Open", "High", "Low", "Close", "Volume"]].dropna()
                ohlc_4h = ohlc_4h.resample("4h").agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }).dropna()

                result["4h_bars"] = len(ohlc_4h)
                result["4h_last_date"] = str(ohlc_4h.index[-1])
                result["4h_data_ok"] = len(ohlc_4h) >= 120  # ~60-80 days of 4h bars (6 per day)
            else:
                result["errors"].append(f"Hourly data missing columns: {hourly_hist.columns.tolist()}")

    except Exception as e:
        result["errors"].append(f"4H data error: {type(e).__name__}: {str(e)[:50]}")

    # Determine final status
    if result["daily_data_ok"] and result["4h_data_ok"] and result["price_ok"]:
        result["status"] = "VALID_FULL"
    elif result["daily_data_ok"] and result["price_ok"]:
        result["status"] = "VALID_DAILY"
    elif result["daily_data_ok"]:
        result["status"] = "VALID_DAILY_NOVOLUME"
    else:
        result["status"] = "INVALID"

    return result


def run_validation():
    """Run full validation suite"""
    print(f"\n{'='*80}")
    print(f"CRYPTO UNIVERSE DATA VALIDATION")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"{'='*80}\n")

    results = {
        "core": [],
        "research": [],
        "timestamp": datetime.now().isoformat(),
        "summary": {}
    }

    # Test core candidates
    print(f"Testing {len(CORE_CANDIDATES)} CORE candidates...")
    for symbol in CORE_CANDIDATES:
        print(f"  Testing {symbol}...", end=" ", flush=True)
        result = test_crypto(symbol)
        results["core"].append(result)
        print(f"{result['status']}")
        time.sleep(0.5)  # Rate limit yfinance

    # Test research candidates
    print(f"\nTesting {len(RESEARCH_CANDIDATES)} RESEARCH candidates...")
    for symbol in RESEARCH_CANDIDATES:
        print(f"  Testing {symbol}...", end=" ", flush=True)
        result = test_crypto(symbol)
        results["research"].append(result)
        print(f"{result['status']}")
        time.sleep(0.5)  # Rate limit yfinance

    # Generate summary
    all_results = results["core"] + results["research"]

    valid_full = [r for r in all_results if r["status"] == "VALID_FULL"]
    valid_daily = [r for r in all_results if r["status"] in ["VALID_DAILY", "VALID_DAILY_NOVOLUME"]]
    invalid = [r for r in all_results if r["status"] in ["INVALID", "NOT_FOUND", "CONFIG_ERROR"]]

    results["summary"] = {
        "total_tested": len(all_results),
        "valid_full": len(valid_full),
        "valid_daily_only": len(valid_daily),
        "invalid": len(invalid),
        "valid_full_symbols": [r["symbol"] for r in valid_full],
        "valid_daily_symbols": [r["symbol"] for r in valid_daily],
        "invalid_symbols": [r["symbol"] for r in invalid],
    }

    # Save results
    output_file = "crypto_universe_validation.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"VALIDATION COMPLETE")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}\n")

    # Print summary
    print(f"SUMMARY:")
    print(f"  Total tested: {results['summary']['total_tested']}")
    print(f"  Valid (full data): {results['summary']['valid_full']} - {results['summary']['valid_full_symbols']}")
    print(f"  Valid (daily only): {results['summary']['valid_daily_only']} - {results['summary']['valid_daily_symbols']}")
    print(f"  Invalid: {results['summary']['invalid']} - {results['summary']['invalid_symbols']}")

    return results


if __name__ == "__main__":
    run_validation()
