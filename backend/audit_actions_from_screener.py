#!/usr/bin/env python3
"""
ACTIONS AUDIT: Test symbols from actual screener
"""

import httpx
import yfinance as yf
from datetime import datetime, timezone
from typing import Dict, List, Any

RAILWAY_URL = "https://swing-analyser-production.up.railway.app"

print("\n" + "=" * 140)
print("ACTIONS AUDIT: SCREENER SYMBOLS")
print("=" * 140)
print(f"[START] {datetime.now(timezone.utc).isoformat()}\n")

# ============================================================================
# SECTION 1: GET SCREENER SYMBOLS
# ============================================================================

print("SECTION 1: FETCHING SCREENER DATA")
print("-" * 140)

screener_data = []
try:
    url = f"{RAILWAY_URL}/api/screener?limit=500"
    with httpx.Client(timeout=30) as client:
        r = client.get(url)
        if r.status_code == 200:
            screener_data = r.json()
            print(f"[OK] Retrieved {len(screener_data)} actions from screener\n")
except Exception as e:
    print(f"[ERROR] {e}\n")

if not screener_data:
    print("[ERROR] No screener data available")
    exit(1)

# Select first 12 symbols for testing
TEST_SYMBOLS = [d.get("ticker") for d in screener_data[:12]]

print(f"Testing {len(TEST_SYMBOLS)} symbols from screener:")
for sym in TEST_SYMBOLS:
    print(f"  - {sym}")

# ============================================================================
# SECTION 2: YFINANCE PRICES
# ============================================================================

print("\n" + "=" * 140)
print("SECTION 2: YFINANCE REFERENCE PRICES")
print("=" * 140 + "\n")

yf_results = {}

print(f"{'Symbol':<8} {'Sector':<15} {'YFinance Price':<18} {'Market Status':<20}")
print("-" * 140)

for symbol in TEST_SYMBOLS:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        if hist.empty:
            price = None
            status = "NO DATA"
        else:
            price = hist['Close'].iloc[-1]
            info = ticker.info
            is_open = info.get("marketState") == "OPEN" if "marketState" in info else None
            status = "MARKET OPEN" if is_open else ("MARKET CLOSED" if is_open is False else "UNKNOWN")

        yf_results[symbol] = {"yfinance_price": price, "market_status": status}

        sector = next((d.get("sector") for d in screener_data if d.get("ticker") == symbol), "N/A")
        print(f"{symbol:<8} {sector:<15} {str(price):<18} {status:<20}")

    except Exception as e:
        yf_results[symbol] = {"error": str(e)}
        print(f"{symbol:<8} {'ERROR':<15} {str(e)[:30]:<18}")

# ============================================================================
# SECTION 3: RAILWAY SCREENER PRICES
# ============================================================================

print("\n" + "=" * 140)
print("SECTION 3: RAILWAY SCREENER PRICES")
print("=" * 140 + "\n")

screener_by_symbol = {d.get("ticker"): d for d in screener_data}

print(f"{'Symbol':<8} {'Railway Price':<18} {'Score':<8} {'Grade':<8} {'Status':<20}")
print("-" * 140)

for symbol in TEST_SYMBOLS:
    if symbol in screener_by_symbol:
        data = screener_by_symbol[symbol]
        price = data.get("price")
        score = data.get("score")
        grade = data.get("setup_grade")
        status = data.get("setup_status", "UNKNOWN")

        print(f"{symbol:<8} {str(price):<18} {str(score):<8} {str(grade):<8} {status:<20}")
    else:
        print(f"{symbol:<8} NOT FOUND")

# ============================================================================
# SECTION 4: PRICE COMPARISON
# ============================================================================

print("\n" + "=" * 140)
print("SECTION 4: PRICE COMPARISON - YFINANCE VS RAILWAY")
print("=" * 140 + "\n")

print(f"{'Symbol':<8} {'YFinance':<18} {'Railway':<18} {'Divergence':<15} {'Status':<20}")
print("-" * 140)

divergence_count = 0
comparison_issues = []

for symbol in TEST_SYMBOLS:
    yf_price = yf_results.get(symbol, {}).get("yfinance_price")
    railway_data = screener_by_symbol.get(symbol, {})
    railway_price = railway_data.get("price")

    if yf_price and railway_price:
        divergence = abs(yf_price - railway_price) / yf_price * 100
        status = "OK" if divergence < 3 else "WARN" if divergence < 10 else "SUSPECT"

        if status != "OK":
            divergence_count += 1
            comparison_issues.append({
                "symbol": symbol,
                "yfinance": yf_price,
                "railway": railway_price,
                "divergence": divergence,
                "status": status
            })

        print(f"{symbol:<8} {str(yf_price):<18} {str(railway_price):<18} {divergence:.2f}%{'':<9} {status:<20}")
    else:
        print(f"{symbol:<8} {str(yf_price):<18} {str(railway_price):<18} N/A{'':<14} UNAVAILABLE")

# ============================================================================
# SECTION 5: DETAILED ANALYSIS OF DIVERGENCES
# ============================================================================

if comparison_issues:
    print("\n" + "=" * 140)
    print("SECTION 5: DETAILED ANALYSIS OF DIVERGENCES")
    print("=" * 140 + "\n")

    for issue in comparison_issues:
        sym = issue["symbol"]
        data = screener_by_symbol.get(sym, {})

        print(f"\n{sym}:")
        print(f"  YFinance Price:    {issue['yfinance']:.2f} (Reference)")
        print(f"  Railway Price:     {issue['railway']:.2f}")
        print(f"  Divergence:        {issue['divergence']:.2f}%")
        print(f"  Railway Grade:     {data.get('setup_grade', 'N/A')}")
        print(f"  Railway Score:     {data.get('score', 'N/A')}")
        print(f"  Market Status:     {yf_results.get(sym, {}).get('market_status', 'Unknown')}")
        print(f"  Likely Cause:      Price data {'STALE/DELAYED' if issue['divergence'] > 5 else 'OK (market hours)'}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 140)
print("AUDIT SUMMARY")
print("=" * 140 + "\n")

print(f"[Symbols Tested]    {len(TEST_SYMBOLS)}/12 from screener")
print(f"[YFinance Available] {sum(1 for d in yf_results.values() if d.get('yfinance_price'))}/{len(TEST_SYMBOLS)}")
print(f"[Railway Available]  {sum(1 for s in TEST_SYMBOLS if s in screener_by_symbol)}/{len(TEST_SYMBOLS)}")
print(f"[Divergence Issues]  {divergence_count}/{len(TEST_SYMBOLS)} (>3% difference)")

if comparison_issues:
    print(f"\n[Problem Symbols]")
    for issue in comparison_issues:
        print(f"  {issue['symbol']}: {issue['divergence']:.1f}% divergence ({issue['status']})")

print(f"\n[VERDICT]")
if divergence_count == 0:
    print("[OK] All tested Actions have <3% price divergence")
    print("[OK] YFinance and Railway prices are in good agreement")
else:
    print(f"[WARN] {divergence_count} Action(s) with significant divergence (>3%)")
    print("       Possible causes: stale Railway cache, market hours differences, delayed yfinance data")

print(f"\n[END] {datetime.now(timezone.utc).isoformat()}")
