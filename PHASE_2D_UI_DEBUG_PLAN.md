# PHASE 2D — DEBUG UI CRYPTO SCALP

**Date:** 5 mai 2026  
**Statut:** 🔍 **DEBUG EN COURS**  
**Objectif:** Résoudre les incohérences UI et valider Phase 2D complètement

---

## PROBLÈMES IDENTIFIÉS

### 1. Journal UI Vide
**Symptôme:** Journal affiche "Aucun trade paper scalp pour l'instant"  
**Cause probable:**
- Endpoint appelé ≠ endpoint réel backend
- Mauvais parsing de la réponse JSON
- Mauvais nom de champ
- Mauvais filtre appliqué
- Frontend et backend ne partagent pas la même DB
- Problème CORS/env variable

**À debugger:**
- Ouvrir DevTools Network
- Aller à Journal tab
- Identifier l'URL exacte appelée (ex: `/api/crypto/scalp/journal/trades`)
- Vérifier la réponse JSON reçue
- Comparer avec le format retourné par le backend lors du test HTTP
- Corriger si nécessaire

### 2. Performance UI Affiche 0
**Symptôme:** 
- Total Trades = 0
- Win Rate = 0.0%
- Net PnL = 0.000%

**Cause probable:**
- Endpoint `/api/crypto/scalp/journal/performance` non appelé correctement
- Réponse mal parsée
- Frontend pointe vers une autre DB/backend instance
- Filtre caché par défaut

**À debugger:**
- Vérifier l'URL complète appelée par le Performance tab
- Comparer avec le test HTTP backend qui retournait les données
- Confirmer que c'est le même backend/DB

### 3. Analysis Tab Vide
**Symptôme:**
- Onglet Analysis vide après "View Analysis" click
- Pas de trade plan visible
- Pas de coûts affichés

**Cause probable:**
- Bouton "View Analysis" ne sélectionne pas le symbole
- selectedSymbol/selectedTrade state non mis à jour
- Onglet Analysis ne se remplit pas
- Appel GET `/api/crypto/scalp/analyze/{symbol}` non exécuté
- Réponse mal mappée

**À debugger:**
- Cliquer "View Analysis" sur MKR
- Ouvrir DevTools Console
- Vérifier si l'onglet Analysis s'affiche
- Vérifier si une requête est envoyée
- Vérifier la réponse JSON

---

## ÉTAPES DE DEBUG

### Phase A: Démarrer Serveur + DevTools

```bash
# Terminal 1: Vérifier que le backend est actif
cd backend/
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2: Vérifier que le frontend dev server tourne
cd frontend/
npm run dev  # doit écouter sur http://localhost:3000
```

### Phase B: Journal Debug

1. Ouvrir http://localhost:3000 dans Chrome
2. Aller à Crypto → Scalp mode
3. Cliquer sur Journal tab
4. **Ouvrir DevTools** (F12 → Network tab)
5. **Chercher l'appel** GET `/api/crypto/scalp/journal/trades` ou similaire
6. **Vérifier la réponse JSON:**
   ```json
   {
     "trades": [
       {
         "id": "scalp_MKR_...",
         "symbol": "MKR",
         "direction": "LONG",
         "status": "SCALP_PAPER_PLANNED",
         "entry_price": 2500,
         ...
       }
     ],
     "count": N
   }
   ```
7. Si vide, vérifier si le backend a réellement des trades:
   ```bash
   curl -s "http://127.0.0.1:8000/api/crypto/scalp/journal/trades" | jq
   ```
8. Si le backend retourne des trades mais l'UI n'en affiche pas:
   - Vérifier le mapping JSON → state
   - Vérifier les noms de champs (symbol vs ticker, direction vs side, etc.)
   - Vérifier les filtres appliqués

### Phase C: Performance Debug

1. Cliquer sur Performance tab
2. Ouvrir DevTools Network
3. Chercher l'appel GET `/api/crypto/scalp/journal/performance`
4. Vérifier la réponse JSON:
   ```json
   {
     "total_trades": 2,
     "closed_trades": 2,
     "winning_trades": 1,
     "win_pct": 50.0,
     "avg_r_winner": 1.0,
     "avg_r_loser": -1.0,
     "net_pnl_pct": 1.75,
     "net_pnl_usd": 175.0
   }
   ```
5. Vérifier que le mapping UI affiche ces champs correctement
6. Si 0, vérifier le backend:
   ```bash
   curl -s "http://127.0.0.1:8000/api/crypto/scalp/journal/performance" | jq
   ```

### Phase D: Analysis Debug

1. Retourner au Screener tab
2. Cliquer "View Analysis →" sur MKR (ou une autre crypto)
3. Ouvrir DevTools Console (F12 → Console)
4. Vérifier si des erreurs JS apparaissent
5. Cliquer sur onglet Analysis pour voir s'il se remplit
6. Si vide, chercher l'appel Network GET `/api/crypto/scalp/analyze/MKR`
7. Vérifier la réponse JSON avec les coûts:
   ```json
   {
     "symbol": "MKR",
     "scalp_grade": "B",
     "entry": 2500,
     "stop_loss": 2450,
     "tp1": 2550,
     "spread_bps": 8,
     "entry_fee_pct": 0.1,
     "exit_fee_pct": 0.1,
     "slippage_pct": 0.05,
     "estimated_roundtrip_cost_pct": 0.25,
     "paper_allowed": true,
     "paper_confidence": 95,
     "execution_authorized": false
   }
   ```

---

## VALIDATION CHECKPOINTS

### ✅ Journal Testé

- [ ] GET `/api/crypto/scalp/journal/trades` retourne des trades
- [ ] Au moins 1 trade SCALP_PAPER_PLANNED ou SCALP_PAPER_CLOSED visible
- [ ] Colonnes: Symbol, Status, Entry, Exit, PnL, etc.
- [ ] Filtres (All/Open/Closed, Symbol, Side) fonctionnels
- [ ] Export CSV button visible et fonctionnel

### ✅ Performance Testé

- [ ] GET `/api/crypto/scalp/journal/performance` retourne des métriques
- [ ] Total Trades > 0
- [ ] Win Rate % affiché correctement
- [ ] Avg R (Winners/Losers) affiché
- [ ] Net PnL % affiché

### ✅ Analysis Testé

- [ ] Sélectionner une crypto depuis Screener
- [ ] View Analysis button fonctionne
- [ ] Onglet Analysis se remplit
- [ ] Affiche: Symbol, Grade, Entry, Stop, TP1, TP2
- [ ] Affiche coûts: spread_bps, fees, slippage, roundtrip %
- [ ] Affiche execution_authorized = false (Paper Only badge)

### ✅ Close Trade Testé

- [ ] Cliquer "Close" sur un trade SCALP_PAPER_PLANNED
- [ ] Modal/Form pour entrer exit_price
- [ ] POST `/api/crypto/scalp/journal/close/{trade_id}`
- [ ] Réponse affiche: net_pnl_pct, r_multiple, hold_time_minutes
- [ ] Trade passe en SCALP_PAPER_CLOSED
- [ ] Performance tab se met à jour

### ✅ Export CSV Testé

- [ ] Cliquer "Export CSV" depuis Journal
- [ ] Fichier téléchargé contient:
  - Symbol, Direction, Status
  - Entry Price, Exit Price
  - Gross PnL %, Net PnL %
  - Fees, Spread, Slippage
  - R Multiple, Hold Time (minutes)
  - Closure Reason

### ✅ Sécurité Confirmée

- [ ] Aucun bouton "Trade Real"
- [ ] Aucun bouton "Open Real"
- [ ] Aucun bouton "Execute"
- [ ] Aucun sélecteur Leverage
- [ ] Tous les trades: execution_authorized = false
- [ ] Tous les trades: status commence par SCALP_PAPER_

### ✅ Build Final

- [ ] `npm run build` → Success (Compiled successfully)
- [ ] TypeScript → No errors
- [ ] ESLint → Optional, warnings acceptable, no blockers

---

## CORRECTIFS À APPLIQUER (Si nécessaire)

### Si Journal est vide
```typescript
// Vérifier l'endpoint appelé
const response = await fetch('/api/crypto/scalp/journal/trades');
const data = await response.json();
console.log('Trades received:', data);

// Vérifier le mapping
trades.map(t => ({
  id: t.id,
  symbol: t.symbol,  // Pas "ticker"
  direction: t.direction,  // Pas "side"
  status: t.status,
  entry_price: t.entry_price,
  // etc...
}))
```

### Si Performance est à 0
```typescript
// Vérifier que le backend a vraiment des closed trades
const response = await fetch('/api/crypto/scalp/journal/performance');
const stats = await response.json();
console.log('Performance stats:', stats);

// Ajouter debug log au render
console.log('Rendering performance:', { total_trades, win_pct, net_pnl_pct })
```

### Si Analysis reste vide
```typescript
// Vérifier que le selectedSymbol est défini
const [selectedSymbol, setSelectedSymbol] = useState(null);

// Analyis tab doit écouter selectedSymbol
useEffect(() => {
  if (!selectedSymbol) return;
  
  fetch(`/api/crypto/scalp/analyze/${selectedSymbol}`)
    .then(r => r.json())
    .then(data => {
      console.log('Analysis data:', data);
      setAnalysisData(data);
    });
}, [selectedSymbol]);

// View Analysis button doit définir selectedSymbol
<button onClick={() => setSelectedSymbol('MKR')}>
  View Analysis →
</button>
```

---

## COMMITS ATTENDUS

Une fois tous les problèmes résolus:

```bash
git add -A
git commit -m "Fix Crypto Scalp UI: Journal/Performance/Analysis endpoints and mapping

- Fixed Journal endpoint call and JSON parsing
- Fixed Performance metrics display
- Fixed Analysis View button and symbol selection
- Verified all cost fields display correctly
- Confirmed security (execution_authorized=false everywhere)
- Build passes with zero TypeScript errors

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin main
```

---

## STATUT FINAL ATTENDU

**Phase 2D UI Validation:** ✅ COMPLETE  
- Backend/API: ✅ Validée (test HTTP)
- Frontend Structure: ✅ Validée (build + tabs)
- **UI Fonctionnelle: 🔄 En cours de debug**

Une fois ce debug complet → Phase 2D UI officielle validée → Phase 2 COMPLÈTE

---

**Prochaine étape:** Redémarrer le frontend et exécuter le debug plan A-D avec screenshots de preuves.

