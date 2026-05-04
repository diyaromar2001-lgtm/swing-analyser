# EDGE COMPUTE DIAGNOSTIC REPORT

**Date:** 2026-05-04  
**Status:** 🔍 DIAGNOSTIC - BUG IDENTIFIED

---

## PROBLEM SUMMARY

### Admin Button Issue
"Calculer Edge Actions (A+/A/B)" returns **"Edge calculé pour 0 tickers"**

### Root Cause Identified ❌
**Function `_run_screener_impl()` does NOT EXIST**

Location: `backend/main.py` line 2949
```python
_run_with_timeout(
    "warmup_edge_screener",
    lambda: _run_screener_impl(fast=True, limit=None),  # ← THIS FUNCTION DOESN'T EXIST
    45,
    warnings,
    errors,
)
```

### Impact
1. Fallback to populate screener cache **fails silently**
2. `current_cache` remains empty
3. No tickers found to filter
4. Returns: `edge_actions_count=0, edge_actions_computed=0`

---

## ISSUE ANALYSIS

### The Flow (Broken)
```
Admin clicks "Calculer Edge Actions (A+/A/B)"
    ↓
Tries to get _screener_cache[_default_screener_cache_key()]
    ↓
Cache empty (first time or cache cleared)
    ↓
Tries to call _run_screener_impl(fast=True, limit=None)
    ↓
Function doesn't exist ❌
    ↓
Exception caught silently (line 2955-2956)
    ↓
current_cache remains empty
    ↓
No filtered tickers found
    ↓
Returns: "Edge calculé pour 0 tickers"
```

---

## SECONDARY ISSUE

### Cache Key Mismatch
Even if screener cache has data, it may be under a different key:
- Endpoint expects: `build_screener_cache_key("standard", False, None, 0, None)`
- But screener may have been called with: `build_screener_cache_key("standard", False, "Tech", 75, None)` (with sector/min_score/signal filters)

Solution: Search in all cache keys or merge all available screener caches.

---

## SOLUTION

### Fix #1: Replace `_run_screener_impl()` with actual screener call
Change line 2949 from:
```python
lambda: _run_screener_impl(fast=True, limit=None),
```

To:
```python
lambda: screener(strategy="standard", exclude_earnings=False, sector=None, min_score=0, signal=None, fast=True),
```

### Fix #2: Merge all available screener cache results
Instead of looking only in default cache, iterate through ALL cache keys:
```python
def get_all_screener_results():
    """Get all screener results from any cache key"""
    all_results = []
    for key, cache_entry in _screener_cache.items():
        if isinstance(cache_entry, dict) and "data" in cache_entry:
            data = cache_entry["data"]
            if isinstance(data, list):
                all_results.extend(data)
    return all_results
```

---

## FILES THAT NEED FIXING

1. **`backend/main.py` (line 2949)**
   - Replace `_run_screener_impl()` call
   - Or implement smarter cache lookup

---

## EXPECTED BEHAVIOR AFTER FIX

### Scenario: Admin clicks "Calculer Edge Actions (A+/A/B)"

**Before fix:**
```
Admin: Clicks button
System: "Edge calculé pour 0 tickers."
Admin: ❌ Confused, nothing happens
```

**After fix:**
```
Admin: Clicks button
System: Calls screener() to populate cache if empty
System: Filters for A+/A/B grades
System: Computes edge for each ticker
System: "Edge calculé pour 45 tickers."
System: ✅ Tickers now have actual edge statuses
```

---

## VERIFICATION STEPS

### Step 1: Check if function exists
```bash
grep -n "_run_screener_impl" backend/main.py
# Expected: NO MATCHES (function doesn't exist)
```

### Step 2: Test edge computation for single ticker
```
POST /api/strategy-edge/compute?ticker=LLY
Headers: Admin API key

Expected response:
{
  "status": "ok",
  "ticker": "LLY",
  "edge_status": "STRONG_EDGE" | "VALID_EDGE" | "WEAK_EDGE" | "NO_EDGE" | "OVERFITTED",
  "message": "Edge calculé pour LLY",
  "trades": 42,
  "pf": 1.45,
  "test_pf": 1.23,
  "expectancy": 0.52,
  "overfit": false,
  "duration_ms": 3240
}
```

### Step 3: Test bulk edge computation
```
POST /api/warmup/edge-actions?grades=A%2B,A,B
Headers: Admin API key

Current (broken): 
{
  "status": "ok",
  "edge_actions_count": 0,
  "edge_actions_computed": 0,
  "edge_actions_tickers": [],
  ...
}

After fix (expected):
{
  "status": "ok",
  "edge_actions_count": 47,
  "edge_actions_computed": 42,
  "edge_actions_tickers": ["LLY", "CL", "LIN", ...],
  ...
}
```

---

## RECOMMENDED FIX PRIORITY

1. **HIGH:** Fix `_run_screener_impl()` call (line 2949)
   - Replace with actual `screener()` call
   - Or implement multi-key cache lookup

2. **MEDIUM:** Add logging to understand cache state
   - Log what cache keys exist
   - Log how many tickers found in each

3. **OPTIONAL:** Optimize cache lookup
   - Consider merging all available screener results
   - Or pre-populate default cache on startup

---

## NEXT STEPS

1. Fix the `_run_screener_impl()` call in backend/main.py
2. Test with `/api/strategy-edge/compute?ticker=LLY` first
3. Then test `/api/warmup/edge-actions?grades=A%2B,A,B`
4. Verify cache is properly written
5. Verify screener reads updated cache
6. Commit and deploy

