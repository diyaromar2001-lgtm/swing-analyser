#!/usr/bin/env python3
"""
Diagnose which provider is being used for intraday data
and compare with actual market prices from multiple sources
"""

import httpx
import pandas as pd
import time
import json
from typing import Optional, Dict, Any

SYMBOLS = ["TON", "MKR", "ETH", "BTC", "SOL"]

# Mapping for different exchanges
COINGECKO_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "TON": "the-open-network",
    "MKR": "maker",
}

KRAKEN_PAIRS = {
    "BTC": "XXBTZUSD",
    "ETH": "XETHZUSD",
    "SOL": "SOLDUSD",
    "BNB": "BNBUSD",
    "XRP": "XXRPZUSD",
}

def get_coingecko_price(symbol: str) -> Optional[Dict[str, Any]]:
    """Get current price from CoinGecko"""
    try:
        cg_id = COINGECKO_MAP.get(symbol)
        if not cg_id:
            return None

        url = f"https://api.coingecko.com/api/v3/simple/price"
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"ids": cg_id, "vs_currencies": "usd"})
            r.raise_for_status()
            data = r.json()
            price = data.get(cg_id, {}).get("usd")
            return {"provider": "CoinGecko", "symbol": symbol, "price": price}
    except Exception as e:
        return {"provider": "CoinGecko", "symbol": symbol, "error": str(e)}

def get_coinbase_candle(symbol: str) -> Optional[Dict[str, Any]]:
    """Get latest candle from Coinbase Pro API"""
    try:
        pair = f"{symbol}-USD"
        url = "https://api.exchange.coinbase.com/products/{}/candles".format(pair)
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"granularity": 300, "limit": 1})
            r.raise_for_status()
            raw = r.json()
            if raw:
                time_val, low, high, open_val, close, vol = raw[0]
                return {
                    "provider": "Coinbase",
                    "symbol": symbol,
                    "pair": pair,
                    "timestamp": time_val,
                    "close": close,
                    "open": open_val,
                    "high": high,
                    "low": low,
                    "volume": vol,
                }
    except Exception as e:
        return {"provider": "Coinbase", "symbol": symbol, "error": str(e)}
    return None

def get_kraken_candle(symbol: str) -> Optional[Dict[str, Any]]:
    """Get latest candle from Kraken API"""
    try:
        pair = KRAKEN_PAIRS.get(symbol, symbol + "USD")
        url = "https://api.kraken.com/0/public/OHLC"
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"pair": pair, "interval": 5})
            r.raise_for_status()
            data = r.json()
            ohlc_data = data.get("result", {}).get(pair, [])
            if ohlc_data:
                latest = ohlc_data[-1]
                time_val, open_val, high, low, close, vwap, vol, count = latest
                return {
                    "provider": "Kraken",
                    "symbol": symbol,
                    "pair": pair,
                    "timestamp": time_val,
                    "close": close,
                    "open": open_val,
                    "high": high,
                    "low": low,
                    "volume": vol,
                }
    except Exception as e:
        return {"provider": "Kraken", "symbol": symbol, "pair": KRAKEN_PAIRS.get(symbol, symbol + "USD"), "error": str(e)}
    return None

def get_okx_candle(symbol: str) -> Optional[Dict[str, Any]]:
    """Get latest candle from OKX API"""
    try:
        inst_id = f"{symbol}-USD"
        url = "https://www.okx.com/api/v5/market/candles"
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params={"instId": inst_id, "bar": "5m", "limit": 1})
            r.raise_for_status()
            data = r.json()
            candles = data.get("data", [])
            if candles:
                latest = candles[0]
                time_ms, open_val, high, low, close, vol, vol_ccy, vol_ccy_quote, confirm = latest
                return {
                    "provider": "OKX",
                    "symbol": symbol,
                    "inst_id": inst_id,
                    "timestamp": int(time_ms) // 1000,  # Convert ms to seconds
                    "close": close,
                    "open": open_val,
                    "high": high,
                    "low": low,
                    "volume": vol,
                }
    except Exception as e:
        return {"provider": "OKX", "symbol": symbol, "error": str(e)}
    return None

print("=" * 120)
print("INTRADAY PROVIDER DIAGNOSIS")
print("=" * 120)
print()

for symbol in SYMBOLS:
    print(f"\n{'=' * 120}")
    print(f"SYMBOL: {symbol}")
    print('=' * 120)

    # Get CoinGecko price (universal reference)
    cg = get_coingecko_price(symbol)
    print(f"\nCoinGecko Reference Price:")
    if "error" in cg:
        print(f"  ERROR: {cg.get('error')}")
    else:
        print(f"  Price: {cg.get('price')} USD")

    # Get Coinbase data
    print(f"\nCoinbase 5m Candle:")
    cb = get_coinbase_candle(symbol)
    if cb and "error" in cb:
        print(f"  ERROR: {cb.get('error')}")
    elif cb:
        print(f"  Pair: {cb.get('pair')}")
        print(f"  Close: {cb.get('close')} USD")
        print(f"  Timestamp: {cb.get('timestamp')} (unix)")
        if cg.get('price'):
            pct_diff = (float(cb.get('close')) - float(cg.get('price'))) / float(cg.get('price')) * 100
            print(f"  vs CoinGecko: {pct_diff:+.2f}%")
    else:
        print(f"  ERROR: No data returned")

    # Get Kraken data
    print(f"\nKraken 5m Candle:")
    kr = get_kraken_candle(symbol)
    if kr and "error" in kr:
        print(f"  Pair Attempted: {kr.get('pair')}")
        print(f"  ERROR: {kr.get('error')}")
    elif kr:
        print(f"  Pair: {kr.get('pair')}")
        print(f"  Close: {kr.get('close')} USD")
        print(f"  Timestamp: {kr.get('timestamp')} (unix)")
        if cg.get('price'):
            pct_diff = (float(kr.get('close')) - float(cg.get('price'))) / float(cg.get('price')) * 100
            print(f"  vs CoinGecko: {pct_diff:+.2f}%")
    else:
        print(f"  ERROR: No data returned")

    # Get OKX data
    print(f"\nOKX 5m Candle:")
    okx = get_okx_candle(symbol)
    if okx and "error" in okx:
        print(f"  Inst ID: {okx.get('inst_id')}")
        print(f"  ERROR: {okx.get('error')}")
    elif okx:
        print(f"  Inst ID: {okx.get('inst_id')}")
        print(f"  Close: {okx.get('close')} USD")
        print(f"  Timestamp: {okx.get('timestamp')} (unix)")
        if cg.get('price'):
            pct_diff = (float(okx.get('close')) - float(cg.get('price'))) / float(cg.get('price')) * 100
            print(f"  vs CoinGecko: {pct_diff:+.2f}%")
    else:
        print(f"  ERROR: No data returned")

print("\n\n" + "=" * 120)
print("SUMMARY TABLE")
print("=" * 120)
print()

# Collect all data
data_map = {}
for symbol in SYMBOLS:
    data_map[symbol] = {
        "coingecko": get_coingecko_price(symbol),
        "coinbase": get_coinbase_candle(symbol),
        "kraken": get_kraken_candle(symbol),
        "okx": get_okx_candle(symbol),
    }
    time.sleep(0.1)  # Rate limiting

print(f"{'Symbol':<8} {'CoinGecko':<12} {'Coinbase':<12} {'Kraken':<12} {'OKX':<12} {'Divergence':<15}")
print("-" * 120)

for symbol in SYMBOLS:
    cg_price = data_map[symbol]["coingecko"].get("price", "ERROR")
    cb_close = data_map[symbol]["coinbase"].get("close", "ERROR")
    kr_close = data_map[symbol]["kraken"].get("close", "ERROR")
    okx_close = data_map[symbol]["okx"].get("close", "ERROR")

    # Check divergence
    prices = []
    if isinstance(cg_price, (int, float)):
        prices.append(float(cg_price))
    if isinstance(cb_close, (int, float)):
        prices.append(float(cb_close))
    if isinstance(kr_close, (int, float)):
        prices.append(float(kr_close))
    if isinstance(okx_close, (int, float)):
        prices.append(float(okx_close))

    if prices:
        divergence = (max(prices) - min(prices)) / min(prices) * 100
        divergence_str = f"{divergence:.2f}%"
    else:
        divergence_str = "N/A"

    print(f"{symbol:<8} {str(cg_price):<12} {str(cb_close):<12} {str(kr_close):<12} {str(okx_close):<12} {divergence_str:<15}")

print("\n" + "=" * 120)
print("END OF DIAGNOSIS")
print("=" * 120)
