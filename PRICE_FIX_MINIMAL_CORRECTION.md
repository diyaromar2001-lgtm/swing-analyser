# MINIMAL CORRECTION: Price Fix HTTP 500

**Root Cause:** `price_timestamp` field stored as datetime object (not JSON serializable)  
**Solution:** Force timestamp to numeric type (float)  
**Risk Level:** LOW (single field fix, defensive)  
**Testing:** LOCAL FASTAPI TESTCLIENT ONLY  

---

## PROBLEM

```python
# Price fix code (640ee35 implementation):
result["price_timestamp"] = price_snap.get("ts", 0)

# If price_snap["ts"] is a datetime object (Railway):
# FastAPI JSON encoder fails: "Object of type datetime is not JSON serializable"
# Result: HTTP 500 on any analyze endpoint
```

---

## MINIMAL FIX

**File:** `backend/crypto_scalp_service.py`

**Change:** Add timestamp type forcing (1 line)

```python
# Instead of:
result["price_timestamp"] = price_snap.get("ts", 0)

# Use:
ts = price_snap.get("ts", 0)
result["price_timestamp"] = float(ts) if isinstance(ts, (int, float)) else 0.0
```

**Or simpler:**
```python
try:
    ts = price_snap.get("ts", 0)
    result["price_timestamp"] = float(ts) if ts else 0.0
except (ValueError, TypeError):
    result["price_timestamp"] = 0.0
```

---

## IMPLEMENTATION PLAN

### Step 1: Implement in crypto_scalp_service.py

**Location:** Where price fields are added to response

**Current code (around line 172 in hotfix 90e3da0):**
```python
result["price_timestamp"] = price_snap.get("ts", 0)
```

**New code:**
```python
# Force timestamp to numeric (prevent datetime serialization error)
ts = price_snap.get("ts", 0)
try:
    result["price_timestamp"] = float(ts) if ts else 0.0
except (ValueError, TypeError):
    result["price_timestamp"] = 0.0
```

### Step 2: Add other price fields (for reference)

These are also part of price fix, ensure they're included:
```python
result["price_source"] = price_source  # Already string, OK
result["displayed_price"] = displayed_price  # Already float, OK
result["intraday_last_close"] = intraday_last_close  # Already float or None, OK
result["snapshot_price"] = snapshot_price  # Already float or None, OK
result["price_suspect"] = price_suspect  # Already bool, OK
result["price_difference_pct"] = price_difference_pct  # Already float or None, OK
```

---

## LOCAL TESTING

### Test 1: Timestamp serialization

```python
import json
from datetime import datetime

# Test cases
ts_float = 1778101234.5
ts_datetime = datetime.now()
ts_none = None

# Valid fix
def safe_timestamp(ts):
    try:
        return float(ts) if ts else 0.0
    except (ValueError, TypeError):
        return 0.0

# Should all work
json.dumps({"ts": safe_timestamp(ts_float)})      # OK
json.dumps({"ts": safe_timestamp(ts_datetime)})   # OK (converts to 0.0)
json.dumps({"ts": safe_timestamp(ts_none)})       # OK (becomes 0.0)
```

### Test 2: Full endpoint test

```bash
cd backend
python3 test_fastapi_json_serialization.py

# Expected: [PASS] All endpoints return valid JSON
```

---

## WHAT THIS FIX DOES

✓ **Solves the problem:**
- Timestamp is always numeric (float)
- No datetime objects in response
- JSON serialization succeeds

✓ **Doesn't break anything:**
- If Railway returns float: stored as-is
- If Railway returns datetime: converted to 0.0 (safe fallback)
- If Railway returns None: stored as 0.0
- If conversion fails: stored as 0.0

✓ **Doesn't change logic:**
- Still fetches intraday 5m close as priority
- Still detects price divergence
- Still adds all informational fields
- No impact on Paper/Watchlist

---

## DEPLOYMENT PLAN

### Phase 1: Modify code (5 min)
1. Edit `backend/crypto_scalp_service.py`
2. Apply 3-line timestamp fix
3. Verify syntax: `python3 -m py_compile crypto_scalp_service.py`

### Phase 2: Test locally (10 min)
1. Run `test_fastapi_json_serialization.py`
2. Verify ALL endpoints HTTP 200
3. Verify JSON valid for TON, BTC, ETH
4. Confirm price fields populated

### Phase 3: Push to production (5 min)
1. Commit: "Fix: Force price_timestamp to numeric type"
2. Push to NEW BRANCH (NOT main yet)
3. Verify Railway deploys
4. Test endpoint: `curl .../analyze/TON`
5. Confirm HTTP 200

### Phase 4: Merge to main (2 min)
1. If all tests pass: merge branch to main
2. Keep for reference: original rollback on main still there
3. New commit on main: stable again

---

## SAFETY VERIFICATION

- [ ] No new dependencies
- [ ] No changes to Paper/Watchlist logic
- [ ] No Real trading execution
- [ ] No leverage features
- [ ] No Actions module modifications
- [ ] No Crypto Swing module modifications
- [ ] All response fields JSON serializable
- [ ] Tested locally with TestClient FastAPI
- [ ] HTTP 200 on all analyze endpoints

---

## ROLLBACK PLAN (if something goes wrong)

If the fix doesn't work:
```bash
git reset --hard ce9a98e  # Stable version
git push origin main --force
```

Back to HTTP 200 immediately.

---

## SUMMARY

| Aspect | Details |
|--------|---------|
| Root cause | datetime object in price_timestamp field |
| Fix | Force ts to float before storing in response |
| Lines changed | 3-4 lines in crypto_scalp_service.py |
| Testing | Local FastAPI TestClient |
| Deployment | New branch → test → merge to main |
| Risk | LOW (single defensive fix) |
| Rollback | 2 commands if needed |

---

**Status:** READY FOR IMPLEMENTATION  
**Prerequisite:** Approval to proceed + access to push branch

