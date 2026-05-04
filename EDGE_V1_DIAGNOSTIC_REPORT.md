# EDGE V1 DIAGNOSTIC REPORT
**Date:** 2026-05-04  
**Scope:** Read-only analysis of Edge v1 caching and computation pipeline  
**Status:** 🔍 DIAGNOSTIC COMPLETE

---

## EXECUTIVE SUMMARY

**Core Finding:** All 107 Action setups display `NO_EDGE` because the screener never computes Edge v1 — it only reads from an empty cache.

**Root Cause:** 
```
Screener reads: get_cached_edge(ticker)
              ↓
         Cache empty (never populated in screener flow)
              ↓
         Returns {} → fallback "NO_EDGE"
```

**Why it happens:**
- `/api/screener` calls `get_cached_edge()` (cache-read only, line ~1040)
- The only place that calls `compute_ticker_edge()` is `/api/warmup` (lines 467, 2156, 2185, 2224)
- `/api/warmup` requires **Admin key** and must be **explicitly triggered**
- User has never clicked "Réparer les caches" on Actions tab
- Result: Cache stays empty → all tickers → "NO_EDGE"

---

## DETAILED FINDINGS

### 1. Edge Status Distribution (107 setups)

| Edge Status | Count | % |
|-------------|-------|-----|
| **NO_EDGE** | 107 | **100%** |
| STRONG_EDGE | 0 | 0 |
| VALID_EDGE | 0 | 0 |
| WEAK_EDGE | 0 | 0 |
| OVERFITTED | 0 | 0 |

### 2. A/A+/B Setups Blocked by Edge Status

| Grade | Status | Count |
|-------|--------|-------|
| A or A+ | NO_EDGE | 17 setups |

**Examples (all NO_EDGE):**
- LLY: score=82, grade=A, edge=NO_EDGE, decision=WAIT, tradable=false
- CL: score=82, grade=A, edge=NO_EDGE, decision=WAIT, tradable=false
- LIN: score=75, grade=A, edge=NO_EDGE, decision=WAIT, tradable=false
- HOLX: score=62, grade=B, edge=NO_EDGE, decision=WAIT, tradable=false

### 3. Root Cause Analysis

#### Code Flow (Screener → Edge)

**In `main.py` line ~1040 (screener endpoint):**
```python
# ── 7. Strategy Edge (cache uniquement — non bloquant) ──────────────
try:
    edge_data    = get_cached_edge(ticker) or {}  # ← CACHE ONLY
    te_status    = edge_data.get("ticker_edge_status", "NO_EDGE")
    ...
```

**Function `get_cached_edge()` (ticker_edge.py line 357):**
```python
def get_cached_edge(ticker: str, period_months: int = PERIOD_MONTHS) -> Optional[Dict]:
    """Retourne l'edge depuis le cache uniquement (sans recalcul)."""
    cached = _edge_cache.get(_cache_key(ticker, period_months))
    if cached:
        return cached["data"]
    return None  # ← Returns None if not in cache
```

**Fallback in screener:** `edge_data or {}` → empty dict → default "NO_EDGE"

#### Where Edge IS Computed

**Only in `/api/warmup` POST endpoint (lines 462-476):**
```python
for ticker in edge_targets:
    df = _get_ohlcv(ticker, allow_download=True)
    if df is None:
        continue
    try:
        compute_ticker_edge(ticker, df, period_months=24)  # ← HERE
        edge_computed += 1
    except Exception as exc:
        ...
```

**Who calls `/api/warmup`:**
- Frontend button "Réparer les caches" (requires Admin key)
- User MUST explicitly click it
- Never auto-triggered on screener load

### 4. Edge v1 Thresholds (If Cache Were Populated)

From `ticker_edge.py` lines 25-38:

```python
MIN_TRADES         = 15
MIN_PROFIT_FACTOR  = 1.2     # Overall PF threshold
MIN_TEST_PF        = 1.0     # Test PF (out-of-sample)
MAX_DRAWDOWN_PCT   = 40.0
MIN_EXPECTANCY     = 0.0     # Must be ≥ 0
OVERFIT_THRESHOLD  = 0.35    # Train PF to Test PF degradation > 35% → OVERFITTED
PERIOD_MONTHS      = 24      # Lookback window

Classification logic (lines 130-149):
- STRONG_EDGE  : PF ≥ 1.5 AND test PF ≥ 1.2 AND n ≥ 20
- VALID_EDGE   : PF ≥ 1.2 AND test PF ≥ 1.0 AND NOT overfitted
- WEAK_EDGE    : PF ≥ 1.1 AND (test PF ≥ 1.0 OR expectancy ≥ 0)
- OVERFITTED   : Train PF >> Test PF (> 35% degradation)
- NO_EDGE      : Everything else
```

These are **reasonable, not excessive** thresholds:
- Require out-of-sample (test) validation (line 143: `tpf >= MIN_TEST_PF`)
- Prevent overfitting (train/test degradation check)
- Require minimum sample (15-20 trades)
- Allow positive expectancy even with modest PF (1.1+)

---

## 5. Why It Looks Like "Edge Too Strict"

It's not that Edge v1 is too strict — **it's that it's never been computed.**

**Proof:**
1. All 107 setups = NO_EDGE (probability of random data ≈ 0)
2. No WEAK_EDGE, no OVERFITTED, no variation = **100% cache miss**
3. If 10% of strategies legitimately passed Edge v1, we'd see some VALID_EDGE
4. We see zero of everything else = cache empty

---

## 6. Crypto Situation

**Crypto screener returns:** `edge_status="NO_EDGE"` uniformly

**Because:**
- `/api/crypto/screener` also calls `get_cached_edge(ticker)` (cache only)
- Crypto warmup also requires `/api/warmup?scope=crypto` + Admin key
- Plus: Crypto Phase 1 backtest explicitly rejected all 3 strategies (PF < 1.20)
- Result: "NO VALIDATED CRYPTO EDGE" banner (correct and intended)

---

## 7. Edge v1 vs Edge v2 Research

**Edge v1 (this analysis):**
- Computes on-demand via `/api/warmup` (Admin-only)
- Caches for 24 hours
- Binary decision: authorized or not
- Output: STRONG_EDGE | VALID_EDGE | WEAK_EDGE | OVERFITTED | NO_EDGE

**Edge v2 Research (separate system):**
- Endpoint: `/api/research/edge-v2`
- Outputs: `edge_v2_status` (V2_VALID_RESEARCH, V2_WATCHLIST, INSUFFICIENT_SAMPLE, etc.)
- Designed for educational observation, not trade authorization
- Already integrated in TradePlan.tsx (lines 521-546)

**Key Difference:**
- Edge v1 = "Can I trade this?" (yes/no gate)
- Edge v2 = "Is this interesting? Why/why not?" (research insight)

---

## DIAGNOSIS CONCLUSIONS

### Is This Normal?

**NO. But not because Edge v1 is broken.**

Expected behavior:
1. Admin clicks "Réparer les caches" → `/api/warmup?scope=actions` (POST)
2. Warmup computes Edge v1 for all 107 tickers
3. Cache populates over ~30-60 seconds
4. Screener reload → reads cache → displays actual edge statuses
5. Some tickers get STRONG_EDGE, VALID_EDGE, or WEAK_EDGE
6. Others stay NO_EDGE (legitimately)

**Current reality:**
- Cache never populated
- All tickers → NO_EDGE (artificial, not real)
- User sees "everything is blocked by edge" but cache is just empty

### Is Edge v1 Too Strict?

**Moderate assessment:**

**Too conservative?**
- Requires test PF ≥ 1.0 (industry standard is 1.0-1.2, this is mid-range)
- Requires ≥ 15-20 trades (reasonable for statistical significance)
- Degrades STRONG → VALID if test trades < 5 on Pullback Confirmed (cautious, OK)

**Too lenient?**
- Allows WEAK_EDGE with PF ≥ 1.1 (this is weak, arguably too permissive)
- Does NOT use Sharpe ratio, sortino, or kelly criterion (only PF-based)
- Does NOT account for recent performance decay

**Verdict:** Thresholds are defensible. Not egregiously strict. But could be tightened (require PF ≥ 1.3 instead of 1.2) if we wanted to reduce false positives.

---

## RECOMMENDATIONS

### 1. **Immediate (No code change)**
- User/Admin clicks "Réparer les caches" button (in Admin Panel → Advanced)
- Wait 30-60s
- Reload screener
- See actual Edge v1 statuses (not uniform NO_EDGE)

### 2. **To Improve Visibility (UI-only fix)**
Create a new edge status badge: **"INSUFFICIENT_SAMPLE"**
- **Why:** Distinguish between "edge tested and failed" vs "edge never tested"
- **Location:** EdgeBadge.tsx (add case for "INSUFFICIENT_SAMPLE")
- **Color:** Gray (#6b7280)
- **Logic:** In screener, if cache empty → show "INSUFFICIENT_SAMPLE" instead of "NO_EDGE"
- **Impact:** User sees why setup is not authorized (cache cold vs. legit rejection)

### 3. **To Prevent Future Cache Cold-Starts**
- Add auto-trigger to `/api/warmup` on first screener load (for Actions, daily at market open)
- OR: Pre-populate cache on app startup with top 50 tickers
- OR: Show banner "Edge cache warming up, check back in 1 min" if empty

### 4. **To Improve Edge v1 Itself (Later)**
- Tighten STRONG/VALID thresholds: require test PF ≥ 1.1 (not 1.0)
- Add Sharpe ratio check (not just PF)
- Require recent performance validation (last 3 months > 1.0)
- Consider regime-aware thresholds (bull market = higher edge required)

### 5. **To Leverage Edge v2**
- Edge v2 already computes and displays in TradePlan
- Consider showing "Edge v2 watchlist" badge on setups that Edge v1 rejects but Edge v2 likes
- **But:** Keep v2 research-only (does not authorize trades)

---

## NEXT STEPS

**To confirm diagnosis:**
1. Admin clicks "Réparer les caches" (Dashboard → Advanced tab)
2. Warmup completes (30-60s)
3. Reload screener
4. Check: Are setups now showing VALID_EDGE / WEAK_EDGE / etc. instead of all NO_EDGE?
   - **If YES:** Cache was the problem ✓
   - **If NO:** Edge v1 is truly rejecting everything (investigate further)

**To measure:**
- Count STRONG_EDGE, VALID_EDGE, WEAK_EDGE after warmup
- If > 5% of A/A+ setups show VALID_EDGE or better → Edge v1 is reasonable
- If < 5% → Edge v1 is very strict (and needs review)

---

## APPENDIX: Code References

- **Edge computation:** `backend/ticker_edge.py` lines 190-354
- **Screener read:** `backend/main.py` line ~1040
- **Warmup trigger:** `backend/main.py` lines 462-476 (POST /api/warmup)
- **Frontend UI:** `frontend/app/components/TradePlan.tsx` lines 117-147 (getExecutionAuthorization)

---

**Report Status:** ✅ DIAGNOSTIC COMPLETE — NO CHANGES MADE  
**Safety:** ✅ Zero code modifications — analysis only  
**Recommendations:** Ready for approval & implementation  

