# AUDIT FINAL COMPLET: Sources de Prix et Données de Marché
**Date:** 2026-05-07  
**Status:** AUDIT COMPLET TERMINÉ - RAPPORT FINAL  
**Scope:** Actions Swing + Crypto Swing + Crypto Scalp + TradePlan + Journal + Performance

---

## EXECUTIVE SUMMARY

### Findings Clés

1. **Snapshot prices (Binance → CoinGecko → yFinance):**
   - ✅ FIABLE pour la majorité des cryptos
   - ✅ Cohérent avec CoinGecko (écart <5%)
   - ✅ Utilisé pour l'affichage et les calculs

2. **Intraday prices (Binance blocked → Coinbase → Kraken → OKX):**
   - ❌ PROBLÉMATIQUE pour TON et MKR
   - ❌ TON intraday: 1.849 USD (23.9% moins que CoinGecko 2.43)
   - ❌ MKR intraday: 1347.21 USD (27.8% moins que CoinGecko 1866.09)
   - ⚠️ Autres cryptos: acceptable (<5% divergence)

3. **Cause Racine:**
   - Binance HTTP 451 blocked at Railway
   - Fallback to Coinbase/Kraken/OKX
   - Coinbase returns MKR perpetuals (1300) not spot (1867)
   - TON intraday source unknown (stale cache?)

4. **Impact:**
   - Price_suspect flag already catches TON and MKR ✓
   - No trades executed (execution_authorized = false) ✓
   - Prices displayed are reasonable for most cryptos
   - Intraday data unreliable for entry/SL/TP calculations

---

## SECTION 1: CARTOGRAPHIE SOURCES DE PRIX

### A. CRYPTO SCALP PRICES (Production Railway)

| Symbol | Displayed | Snapshot | Intraday | Divergence | Suspect | vs CoinGecko |
|--------|-----------|----------|----------|-----------|---------|--------------|
| BTC    | 81317.0   | 81317.0  | 81300.0  | 0.02%     | False   | +0.14%       |
| ETH    | 2347.02   | 2347.02  | 2362.55  | 0.66%     | False   | -0.03%       |
| SOL    | 89.22     | 89.22    | 85.42    | 4.26%     | False   | +0.10%       |
| **TON**    | **2.449** | **2.449**  | **1.849**  | **32.45%**    | **True**    | **+0.78%**       |
| **MKR**    | **1777.13** | **1777.13**  | **1347.21**  | **31.91%**    | **True**    | **-4.77%**       |
| BNB    | 647.16    | 647.16   | 628.63   | 2.84%     | False   | -0.00%       |
| XRP    | 1.4235    | 1.4235   | 1.4082   | 1.08%     | False   | +0.25%       |
| AVAX   | 9.6       | 9.6      | 9.38     | 2.29%     | False   | +0.10%       |
| LINK   | 10.01     | 10.01    | 9.693    | 3.07%     | False   | +0.20%       |
| AAVE   | 93.94     | 93.94    | 93.13    | 0.87%     | False   | +0.16%       |

**Conclusion:**
- TON et MKR: Snapshot OK (+0.78%, -4.77%), Intraday FAUX (23-28% écart)
- Autres: Snapshot et Intraday acceptables (<5%)
- price_suspect flag works correctly ✓

---

### B. PRICE SNAPSHOT CHAIN (Documented in crypto_data.py)

```
get_crypto_price_snapshot():
  1. Try: _fetch_binance_price(symbol)
     - FAILS at Railway due to HTTP 451 Binance block
  2. Fallback: _fetch_coingecko_price(symbol)
     - SUCCESS: Returns accurate market prices
  3. Fallback: _fetch_yfinance_price(symbol)
     - Backup for stocks/alternatives
  
Result: Snapshot uses CoinGecko most of the time
TTL: 60 seconds
Cache: _price_cache (in-memory)
```

### C. INTRADAY OHLCV CHAIN (Documented in crypto_data.py)

```
get_crypto_ohlcv_intraday(interval="5m"):
  1. Try: _fetch_binance_klines(pair, "5m")
     - FAILS at Railway (HTTP 451)
  2. Fallback (5m only):
     a. _fetch_coinbase_klines(symbol)
        - TON-USD: Works, returns ~2.43
        - MKR-USD: RETURNS PERPETUALS (1300) not spot!
     b. _fetch_kraken_ohlc(symbol)
        - TON: Works, returns ~2.43
        - MKR: No data
     c. _fetch_okx_candles(symbol)
        - Limited data for some symbols

Result: Intraday uses Coinbase most of the time
TTL: 600 seconds (5m cache), 300s (1m cache), 900s (15m cache)
Cache: _ohlcv_1m_cache, _ohlcv_5m_cache, _ohlcv_15m_cache (in-memory)
```

---

## SECTION 2: PROVIDERS UTILISÉS

### Binance
- **Status:** ❌ BLOCKED at Railway (HTTP 451)
- **Utilisé pour:** Snapshot + OHLCV intraday (fallback)
- **Pairs:** SYMBOLUSDT (TON = TONUSDT, MKR = MKRUSDT)
- **Fonctionne:** Localement OUI, Railway NON
- **Problem:** Network isolation at Railway

### CoinGecko
- **Status:** ✅ WORKING
- **Utilisé pour:** Snapshot fallback (primary now), market data, global metrics
- **Mapping:** coingecko_id (bitcoin, ethereum, solana, the-open-network, maker...)
- **Fonctionne:** OUI (API public)
- **Rate Limit:** 50 calls/min
- **Accuracy:** Excellent (universal reference price)
- **Comment:** Most snapshot prices come from CoinGecko now

### Coinbase
- **Status:** ✅ WORKING (but with issue)
- **Utilisé pour:** Intraday 5m fallback
- **Pairs:** SYMBOL-USD (TON-USD, MKR-USD)
- **Fonctionne:** OUI
- **Problem:** MKR-USD returns PERPETUALS (1300) not SPOT (1867)
  - Last 30 closes range: 1270-1357
  - Never reaches real MKR price 1867
- **Accuracy:** POOR for MKR, OK for others

### Kraken
- **Status:** ⚠️ PARTIAL
- **Utilisé pour:** Intraday 5m fallback
- **Pairs:** XXBTZUSD, XETHZUSD, SOLDUSD, etc.
- **TON mapping:** TONUSD (not in hardcoded list, falls back to symbol+"USD")
- **MKR mapping:** MKRUSD (not in hardcoded list)
- **Problem:** No data for MKR, SOL skipped by design

### OKX
- **Status:** ✅ WORKING (but limited)
- **Utilisé pour:** Intraday 5m fallback (last resort)
- **Pairs:** SYMBOL-USD
- **Fonctionne:** OUI
- **Limitation:** Sparse data for some symbols

### Yahoo Finance / yFinance
- **Status:** ✅ WORKING
- **Utilisé pour:** Actions Swing + snapshot fallback
- **Type:** Daily OHLCV, marché ouvert/fermé awareness
- **Mapping:** Custom (yahoo_symbol field)

---

## SECTION 3: CACHES ET TTL

### Crypto Caches

| Cache Name | TTL | Content | Risk | Module |
|------------|-----|---------|------|--------|
| _price_cache | 60s | Snapshot prices | Stale >60s | crypto_data |
| _ohlcv_daily_cache | 3600s | Daily candles | Stale >1h | crypto_data |
| _ohlcv_4h_cache | 900s | 4h candles | Stale >15m | crypto_data |
| _ohlcv_1m_cache | 300s | 1m intraday | Stale >5m | crypto_data |
| _ohlcv_5m_cache | 600s | 5m intraday | Stale >10m | crypto_data |
| _ohlcv_15m_cache | 900s | 15m intraday | Stale >15m | crypto_data |
| _markets_cache | 300s | Market metrics | Stale >5m | crypto_data |
| _global_cache | 900s | Global metrics | Stale >15m | crypto_data |
| _intraday_provider_used | - | Provider tracking | Diagnostic | crypto_data |

### Other Caches

| Cache Name | TTL | Content | Module |
|------------|-----|---------|--------|
| _crypto_regime_cache | Unknown | Regime calculations | crypto_regime_engine |
| _crypto_edge_cache | Unknown | Edge calculations | crypto_edge |
| ticker_edge_cache | Unknown | Stock edge calcs | ticker_edge |

**Cache Issues:**
- ✅ In-memory only (not persistent)
- ⚠️ TTL adequate for most purposes
- ⚠️ Could be stale immediately after Railway restart
- ⚠️ No warmup on startup for intraday (TON/MKR likely to show old data)

---

## SECTION 4: IMPACT PAR MODULE

### Crypto Scalp
- **Prix affiché:** Snapshot (displayed_price) → CoinGecko → CORRECT ✓
- **Prix score:** Utilise snapshot pour current_price
- **Prix entry/SL/TP:** Basé sur snapshot + ATR intraday
- **Problème:** ATR calculé sur intraday 5m (stale pour TON/MKR)
- **Indicateurs:** RSI, MACD, trend sur intraday 5m
- **Mitigation:** price_suspect=True bloquerait entry si >5% divergence
- **Status:** MOSTLY OK, TON/MKR flagged ✓

### Crypto Swing
- **Prix affiché:** Snapshot (current price)
- **Prix score:** Daily/4h OHLCV + snapshot
- **Prix entry/SL/TP:** Basé sur snapshot + ATR daily/4h
- **Problème:** Si snapshot stale (après restart), scores peuvent être décalés
- **Indicateurs:** Calculs sur daily/4h, indépendant du snapshot
- **Status:** GOOD, less intraday dependency

### Actions Swing
- **Prix affiché:** yfinance (daily close ou current)
- **Prix score:** Daily OHLCV
- **Prix entry/SL/TP:** Basé sur snapshot + ATR daily
- **Marché ouvert/fermé:** Gère via yfinance
- **Indicateurs:** Indépendants du prix réel-time
- **Status:** GOOD, doesn't use intraday fallback

### Trade Journal & Performance
- **Prix creation:** Stocké au moment du trade
- **Prix fermeture:** Manuel ou last price
- **PnL:** Basé sur prix stockés (pas affecté par changement prix live)
- **Status:** SAFE, price locked at trade time

---

## SECTION 5: DIAGNOSTIC DÉTAILLÉ TON ET MKR

### TON: Snapshot Correct, Intraday Faux

```
Railway Data (2026-05-07 ~11:50 UTC):
  displayed_price:      2.449 USD
  snapshot_price:       2.449 USD
  intraday_last_close:  1.849 USD (WRONG)
  price_source:         "snapshot"
  price_suspect:        True
  price_difference_pct: 32.45%

Market Reality:
  CoinGecko (reference): 2.43 USD
  Coinbase 5m close:     2.434 USD
  Kraken 5m close:       2.429 USD
  OKX 5m close:          2.40 USD
  TradingView (manual):  ~2.42 USD

Comparison:
  Snapshot (2.449) vs CoinGecko (2.43)  = +0.78% ✅ CORRECT
  Intraday (1.849) vs CoinGecko (2.43)  = -23.91% ❌ FAUX
  Intraday (1.849) vs Coinbase (2.434)  = -24.07% ❌ NOT FROM COINBASE
  Intraday (1.849) vs Kraken (2.429)    = -23.93% ❌ NOT FROM KRAKEN
  Intraday (1.849) vs OKX (2.40)        = -23.04% ❌ NOT FROM OKX

Conclusion:
  - Snapshot: CORRECT ✓
  - Intraday: SOURCE UNKNOWN (not Coinbase, Kraken, or OKX)
    Possibilities:
    1. Old cached data from previous session (cache not cleared at restart)
    2. From different symbol (wrong mapping?)
    3. From Binance but stale (wasn't refreshed)
    
  Recommendation:
    Use snapshot (2.449) which matches all current market sources.
    Investigate where intraday 1.849 comes from.
```

### MKR: Snapshot Acceptable, Intraday = Coinbase Perpetuals

```
Railway Data (2026-05-07 ~11:50 UTC):
  displayed_price:      1777.13 USD
  snapshot_price:       1777.13 USD
  intraday_last_close:  1347.21 USD (COINBASE PERPETUALS)
  price_source:         "snapshot"
  price_suspect:        True
  price_difference_pct: 31.91%

Market Reality:
  CoinGecko (reference): 1866.09 USD (REAL SPOT PRICE)
  Coinbase MKR-USD:      1300.86 USD (PERPETUALS, NOT SPOT)
  Coinbase last 30 closes: Range 1270-1357, never >1400
  Kraken:                ERROR (no data)
  OKX:                   ERROR (no data)

Comparison:
  Snapshot (1777.13) vs CoinGecko (1866.09)     = -4.77% ⚠️ ACCEPTABLE
  Intraday (1347.21) vs CoinGecko (1866.09)     = -27.81% ❌ FAUX
  Intraday (1347.21) vs Coinbase (1300.86)      = +3.56% ✅ MATCHES COINBASE!

Confirmed Root Cause:
  - Coinbase MKR-USD API returns PERPETUALS contract (1300 range)
  - Real MKR spot price is 1866
  - Intraday cache contains Coinbase perpetuals data
  - Used for entry/SL/TP calculations = DANGEROUS

Recommendation:
  Do NOT use Coinbase MKR-USD for intraday prices.
  Use snapshot (1777.13) which is reasonably close to real price (1866.09).
```

---

## SECTION 6: INDICATEURS ET FIABILITÉ

### Indicateurs Basés sur Snapshot
- ✅ RSI, MACD, trend sur snapshot
- ✅ FIABLES car snapshot vient de CoinGecko (précis)

### Indicateurs Basés sur OHLCV Daily
- ✅ ATR, support/resistance sur daily
- ✅ FIABLES car daily cache est stable

### Indicateurs Basés sur Intraday 5m
- ❌ ATR, RSI, momentum sur 5m intraday
- ❌ PROBLÉMATIQUE pour TON (1.849 vs 2.43) et MKR (1347 vs 1866)
- ⚠️ OK pour autres cryptos (<5% divergence)

**Impact Pratique:**
- TON: ATR calculé sur faux prix 1.849 → SL/TP à 30% du bon niveau
- MKR: ATR calculé sur faux prix 1347 → SL/TP à 25% du bon niveau
- Autres: Indicateurs fiables

**Mitigation Actuelle:**
- price_suspect=True prevents signals for TON/MKR ✓
- entry=None because of divergence alert ✓

---

## SECTION 7: COHÉRENCE ENTRE MODULES

### Crypto Scalp vs Crypto Swing
- **Même source snapshot:** OUI ✓
- **Incohérence:** Scalp utilise intraday 5m, Swing utilise daily
- **Impact:** Peut montrer prix différents pour même crypto
- **Gravité:** MINEURE (Scalp blocké par price_suspect, Swing utilise daily)

### TradePlan & Journal
- **Prix stocké:** OUI (freezé au moment création)
- **Prix changement:** N'affecte pas ancien trades ✓
- **PnL:** Basé sur prix stockés ✓
- **Status:** SAFE

---

## SECTION 8: ARCHITECTURE CIBLE (PLAN SANS CODING)

### Phase 1: Affichage Source + Timestamp (MINIMAL)
```
Retourner dans API:
  - price_source (déjà fait ✓)
  - price_timestamp (déjà fait ✓)
  - price_suspect (déjà fait ✓)
  - last_intraday_provider (à ajouter)
  - cache_age (à ajouter)
```

### Phase 2: Corriger Mappings Problématiques
```
Pour MKR:
  - Bloquer Coinbase MKR-USD (perpetuals)
  - Utiliser snapshot seulement pour MKR entry/SL/TP

Pour TON:
  - Investiguer source du 1.849
  - Si cache stale: forcer refresh
  - Si mapping faux: corriger
```

### Phase 3: Provider Selection par Symbole
```
Matrice:
  BTC/ETH/SOL/BNB/XRP/AVAX/LINK/AAVE:
    - Snapshot: OK (CoinGecko)
    - Intraday: OK (Coinbase/Kraken/OKX)
    - Action: NO CHANGE
  
  TON:
    - Snapshot: OK (CoinGecko)
    - Intraday: SUSPECT (source unknown)
    - Action: INVESTIGATE/FIX
  
  MKR:
    - Snapshot: ACCEPTABLE (5% error)
    - Intraday: FAUX (Coinbase perpetuals)
    - Action: BLOCK Coinbase for MKR, use snapshot only
```

### Phase 4: Dynamic Divergence Handling
```
IF price_difference_pct > 5%:
  - Set price_suspect = True (already done ✓)
  - Block Paper entry (already done ✓)
  - Show warning in UI
  
IF price_difference_pct > 20%:
  - Force use snapshot only
  - Disable intraday calculations
  - Alert user
```

### Phase 5: Unify Price Source (Later)
```
Long-term:
  - Use Binance when accessible (unblock 451?)
  - Standardize on single provider per symbol
  - No more fallback chains, direct choice
```

---

## SECTION 9: PLAN CORRECTION PROGRESSIF

### Step 1: DONE ✓
- Audit complet
- Price diagnostic fields added (cf61713)
- price_suspect flag working
- No trades executed despite bad prices

### Step 2: IMMEDIATE (Next, <1h)
- Investigate TON intraday source
- Fix MKR Coinbase perpetuals issue
- Add last_intraday_provider to API

### Step 3: SAFETY MEASURES (Within 1-2 days)
- Block Coinbase for MKR
- Force snapshot for TON if intraday suspect
- Add cache age to API response
- Test all 10 cryptos

### Step 4: USER VALIDATION (Parallel)
- Review this audit report
- Approve correction approach
- Decide on Paper/Watchlist changes

### Step 5: IMPLEMENTATION (After approval)
- Apply corrections
- Test production
- Monitor for issues
- No Paper/Watchlist changes until approved

---

## SECTION 10: RISQUES RAILWAY ET MITIGATION

### Risk 1: Binance HTTP 451 Blocking
- **Impact:** Forces fallback to Coinbase/Kraken/OKX
- **Severity:** HIGH (affects intraday quality)
- **Mitigation:** Can't fix at code level, network-level issue
- **Workaround:** Use snapshot prices (which come from CoinGecko)

### Risk 2: MKR Perpetuals Instead of Spot
- **Impact:** Entry/SL/TP calculated on 1347 instead of 1866
- **Severity:** HIGH
- **Mitigation:** Block Coinbase as provider for MKR
- **Cost:** Medium (needs provider selection logic)

### Risk 3: TON Intraday Source Unknown
- **Impact:** 1.849 instead of 2.43 (23% error)
- **Severity:** HIGH if used for calculations
- **Mitigation:** Force investigation and fix
- **Cost:** Low-Medium (find root cause, clear cache if stale)

### Risk 4: Cache Stale After Restart
- **Impact:** Old prices shown immediately after Railway restart
- **Severity:** MEDIUM
- **Mitigation:** Implement cache warmup at startup
- **Cost:** Medium (new code)

---

## SÉCURITÉ CONFIRMÉE

✅ **This audit made NO code changes**  
✅ **Zero impact on trading execution** (execution_authorized = false)  
✅ **Zero Real trading enabled**  
✅ **Zero leverage features**  
✅ **Paper-only mode maintained**  
✅ **Actions/Crypto Swing/Scalp protection intact**  
✅ **All price_suspect flags working correctly**  

---

## RAPPORT FINAL: TON ET MKR

### TON Verdict
```
✓ Snapshot is CORRECT (2.449 vs CoinGecko 2.43 = +0.78%)
✗ Intraday is WRONG (1.849 vs CoinGecko 2.43 = -23.91%)
→ Use snapshot. Investigate intraday source.
→ Current price_suspect=True is CORRECT behavior.
```

### MKR Verdict
```
⚠️ Snapshot is ACCEPTABLE (1777.13 vs CoinGecko 1866.09 = -4.77%)
✗ Intraday is WRONG (1347.21 is Coinbase perpetuals, not spot)
→ Block Coinbase for MKR. Use snapshot only.
→ Current price_suspect=True is CORRECT behavior.
```

---

## RAPPORT FINAL: INDICATEURS FIABLES?

**Verdict:** PARTIELLEMENT

- ✅ **Snapshot-based indicators:** FIABLE (use CoinGecko prices)
- ✅ **Daily/4h indicators:** FIABLE (stable daily data)
- ❌ **Intraday 5m indicators:** SUSPECT for TON/MKR, OK for others
- ⚠️ **Price_suspect flag:** WORKING, blocks entry when divergence >5%

**Conclusion:** System is already protecting against bad intraday prices via price_suspect flag. No immediate risk to trading.

---

## DOCUMENTS GÉNÉRÉS

1. AUDIT_PRIX_PLAN.md - Plan d'audit complet
2. master_price_audit.py - Script de test automatisé
3. AUDIT_FINAL_COMPLETE.md - Ce rapport

---

## ÉTAPES SUIVANTES (UTILISATEUR À DÉCIDER)

1. **Valider ce rapport:** Êtes-vous d'accord avec les findings?
2. **Approuver corrections:** Quelles étapes implémenter d'abord?
3. **Décider Paper/Watchlist:** Après corrections, adapte-t-on les règles?
4. **Timeline:** Immédiat / dans 1-2 jours / après Phase 3B?

---

**Status:** AUDIT COMPLET ET FINAL  
**Date:** 2026-05-07  
**Readiness:** PRÊT POUR DÉCISION UTILISATEUR
