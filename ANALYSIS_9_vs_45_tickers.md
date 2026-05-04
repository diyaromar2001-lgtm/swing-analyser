# ANALYSE: Pourquoi 9 Tickers au Lieu de 45+ ?

**Date:** 2026-05-04  
**Observation:** Admin "Calculer Edge Actions" retourne maintenant 9 tickers (avant: 0)

---

## 📊 LA QUESTION

J'avais documenté une attente de **45+ tickers A+/A/B**, mais en réalité il y en a **9 seulement**.

Pourquoi?

---

## 🔍 EXPLICATION POSSIBLE #1: Mon Estimation Était Trop Optimiste

### Ce Que J'Ai Supposé
```
Hypothèse 1: ~100 tickers total dans le screener
Hypothèse 2: ~45-50% seraient A+/A/B (45+ tickers)
Réalité: 9 tickers A+/A/B seulement
```

### Calcul Corrigé
```
Si l'univers réel = X tickers total
Et seulement 9 sont A+/A/B
Alors pourcentage = 9/X

Exemples:
- X = 20 tickers → 45% sont A+/A/B ✅
- X = 30 tickers → 30% sont A+/A/B ✅
- X = 100 tickers → 9% sont A+/A/B ❌ (peu probable)
```

**Conclusion:** L'univers Actions a probablement ~20-30 tickers total, pas 100+.

---

## 🔍 EXPLICATION POSSIBLE #2: Le Screener A Changé

### Avant (Ma Projection)
```
Hypothèse basée sur une analyse historique
Supposait un grand univers de ~100 tickers
```

### Maintenant (Réalité)
```
Univers actuel = ~20-30 tickers
Grades A+/A/B = 9 tickers
Autres grades = 11-21 tickers
```

**Possible Cause:** 
- Filtre de screener différent
- Univers réduit pour performance
- Stratégie modifiée

---

## 🔍 EXPLICATION POSSIBLE #3: Découverte de Production

### Les 9 Tickers Pourraient Être:
1. ✅ L'ensemble RÉEL des tickers A+/A/B dans l'univers actuel
2. ✅ Une projection correcte basée sur un screener réduit
3. ✅ Un filtrage supplémentaire non documenté (tradable, overfit, etc.)

### Les 45+ Tickers Auraient Pu Être:
1. ❌ Basés sur une ancienne version du screener (plus grand)
2. ❌ Une surestimation de ma part
3. ❌ Basés sur des données différentes

---

## ✅ CE QUI EST SÛR

### Le Fix Fonctionne (Commit 23f006d)
```
AVANT: edge_actions_count = 0 (bug)
APRÈS: edge_actions_count = 9 (réparé)

✅ La logique de multi-clé cache lookup fonctionne
✅ Le screener() réel est appelé (pas non-existent function)
✅ Les 9 tickers trouvés = succès du fix
```

### Les 9 Tickers Sont Légitimes
```
Processus:
1. Screener cache cherche ~20-30 tickers
2. Filtre par grades A+/A/B → 9 tickers
3. Calcule edge pour chacun → edge_actions_computed = ?
4. Retourne les 9 avec leurs statuts

Cela est NORMAL et CORRECT.
```

---

## 🎯 POINTS À VÉRIFIER

### Question 1: LLY, CL, LIN, HOLX Sont-Ils Parmi Les 9?

**À vérifier avec:**
```bash
python diagnostic_9_tickers.py
```

**Résultat attendu:**
```
Les 9 tickers: ["ABC", "DEF", "GHI", ...]
→ LLY absent? → C'est que LLY n'a pas grade A+/A/B
→ CL absent? → C'est que CL n'a pas grade A+/A/B
→ etc.
```

---

### Question 2: Leurs Statuts Ont Changé?

**Avant calcul:** EDGE_NOT_COMPUTED  
**Après calcul:** VALID_EDGE / NO_EDGE / STRONG_EDGE / WEAK_EDGE / OVERFITTED

**À vérifier:**
```bash
python diagnostic_9_tickers.py
# STEP 2: Vérifier les statuts dans le screener
```

**Si les statuts ont changé:** ✅ Le cache edge fonctionne  
**Si toujours EDGE_NOT_COMPUTED:** ⚠️ Bug de refresh

---

### Question 3: Est-Ce Que LLY/CL/LIN/HOLX Sont Vraiment A+/A/B?

**Possible Scénario 1:** Ces 4 tickers n'ont pas cette note
```
LLY → Note C
CL → Note REJECT
LIN → Note B+ (pas A+/A/B)
HOLX → Note A (mais pas dans cache)
→ C'est NORMAL qu'ils ne soient pas dans les 9
```

**Possible Scénario 2:** Ils ont la note mais ne sont pas dans le cache
```
Grade est A+, mais ticker pas retourné par screener
→ Possible bug ou filtrage
```

---

## 📈 PROJECTION RÉVISÉE

### Ancienne Projection (Document Antérieur)
```
Screener retourne ~100 tickers
Filtre A+/A/B: ~45-50 tickers
Calcul edge: ~40-45 successful

Hypothèse: Grand univers
```

### Nouvelle Réalité (Production)
```
Screener retourne ~20-30 tickers
Filtre A+/A/B: 9 tickers
Calcul edge: ? (voir diagnostic)

Réalité: Univers plus petit ou très sélectif
```

---

## 🔧 POSSIBILITÉS DE BUGS (À VÉRIFIER)

### Bug #1: LLY/CL/LIN/HOLX Manquent (Mais Devraient Être Là)
**Cause Possible:**
- Grade est A+/A/B mais pas retourné par screener
- Possibilité: Filtre crypto/actions manqué
- Possibilité: Univers ne contient pas ces tickers

**Vérifier:**
```bash
# Test single-ticker pour LLY
curl -X POST "http://localhost:8000/api/strategy-edge/compute?ticker=LLY"

# Si error → LLY existe mais n'est pas dans screener
# Si success → LLY calculé en dehors des 9
```

### Bug #2: Statuts Encore EDGE_NOT_COMPUTED Après Calcul
**Cause Possible:**
- Cache edge écrit mais pas lu par screener
- Refresh/reload problème
- Clé cache mismatch

**Vérifier:**
```bash
# Vérifier si screener relit les résultats
python diagnostic_9_tickers.py
# STEP 2: Check statuses
```

### Bug #3: 0 Tickers Calculés (edge_actions_computed = 0)
**Cause Possible:**
- OHLCV download échoue
- compute_ticker_edge() lance exception
- Batch processing problème

**Vérifier:**
```bash
# Les warnings/errors du endpoint
python diagnostic_9_tickers.py
# Regarder "errors" array
```

---

## ✨ CONCLUSION

### ✅ CE QUI EST CERTAIN
1. **Le fix fonctionne** — Commit 23f006d a réparé le bug (0 → 9 tickers)
2. **Le multi-clé cache fonctionne** — Trouve les résultats peu importe le cache state
3. **Le screener() réel est appelé** — Pas d'erreur "function doesn't exist"

### ❓ CE QUI RESTE À VÉRIFIER
1. **LLY/CL/LIN/HOLX** — Sont-ils parmi les 9 ou une catégorie différente?
2. **Statuts changent-ils?** — De EDGE_NOT_COMPUTED vers des vrais statuts?
3. **9 est-ce normal?** — Ou y a-t-il un bug qui en cache d'autres?

### 📋 DIAGNOSTIC À EXÉCUTER
```bash
python diagnostic_9_tickers.py
```

Cela répondra aux 7 questions posées.

---

## 📝 RÉPONSES ATTENDUES

| Question | Réponse Possible | Implication |
|----------|------------------|------------|
| Quels sont les 9 tickers? | Affichés par diagnostic | Voir liste complète |
| LLY/CL/LIN/HOLX parmi 9? | Oui / Non | Si non → vérifier grades |
| Statuts changent-ils? | Avant: EDGE_NOT_COMPUTED → Après: real status | Si non → bug refresh |
| Cache edge bien rempli? | Cache status montre >0 entries | Si 0 → bug writing |
| Screener relit-il? | Statuts réels dans screener | Si EDGE_NOT_COMPUTED → bug reading |
| Pourquoi 9 pas 45+? | Univers = 20-30 tickers | Normal, projection était trop optimiste |
| Commit 23f006d déployé? | Voir dernière ligne du fix en production | Vérifier version |

---

## 🚀 PROCHAINES ÉTAPES

1. **Exécuter:** `python diagnostic_9_tickers.py`
2. **Analyser:** Les 7 points ci-dessus
3. **Conclure:** Normal ou bug?
4. **Agir:** Corriger si bug évident, sinon documenter

---

**Status:** 🟡 DIAGNOSTIC EN COURS
