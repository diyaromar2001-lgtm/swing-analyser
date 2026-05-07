#!/usr/bin/env python3
"""
COMPREHENSIVE ACTIONS AUDIT
Tests important Actions symbols for price data quality and provider reliability
"""

import yfinance as yf
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Any

# ============================================================================
# TEST ACTIONS SELECTION
# ============================================================================

# Select important Actions from different sectors
TEST_ACTIONS = [
    # Technology (Mega cap)
    ("AAPL", "Technology", "Mega cap"),
    ("MSFT", "Technology", "Mega cap"),
    ("NVDA", "Technology", "AI/Semis"),
    ("GOOGL", "Technology", "Mega cap"),

    # Healthcare
    ("UNH", "Healthcare", "Large cap"),
    ("JNJ", "Healthcare", "Pharma"),

    # Financials
    ("JPM", "Financials", "Large cap"),
    ("V", "Financials", "Payments"),

    # Energy
    ("XOM", "Energy", "Integrated"),

    # Industrials
    ("GE", "Industrials", "Conglomerate"),

    # Consumer
    ("PG", "Consumer Staples", "Large cap"),
    ("AMZN", "Consumer Discretionary", "E-commerce"),

    # Auto
    ("TSLA", "Auto", "EV"),
]

RAILWAY_URL = "https://swing-analyser-production.up.railway.app"

# ============================================================================
# TEST ACTIONS ON YFINANCE (Local Reference)
# ============================================================================

def test_yfinance_prices():
    """Test actions prices on yfinance (reference provider)"""
    print("\n" + "=" * 140)
    print("SECTION 1: YFINANCE REFERENCE PRICES (LOCAL)")
    print("=" * 140 + "\n")

    results = {}

    print(f"{'Symbol':<8} {'Sector':<25} {'Type':<20} {'Current Price':<15} {'Market Status':<20}")
    print("-" * 140)

    for symbol, sector, atype in TEST_ACTIONS:
        try:
            ticker = yf.Ticker(symbol)

            # Get current price
            hist = ticker.history(period="5d")
            if hist.empty:
                price = None
                status = "NO DATA"
            else:
                price = hist['Close'].iloc[-1]

                # Check if market is open
                info = ticker.info
                is_open = info.get("marketState") == "OPEN" if "marketState" in info else None

                if is_open is None:
                    status = "Unknown"
                elif is_open:
                    status = "MARKET OPEN"
                else:
                    status = "MARKET CLOSED"

            results[symbol] = {
                "sector": sector,
                "type": atype,
                "yfinance_price": price,
                "market_status": status
            }

            print(f"{symbol:<8} {sector:<25} {atype:<20} {str(price):<15} {status:<20}")

        except Exception as e:
            results[symbol] = {
                "sector": sector,
                "type": atype,
                "error": str(e),
                "yfinance_price": None
            }
            print(f"{symbol:<8} {sector:<25} {atype:<20} ERROR: {str(e):<10}")

    return results

# ============================================================================
# TEST ACTIONS ON RAILWAY
# ============================================================================

def test_railway_actions():
    """Test actions on Railway screener API"""
    print("\n" + "=" * 140)
    print("SECTION 2: RAILWAY ACTIONS SWING SCREENER")
    print("=" * 140 + "\n")

    results = {}
    all_screener_data = {}

    try:
        # Get full screener data first
        url = f"{RAILWAY_URL}/api/screener"
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            if r.status_code == 200:
                screener_data = r.json()
                for item in screener_data:
                    symbol = item.get("symbol")
                    if symbol:
                        all_screener_data[symbol] = item
    except Exception as e:
        print(f"[Error fetching screener] {e}")

    print(f"{'Symbol':<8} {'Status':<15} {'Current Price':<15} {'Provider':<15} {'Grade':<10} {'Long':<8} {'Short':<8}")
    print("-" * 140)

    for symbol, sector, atype in TEST_ACTIONS:
        if symbol in all_screener_data:
            data = all_screener_data[symbol]
            results[symbol] = {
                "http_status": 200,
                "current_price": data.get("current_price"),
                "price_source": data.get("price_source"),
                "data_status": data.get("data_status"),
                "grade": data.get("grade"),
                "long_score": data.get("long_score"),
                "short_score": data.get("short_score"),
            }

            print(f"{symbol:<8} {data.get('data_status', 'UNKNOWN'):<15} {str(data.get('current_price', 'N/A')):<15} {str(data.get('price_source', 'N/A')):<15} {str(data.get('grade', 'N/A')):<10} {str(data.get('long_score', 'N/A')):<8} {str(data.get('short_score', 'N/A')):<8}")
        else:
            results[symbol] = {
                "http_status": 404,
                "error": "Not in screener"
            }
            print(f"{symbol:<8} NOT FOUND (404)")

    return results

# ============================================================================
# COMPARISON AND VALIDATION
# ============================================================================

def validate_prices(yf_results, railway_results):
    """Compare yfinance vs Railway prices"""
    print("\n" + "=" * 140)
    print("SECTION 3: PRICE COMPARISON - YFINANCE VS RAILWAY")
    print("=" * 140 + "\n")

    print(f"{'Symbol':<8} {'YFinance':<15} {'Railway':<15} {'Divergence':<15} {'Status':<20}")
    print("-" * 140)

    comparison_results = {}

    for symbol, sector, atype in TEST_ACTIONS:
        yf_price = yf_results.get(symbol, {}).get("yfinance_price")
        railway_price = railway_results.get(symbol, {}).get("current_price")

        if yf_price and railway_price:
            divergence = abs(yf_price - railway_price) / yf_price * 100
            comparison_results[symbol] = {
                "yfinance_price": yf_price,
                "railway_price": railway_price,
                "divergence": divergence,
                "status": "OK" if divergence < 5 else "WARN" if divergence < 15 else "SUSPECT"
            }

            print(f"{symbol:<8} {str(yf_price):<15} {str(railway_price):<15} {divergence:.2f}%{'':<10} {comparison_results[symbol]['status']:<20}")
        else:
            print(f"{symbol:<8} {str(yf_price):<15} {str(railway_price):<15} N/A{'':<15} UNAVAILABLE")

    return comparison_results

# ============================================================================
# DETAILED ANALYSIS
# ============================================================================

def detailed_analysis(yf_results, railway_results):
    """Detailed analysis of each action"""
    print("\n" + "=" * 140)
    print("SECTION 4: DETAILED ANALYSIS BY ACTION")
    print("=" * 140 + "\n")

    for symbol, sector, atype in TEST_ACTIONS:
        print(f"\n{symbol} ({sector} - {atype}):")
        print("-" * 80)

        yf_data = yf_results.get(symbol, {})
        railway_data = railway_results.get(symbol, {})

        # YFinance data
        print(f"  YFinance:")
        print(f"    Current Price: {yf_data.get('yfinance_price', 'N/A')}")
        print(f"    Market Status: {yf_data.get('market_status', 'Unknown')}")

        # Railway data
        print(f"  Railway:")
        if railway_data.get("http_status") == 200:
            print(f"    Current Price: {railway_data.get('current_price', 'N/A')}")
            print(f"    Data Status:   {railway_data.get('data_status', 'Unknown')}")
            print(f"    Price Source:  {railway_data.get('price_source', 'Unknown')}")
            print(f"    Grade:         {railway_data.get('grade', 'N/A')}")
            print(f"    Long Score:    {railway_data.get('long_score', 'N/A')}")
            print(f"    Short Score:   {railway_data.get('short_score', 'N/A')}")
        else:
            print(f"    Status: {railway_data.get('error', 'Unknown error')}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "=" * 140)
    print("COMPREHENSIVE ACTIONS AUDIT")
    print("=" * 140)
    print(f"[START] {datetime.now(timezone.utc).isoformat()}")

    # Section 1: Test yfinance
    yf_results = test_yfinance_prices()

    # Section 2: Test Railway
    railway_results = test_railway_actions()

    # Section 3: Compare prices
    comparison_results = validate_prices(yf_results, railway_results)

    # Section 4: Detailed analysis
    detailed_analysis(yf_results, railway_results)

    # Summary
    print("\n" + "=" * 140)
    print("AUDIT SUMMARY")
    print("=" * 140)

    yf_available = sum(1 for d in yf_results.values() if d.get("yfinance_price"))
    railway_available = sum(1 for d in railway_results.values() if d.get("http_status") == 200)
    divergence_issues = sum(1 for c in comparison_results.values() if c.get("status") != "OK")

    print(f"[YFinance] {yf_available}/{len(TEST_ACTIONS)} symbols with data")
    print(f"[Railway]  {railway_available}/{len(TEST_ACTIONS)} symbols with data")
    print(f"[Issues]   {divergence_issues}/{len(comparison_results)} symbols with >5% divergence")

    if divergence_issues > 0:
        suspect_symbols = [s for s, c in comparison_results.items() if c.get("status") != "OK"]
        print(f"[Problems] {', '.join(suspect_symbols)}")

    print(f"\n[END] {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()
