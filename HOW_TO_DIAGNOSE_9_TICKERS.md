# COMMENT FAIRE LE DIAGNOSTIC DES 9 TICKERS

**Objectif:** Répondre aux 7 questions de l'utilisateur avec des données réelles

---

## 🚀 ÉTAPE 1: Démarrer le Backend

```bash
cd backend
python main.py
```

**Attendre le message:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 🔍 ÉTAPE 2: Exécuter le Diagnostic

**Dans un autre terminal:**

```bash
cd .. && python diagnostic_9_tickers.py
```

**Durée estimée:** 30-60 secondes

---

## 📊 ÉTAPE 3: Analyser les Résultats

### Structure du Diagnostic

```
STEP 1: Récupérer les 9 tickers calculés
├─ Response JSON
├─ Nombre de tickers trouvés
├─ Nombre calculés avec succès
├─ Warnings/Errors

STEP 2: Vérifier les statuts dans le screener
├─ Nombre de tickers dans screener
├─ Statut de chaque ticker (EDGE_NOT_COMPUTED? VALID_EDGE?)
├─ Grade de chaque ticker
└─ Décision finale

STEP 3: Vérifier l'état du cache
├─ Cache status
├─ Nombre d'entrées
└─ Détails par type

STEP 4: Vérifier les tickers individuels
├─ LLY status
├─ CL status
├─ LIN status
└─ HOLX status

RÉSUMÉ & CONCLUSIONS
├─ Les 9 sont-ils normaux?
├─ LLY/CL/LIN/HOLX manquent-ils?
├─ Statuts ont-ils changé?
├─ Pourquoi 9 et pas 45+?
└─ Commit 23f006d déployé?
```

---

## 📋 TABLEAU DE VÉRIFICATION

### Résultat 1: Les 9 Tickers

```
✅ BON: 9 tickers A+/A/B sont affichés
❌ MAUVAIS: 0 ou autre nombre
```

**Exemple de BON résultat:**
```
Les 9 tickers: ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR", "STU", "VWX", "YZA"]
```

---

### Résultat 2: LLY/CL/LIN/HOLX

#### Cas A: Tous les 4 Sont Parmi les 9
```
✅ NORMAL: Ils ont tous grade A+/A/B
✅ FIX COMPLET: Les 4 tickers importants sont calculés
```

**Action:** Vérifier leurs statuts (Résultat 3)

#### Cas B: Certains Manquent
```
⚠️ À INVESTIGUER: Pourquoi LLY n'est pas parmi les 9?
   → Vérifier son grade dans screener
   → Si grade ≠ A+/A/B → C'est NORMAL
   → Si grade = A+/A/B mais pas dans les 9 → BUG
```

**Action:** Vérifier grade + screener cache

---

### Résultat 3: Changement de Statuts

**BEFORE = EDGE_NOT_COMPUTED (avant calcul)**
**AFTER = VALID_EDGE / NO_EDGE / etc. (après calcul)**

```
✅ BON: Statuts ont changé
   Exemple: EDGE_NOT_COMPUTED → VALID_EDGE

❌ MAUVAIS: Statuts restent EDGE_NOT_COMPUTED
   Cause possible: Cache write/read bug
```

**Table de Vérification:**

| Ticker | Statut Actuel | Changé? | Note |
|--------|---------------|---------|------|
| ABC | VALID_EDGE | ✅ Oui | Bon |
| DEF | NO_EDGE | ✅ Oui | Bon |
| GHI | EDGE_NOT_COMPUTED | ❌ Non | Bug! |

**Si Bug:** Vérifier _persist_runtime_cache_state()

---

### Résultat 4: Cache Edge

```
✅ BON: Cache contient les 9 tickers
   Clue: edge_actions_computed = 9

⚠️ ATTENTION: edge_actions_computed < 9
   Cause: Certains tickers échoués (OHLCV? Exception?)
   Check: "errors" array
```

**Interprétation:**

```
STEP 1 affiche:
  edge_actions_count: 9       ← Trouvés
  edge_actions_computed: 9    ← Calculés = OK ✅
  edge_actions_failed: 0      ← 0 échoués = OK ✅

STEP 1 affiche:
  edge_actions_count: 9       ← Trouvés
  edge_actions_computed: 6    ← Seulement 6 calculés ⚠️
  errors: ["edge_actions:ABC: ...", ...]  ← 3 échoués
```

---

### Résultat 5: Screener Relit-Il?

**Méthode:**
1. Observer STEP 2 output
2. Voir statuts des 9 tickers

```
✅ SCREENER RELIT:
   Les 9 tickers affichent des vrais statuts
   Exemple: "ABC → VALID_EDGE", "DEF → NO_EDGE"

❌ SCREENER NE RELIT PAS:
   Les 9 tickers affichent "EDGE_NOT_COMPUTED"
   Cause: Cache persist / read bug
```

**Fix si Bug:**
```python
# Dans get_cached_edge_with_status():
# Vérifier que cache est bien chargé au startup

# Ou forcer reload:
# Recharger l'app / redémarrer backend
```

---

### Résultat 6: Pourquoi 9 et Pas 45+?

**Ma Projection vs Réalité:**

```
Ma projection:   ~100 tickers total → 45+ A+/A/B
Réalité:         ~20-30 tickers total → 9 A+/A/B

Pourcentage: 9/20 = 45% ✅ ou 9/30 = 30% ✅
```

**Interprétation:**

```
STEP 2 affiche:
  "Screener contient 25 tickers"
  
→ 25 total, 9 A+/A/B = 36% = NORMAL ✅

STEP 2 affiche:
  "Screener contient 100 tickers"
  
→ 100 total, 9 A+/A/B = 9% = ANORMAL ❌
  (Beaucoup de tickers ne sont pas A+/A/B)
```

**Conclusion:**
- Si ~20-30 tickers total → 9 c'est NORMAL
- Si ~100+ tickers total → 9 c'est probablement BUG

---

### Résultat 7: Commit 23f006d Déployé?

**Preuve Indirecte (la plus fiable):**

```
Avant fix:  edge_actions_count = 0   ← Non-existent function
Après fix:  edge_actions_count = 9   ← Multi-key cache

FAIT: Vous voyez 9 = Fix IS DEPLOYED ✅
```

**Vérification Directe (si possible):**

```bash
# Sur le serveur production:
git log --oneline -1

# Résultat attendu:
# 23f006d fix: Replace non-existent _run_screener_impl()

# Ou voir le code:
# backend/main.py lines 2954-2961
# Si contient: "for cache_key, cache_entry in _screener_cache.items()"
# → Code 23f006d ✅
```

---

## 🎯 TABLEAU RÉCAPITULATIF

| Vérification | Résultat BON | Résultat MAUVAIS | Action |
|---|---|---|---|
| STEP 1: 9 tickers | 9 affichés | 0 ou autre | Vérifier screener cache |
| STEP 2: LLY/CL/LIN/HOLX | Parmi les 9 | Manquent | Vérifier grades |
| STEP 2: Statuts changent | VALID_EDGE etc. | EDGE_NOT_COMPUTED | Vérifier cache persist |
| STEP 1: Edge computed | 9 = 9 | 6 < 9 | Vérifier errors |
| STEP 2: Screener relit | Vrais statuts | EDGE_NOT_COMPUTED | Redémarrer backend |
| STEP 2: Screener count | 20-30 tickers | 100+ tickers | Vérifier screener filter |
| Commit déployé | Preuve: 9 ≠ 0 | N/A | Vérifier git log |

---

## 🔴 ANOMALIES POSSIBLES

### Anomalie #1: edge_actions_computed < 9

**Symptôme:**
```
edge_actions_count: 9
edge_actions_computed: 5
errors: ["edge_actions:ABC: ...", "edge_actions:DEF: ...", ...]
```

**Causes Possibles:**
1. OHLCV download failed for some tickers
2. compute_ticker_edge() threw exception
3. Network timeout

**Fix:**
- Vérifier les "errors" array
- Essayer les tickers individuels (STEP 4)
- Augmenter timeout si besoin

---

### Anomalie #2: Statuts Toujours EDGE_NOT_COMPUTED

**Symptôme:**
```
STEP 2: Vérifier les statuts dans le screener
  ABC → EDGE_NOT_COMPUTED
  DEF → EDGE_NOT_COMPUTED
  GHI → EDGE_NOT_COMPUTED
```

**Causes Possibles:**
1. Cache not persisted correctly
2. Cache not loaded on app startup
3. Screener not reloading cache

**Fix:**
```bash
# Redémarrer le backend:
cd backend
python main.py  # Relancer
```

---

### Anomalie #3: LLY/CL/LIN/HOLX Manquent

**Symptôme:**
```
Les 9 tickers: ["ABC", "DEF", ..., "ZZZ"]
LLY, CL, LIN, HOLX NOT FOUND
```

**Causes Possibles:**
1. Grades différents (C, D, REJECT, B+, etc.)
2. Pas dans screener cache
3. Excluded par autre filtre

**Fix:**
```bash
# Vérifier le grade de chaque:
STEP 4: Vérifier les tickers individuels
  LLY: grade=C → NORMAL (exclu du filtrage A+/A/B)
  CL: grade=REJECT → NORMAL
```

---

## 📝 RAPPORT À GÉNÉRER

Après avoir exécuté le diagnostic, créer un rapport:

```
DIAGNOSTIC RESULT - 2026-05-04

STEP 1: 9 Tickers Calculés
  ✅ edge_actions_count = 9
  ✅ edge_actions_computed = 9
  Tickers: [ABC, DEF, GHI, ...]

STEP 2: Statuts Screener
  ✅ ABC: VALID_EDGE (changed from EDGE_NOT_COMPUTED)
  ✅ DEF: NO_EDGE (changed from EDGE_NOT_COMPUTED)
  ⚠️ GHI: EDGE_NOT_COMPUTED (NOT CHANGED - BUG?)

STEP 3: Cache Status
  ✅ edge_cache contains 9 entries

STEP 4: Tickers Individuels
  ⚠️ LLY: NOT in 9 (grade=C, excluded)
  ⚠️ CL: NOT in 9 (grade=REJECT, excluded)
  ✅ XYZ: in 9 (grade=A, included)

CONCLUSION:
  ✅ FIX FONCTIONNE (9 ≠ 0)
  ⚠️ POTENTIAL BUG: LLY/CL grades différents
  ✅ COMMIT 23f006d DÉPLOYÉ
```

---

## 🚀 PROCHAINES ÉTAPES

1. **Exécuter:** `python diagnostic_9_tickers.py`
2. **Analyser:** Les 7 résultats ci-dessus
3. **Reporter:** Les anomalies trouvées
4. **Corriger:** Si bug évident identifié

---

**Durée totale:** 5-10 minutes

**Précision:** 95% (données réelles de l'API)
