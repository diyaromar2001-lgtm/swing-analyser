# INTRADAY PROVIDERS EVALUATION REPORT

**Date:** 2026-05-06  
**Time:** 21:09 UTC  
**Objective:** Find alternative to Binance (HTTP 451 blocked from Railway)  
**Test Method:** `/api/debug/intraday-providers/{symbol}` endpoint  
**Symbols Tested:** BTC, ETH, SOL, BNB, XRP (Tier 1 + sample)

---

## EXECUTIVE SUMMARY

**✅ 4 viable alternatives found to Binance**

| Provider | Status | 5m Data | Candles | Speed | Symbols | Recommendation |
|----------|--------|---------|---------|-------|---------|-----------------|
| **Coinbase** | ✅ | Native | 350 | 24-176ms | BTC,ETH,SOL,BNB,XRP (5/5) | **PRIMARY** |
| **Kraken** | ✅ | Native | 721 | 37-185ms | BTC,ETH,BNB,XRP (4/5) | SECONDARY |
| **OKX** | ✅ | Native | 100 | 189-253ms | BTC,ETH,SOL,BNB,XRP (5/5) | TERTIARY |
| **CryptoCompare** | ✅ | 1m (agg) | 61 | 171-200ms | BTC,ETH,SOL,BNB,XRP (5/5) | FALLBACK |
| **ByBit** | ❌ | N/A | 0 | N/A | BLOCKED | DO NOT USE |

---

## DETAILED PROVIDER ANALYSIS

### 1. COINBASE PRO (RECOMMENDED PRIMARY)

**Connectivity:** ✅ HTTP 200 from Railway  
**Data Format:** Native 5m OHLCV candles  
**Coverage:** All 5 Tier 1 symbols  

**Performance by Symbol:**

| Symbol | Status | Candles | Time | Sample |
|--------|--------|---------|------|--------|
| BTC | ✅ | 350 | 24ms | [1778101500, 81452.36, 81511.56, 81459.17, 81491.14] |
| ETH | ✅ | 350 | 32ms | Similar structure |
| SOL | ✅ | 350 | 29ms | Similar structure |
| BNB | ✅ | 350 | 176ms | Similar structure |
| XRP | ✅ | 350 | 134ms | Similar structure |

**Specification:**
```
API: https://api.exchange.coinbase.com/products/{PAIR}/candles
Pair Format: {SYMBOL}-USD (BTC-USD, ETH-USD, SOL-USD, etc.)
Parameters:
  - granularity: 300 (seconds = 5 minutes)
  - limit: 300 (default)
Response: [[timestamp, low, high, open, close, volume], ...]
Auth: None required (public endpoint)
Rate Limit: Unknown but appears stable
```

**Advantages:**
- ✅ Fastest response (24-176ms)
- ✅ 350 candles per request (~29 hours @ 5m)
- ✅ Pure 5m native data
- ✅ All 5 tier 1 symbols supported
- ✅ No authentication required
- ✅ Well-maintained Coinbase API
- ✅ Industry-standard crypto exchange

**Disadvantages:**
- ⚠️ Only 350 candles (enough for ~29 hours of data)
- ⚠️ If Coinbase blocks Railway later, need fallback

---

### 2. KRAKEN API (RECOMMENDED SECONDARY)

**Connectivity:** ✅ HTTP 200 from Railway  
**Data Format:** Native 5m OHLCV candles  
**Coverage:** 4/5 symbols (SOL fails)  

**Performance by Symbol:**

| Symbol | Status | Candles | Time | Issue |
|--------|--------|---------|------|-------|
| BTC | ✅ | 721 | 37ms | - |
| ETH | ✅ | 721 | 166ms | - |
| SOL | ❌ | 0 | - | HTTP 200 but empty data |
| BNB | ✅ | 721 | 176ms | - |
| XRP | ✅ | 721 | 185ms | - |

**Specification:**
```
API: https://api.kraken.com/0/public/OHLC
Pair Format: X{SYMBOL}ZUSD (XXBTZUSD=BTC-USD, XETHZUSD=ETH-USD)
             Special: SOLDUSD (not XSOLZUSD), BNBUSD, XXRPZUSD
Parameters:
  - pair: Kraken pair ID
  - interval: 5 (minutes)
Response: {"result": {pair: [[time, o, h, l, c, vwap, volume, count], ...]}}
Auth: None required (public endpoint)
Rate Limit: Unknown
```

**Advantages:**
- ✅ 721 candles per request (~60 hours @ 5m) - EXCELLENT
- ✅ Very fast (37-185ms)
- ✅ 4/5 tier 1 symbols supported
- ✅ No authentication required
- ✅ Kraken is major, stable exchange

**Disadvantages:**
- ❌ SOL fails to return data
- ⚠️ Non-standard pair naming (X prefix, Z suffix for USD)
- ⚠️ If SOL needed, must fallback to other provider

---

### 3. OKX API (TERTIARY)

**Connectivity:** ✅ HTTP 200 from Railway  
**Data Format:** Native 5m OHLCV candles  
**Coverage:** All 5 Tier 1 symbols  

**Performance by Symbol:**

| Symbol | Status | Candles | Time |
|--------|--------|---------|------|
| BTC | ✅ | 100 | 189ms |
| ETH | ✅ | 100 | 190ms |
| SOL | ✅ | 100 | 195ms |
| BNB | ✅ | 100 | 184ms |
| XRP | ✅ | 100 | 253ms |

**Specification:**
```
API: https://www.okx.com/api/v5/market/candles
Pair Format: {SYMBOL}-USD (BTC-USD, ETH-USD, SOL-USD, etc.)
Parameters:
  - instId: {SYMBOL}-USD
  - bar: 5m
  - limit: 100
Response: [[timestamp_ms, open, high, low, close, vol, vol_ccy, vol_ccy_quote, confirm], ...]
Auth: None required (public endpoint)
Rate Limit: Appears stable
```

**Advantages:**
- ✅ All 5 tier 1 symbols supported
- ✅ Simple naming convention
- ✅ No authentication required
- ✅ OKX is major exchange

**Disadvantages:**
- ❌ Only 100 candles per request (~8 hours @ 5m)
- ⚠️ Slower than Coinbase (184-253ms)
- ⚠️ Fewer historical candles limits lookback

---

### 4. CRYPTOCOMPARE API (FALLBACK ONLY)

**Connectivity:** ✅ HTTP 200 from Railway  
**Data Format:** 1-minute candles (can aggregate to 5m)  
**Coverage:** All 5 Tier 1 symbols  

**Performance by Symbol:**

| Symbol | Status | Points (1m) | Time | Note |
|--------|--------|-------------|------|------|
| BTC | ✅ | 61 | 171ms | 1m only |
| ETH | ✅ | 61 | 186ms | 1m only |
| SOL | ✅ | 61 | 196ms | 1m only |
| BNB | ✅ | 61 | 182ms | 1m only |
| XRP | ✅ | 61 | 200ms | 1m only |

**Specification:**
```
API: https://min-api.cryptocompare.com/data/v2/histominute
Parameters:
  - fsym: BTC, ETH, SOL, etc.
  - tsym: USD
  - limit: 60 (get 60 minutes)
  - aggregate: 1 (1 minute bars)
Response: {"Data": {"Data": [{time, high, low, open, volumefrom, volumeto, close, ...}, ...]}}
Auth: None required (free tier)
Rate Limit: Free tier available, paid tiers for higher limits
```

**Advantages:**
- ✅ All 5 tier 1 symbols supported
- ✅ Free tier available
- ✅ Reliable provider

**Disadvantages:**
- ❌ Only 1-minute candles (must aggregate manually)
- ❌ Only 61 points (~1 hour @ 1m, ~12 hours @ 5m after aggregation)
- ❌ Slowest response (171-200ms)
- ⚠️ 1m→5m aggregation adds complexity & potential artifacts

---

### 5. BYBIT (NOT VIABLE)

**Connectivity:** ❌ HTTP 403 from Railway  
**Error:** `"The Amazon CloudFront distribution is configured to block access from your country"`  
**Status:** Do NOT use - explicitly blocked by ByBit infrastructure  

---

## RATE LIMITING & STABILITY

### Current Observations

**Coinbase:**
- No rate limiting observed
- Consistent fast responses (24-176ms)
- Appears stable for production use

**Kraken:**
- No rate limiting observed  
- Fast responses (37-185ms)
- 721 candles per call = less frequent requests needed

**OKX:**
- No rate limiting observed
- Stable responses (184-253ms)
- Lower candle count might trigger more frequent updates

**CryptoCompare:**
- Free tier available
- Response times stable (171-200ms)
- 1m data requires aggregation

---

## RECOMMENDATION & IMPLEMENTATION PLAN

### PRIMARY: Coinbase Pro

**Why Coinbase:**
1. ✅ Fastest response times (24-176ms)
2. ✅ All 5 Tier 1 symbols covered
3. ✅ 350 candles = ~29 hours lookback (good for scalp signals)
4. ✅ Native 5m data (no aggregation needed)
5. ✅ Industry standard, stable
6. ✅ No authentication required
7. ✅ Simple API contract

**When Coinbase fails:** Fall back to Kraken (or OKX if Kraken SOL issue continues)

### SECONDARY: Kraken

**Why Kraken as backup:**
1. ✅ 721 candles = ~60 hours lookback (excellent)
2. ✅ Fast (37-185ms)
3. ✅ 4/5 symbols OK
4. ❌ SOL fails (requires OKX fallback)

**When Kraken fails:** Fall back to OKX

### TERTIARY: OKX

**Why OKX as final fallback:**
1. ✅ All 5 symbols covered
2. ✅ Stable
3. ❌ Only 100 candles (~8 hours)
4. ❌ Slower (184-253ms)

### NOT VIABLE: CryptoCompare

- Only use if real 5m providers all fail
- 1m data requires aggregation (adds 5 minutes of lookback loss)
- Less suitable for scalp signals

---

## IMPLEMENTATION APPROACH

```python
def get_crypto_ohlcv_intraday_with_fallback(
    symbol: str,
    interval: str = "5m",
    allow_download: bool = True
) -> Optional[pd.DataFrame]:
    """
    Fetch intraday OHLCV with provider fallback:
    1. Try Binance (works locally, blocked at Railway)
    2. Try Coinbase (primary fallback)
    3. Try Kraken (secondary)
    4. Try OKX (tertiary)
    5. Return None if all fail
    """
    
    # Try Binance first (works locally)
    df = _fetch_binance_klines(...)
    if df is not None and len(df) >= 20:
        return df  # Success
    
    if not allow_download:
        return None
    
    # Fallback: Try Coinbase
    df = _fetch_coinbase_klines(symbol, granularity=300, limit=300)
    if df is not None and len(df) >= 20:
        return df  # Success
    
    # Fallback: Try Kraken
    if symbol != "SOL":  # Skip SOL (known issue)
        df = _fetch_kraken_ohlc(symbol, interval=5)
        if df is not None and len(df) >= 20:
            return df
    
    # Fallback: Try OKX
    df = _fetch_okx_candles(symbol, bar="5m")
    if df is not None and len(df) >= 20:
        return df
    
    # Fallback: Try CryptoCompare 1m and aggregate
    df = _fetch_cryptocompare_minute(symbol)
    if df is not None and len(df) >= 100:  # Need 100 1m bars = 20 5m bars
        df = _aggregate_1m_to_5m(df)
        return df
    
    # All providers failed
    return None
```

---

## FILES TO MODIFY (ESTIMATED)

1. **backend/crypto_data.py**
   - Add `_fetch_coinbase_klines()`
   - Add `_fetch_kraken_ohlc()`
   - Add `_fetch_okx_candles()`
   - Modify `get_crypto_ohlcv_intraday()` to try fallbacks
   - Update logging to show which provider succeeded

2. **backend/crypto_scalp_service.py**
   - No changes needed (uses `get_crypto_ohlcv_intraday()`)

3. **Logs/Reporting**
   - Add `data_provider` field to responses (BINANCE / COINBASE / KRAKEN / OKX)
   - Add `fallback_reason` if fallback used
   - Show response times per provider

---

## TESTS REQUIRED (POST-IMPLEMENTATION)

### Local Tests
- [ ] Coinbase API reachable locally
- [ ] Kraken API reachable locally
- [ ] OKX API reachable locally
- [ ] Correct OHLCV format parsing for each provider
- [ ] Fallback chain works correctly
- [ ] Warmup with fallback succeeds

### Production Tests (Railway)
- [ ] POST /api/crypto/scalp/warmup-intraday?tier=1 returns 5/5 success
- [ ] Each symbol shows correct provider in logs
- [ ] Cache populated with 300+ candles minimum
- [ ] /api/cache-status shows crypto_intraday_5m_cache_count > 0

### Vercel UI Tests
- [ ] Dashboard shows real data for Tier 1 symbols
- [ ] Crypto Scalp screener shows non-UNAVAILABLE status
- [ ] Confidence scores calculated
- [ ] Phase 3A fields populated

---

## RISKS & MITIGATION

| Risk | Mitigation |
|------|-----------|
| Provider also gets blocked | Multiple fallbacks (Coinbase→Kraken→OKX→CryptoCompare) |
| Different data quality | Monitor provider accuracy vs Binance locally |
| Rate limiting later | Increase cache TTL, extend candle lookback |
| Kraken SOL issue | Fallback to OKX for SOL specifically |
| CryptoCompare 1m aggregation artifacts | Only use as last resort |

---

## SECURITY & COMPLIANCE

- ✅ No authentication keys required (public APIs)
- ✅ No Terms of Service violations (all providers allow public API access)
- ✅ Data sourced from legitimate exchanges
- ✅ No leverage, Real trading, or unsecured operations
- ✅ Follows project constraints

---

## SUMMARY TABLE

| Aspect | Coinbase | Kraken | OKX | CryptoCompare |
|--------|----------|--------|-----|---------------|
| **Viability** | PRIMARY | SECONDARY | TERTIARY | FALLBACK |
| **Symbols** | 5/5 | 4/5 | 5/5 | 5/5 |
| **Candles** | 350 | 721 | 100 | 61 (1m) |
| **Speed** | 24-176ms | 37-185ms | 184-253ms | 171-200ms |
| **Data Quality** | Native 5m | Native 5m | Native 5m | 1m (agg) |
| **Production Ready** | ✅ YES | ✅ YES | ⚠️ Slower | ⚠️ Complex |

---

**Next Step:** Await your approval to proceed with implementation of Coinbase/Kraken/OKX fallback chain.

**Files:** `/api/debug/intraday-providers/{symbol}` endpoint available on Railway for continued testing if needed.

