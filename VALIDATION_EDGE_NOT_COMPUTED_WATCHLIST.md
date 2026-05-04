# VALIDATION: EDGE_NOT_COMPUTED + WATCHLIST LOGIC

**Date:** 2026-05-04  
**Status:** ✅ VERIFIED & CORRECT

---

## REQUIREMENT

EDGE_NOT_COMPUTED must:
- ❌ Block execution (PLANNED, OPEN) 
- ✅ Allow watchlist (WATCHLIST with execution_authorized=false)

**Reasoning:** EDGE_NOT_COMPUTED = "edge not yet calculated", not "bad setup"
→ Exactly a use case for watchlist (monitor while awaiting computation)

---

## CODE VERIFICATION

### 1. Execution Authorization (BLOCKED) ✅

**File:** `frontend/app/components/TradePlan.tsx` line 118

```typescript
function getExecutionAuthorization(row: TickerResult) {
  const edgeOk = row.ticker_edge_status === "STRONG_EDGE" || row.ticker_edge_status === "VALID_EDGE";
  // ...
  const authorized = tradableOk && buyOk && edgeOk && setupOk && setupStatusOk && overfitOk && riskOk;
  // ...
}
```

**Logic:**
- EDGE_NOT_COMPUTED → edgeOk = false
- edgeOk = false → authorized = false
- authorized = false → Button "✅ Préparer ce trade" NOT shown
- Result: **Execution BLOCKED** ✅

---

### 2. Watchlist Eligibility (ALLOWED) ✅

**File:** `frontend/app/components/TradePlan.tsx` lines 220-225

```typescript
const blockedForWatchlist =
  row.setup_status === "INVALID" ||
  row.overfit_warning === true ||
  row.setup_grade === "REJECT" ||
  ["SKIP", "NO_TRADE"].includes(row.final_decision ?? "");

const watchlistEligible = !execAuth.authorized && !blockedForWatchlist;
```

**Check:**
- EDGE_NOT_COMPUTED is NOT in blockedForWatchlist list ✅
- blockedForWatchlist = false
- execAuth.authorized = false (from step 1)
- watchlistEligible = !false && !false = **true** ✅

**Result:**
- Line 511-517: Button "🟠 Ajouter à la watchlist" **IS shown** ✅

---

### 3. Watchlist Saving (CORRECT) ✅

**File:** `frontend/app/components/TakeTradeModal.tsx` line 63

```typescript
export function TakeTradeModal({ 
  t, 
  journalStatus = "PLANNED" 
}: { 
  t: TickerResult; 
  journalStatus?: "PLANNED" | "WATCHLIST"; 
  ...
}) {
  // ...
  execution_authorized: journalStatus === "PLANNED",  // ← KEY LINE
  // ...
}
```

**Logic:**
- When user clicks "Ajouter à la watchlist"
- journalStatus = "WATCHLIST"
- execution_authorized = false ✅
- Trade saved with status=WATCHLIST, execution_authorized=false ✅

**Result:** Trade Journal entry is NOT executable (no OPEN button) ✅

---

## TEST SCENARIOS

### Scenario 1: A+ setup with EDGE_NOT_COMPUTED
```
Setup: LLY, grade=A+, EDGE_NOT_COMPUTED, score=82

UI shown:
✅ Ticker card shows blue badge ◆ EDGE NOT COMPUTED
✅ TradePlan opens
✅ Execution authorization blocked: "Edge non calculé (cliquer Calculer Edge)"
✅ NO button "✅ Préparer ce trade"
✅ YES button "🟠 Ajouter à la watchlist" (visible)

User clicks "Ajouter à la watchlist"
✅ TakeTradeModal opens with label "🟠 Ajouter à la watchlist"
✅ Saved to Trade Journal as WATCHLIST with execution_authorized=false

In Trade Journal:
✅ Entry shows status WATCHLIST
✅ NO button OPEN (disabled because execution_authorized=false)
✅ Can still be REJECTED or marked complete
```

### Scenario 2: A setup with EDGE_NOT_COMPUTED
```
Setup: CL, grade=A, EDGE_NOT_COMPUTED, score=82

UI shown:
✅ Same as Scenario 1 (watchlist eligible)
✅ Button "Ajouter à la watchlist" visible
✅ No execution authorization
```

### Scenario 3: B setup with EDGE_NOT_COMPUTED
```
Setup: HOLX, grade=B, EDGE_NOT_COMPUTED, score=62

UI shown:
✅ Watchlist button visible (grade B eligible)
✅ Execution blocked
✅ Can be added to watchlist
```

### Scenario 4: REJECT setup (control)
```
Setup: XYZ, grade=REJECT, EDGE_NOT_COMPUTED, score=40

blockedForWatchlist = true (row.setup_grade === "REJECT")
✅ Button "🟠 Ajouter à la watchlist" NOT shown
✅ Button "⛔ Trade non autorisé" shown instead
```

---

## NO UNINTENDED CHANGES

✅ **BUY/WAIT/SKIP logic**: Untouched
✅ **tradable field**: Untouched
✅ **final_decision**: Untouched
✅ **Edge v1 computation**: Untouched
✅ **Crypto screener**: Untouched
✅ **Risk filters**: Untouched
✅ **Earnings warning**: Untouched
✅ **Overfit warning**: Untouched

---

## BUILD VERIFICATION ✅

```
Frontend build: SUCCESS
✓ Compiled in 4.0s
✓ TypeScript check: PASSED
✓ All pages generated: 5/5
✓ Zero errors, zero warnings
```

---

## SECURITY CHECKLIST ✅

| Check | Result | Notes |
|-------|--------|-------|
| EDGE_NOT_COMPUTED blocks execution | ✅ | edgeOk = false → authorized = false |
| EDGE_NOT_COMPUTED allows watchlist | ✅ | Not in blockedForWatchlist list |
| WATCHLIST has execution_authorized=false | ✅ | TakeTradeModal logic correct |
| No OPEN button for WATCHLIST entries | ✅ | execution_authorized=false blocks OPEN |
| Trade execution still requires validation | ✅ | Security maintained |
| Admin endpoints untouched | ✅ | No changes to warmup/admin logic |

---

## SUMMARY

The implementation **already correctly handles EDGE_NOT_COMPUTED + watchlist**:

1. ✅ Execution is blocked (as expected)
2. ✅ Watchlist is allowed (as expected)
3. ✅ Saved with execution_authorized=false (as expected)
4. ✅ No OPEN button shown in Trade Journal (as expected)
5. ✅ All security maintained

**No changes required to TradePlan.tsx or any other file.**

The original implementation was designed correctly to support this use case.

---

**Status:** READY FOR COMMIT ✅

