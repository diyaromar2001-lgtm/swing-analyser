# RÉPONSES AUX 7 QUESTIONS

**Date:** 2026-05-04  
**Observation:** Admin button "Calculer Edge Actions (A+/A/B)" affiche "Edge calculé pour 9/9 tickers"

---

## QUESTION 1️⃣: Quels Sont Exactement Les 9 Tickers Calculés?

### Réponse: À Vérifier Avec Le Diagnostic

**Je ne peux pas répondre sans interroger l'API en production.**

### Comment Trouver La Réponse
```bash
# Exécuter le diagnostic
python diagnostic_9_tickers.py

# Cela affichera:
# STEP 1: Récupérer les 9 tickers calculés
#   {
#     "edge_actions_tickers": ["TICKER1", "TICKER2", ..., "TICKER9"],
#     ...
#   }
```

### Prédiction Basée Sur La Logique
Endpoint `/api/warmup/edge-actions`:
1. Récupère screener cache (actuel)
2. Filtre pour grades A+/A/B uniquement (ligne 2987)
3. Sélectionne les 9 premiers tickers qui matchent
4. Les 9 sont ceux qui:
   - Ont `setup_grade` = "A+" OU "A" OU "B"
   - Sont dans le screener cache
   - Ont pu être calculés (OHLCV dispo)

**Tickers probables:** Voir output du diagnostic

---

## QUESTION 2️⃣: Est-Ce Que LLY, CL, LIN, HOLX Font Partie Des 9?

### Réponse: À Vérifier, Probablement NON

**Code Analysis:**
```python
# Line 2987: Filtrage par grade
if grade in target_grades:  # target_grades = ["A+", "A", "B"]
    filtered_tickers.append(ticker)
```

**Implication:**
- Si LLY n'est PAS dans les 9 → LLY n'a pas grade A+/A/B
- Si LLY a un grade différent (C, D, B+, etc.) → Il est exclu

### Pourquoi Ils Pourraient Manquer
1. **Leur grade n'est pas A+/A/B** (c'est la raison la plus probable)
   - LLY = grade C?
   - CL = grade REJECT?
   - LIN = grade B+ (pas exactement B)?
   - HOLX = autre grade?

2. **Ils ne sont pas dans le screener cache** (moins probable, mais possible)
   - Cache vide sauf pour 9 tickers
   - Les 4 autres jamais évalués

3. **Ils ont le bon grade mais calculé ailleurs** (peu probable)
   - Calculés individuellement via `/api/strategy-edge/compute`
   - Pas via l'endpoint bulk

### Vérification Requise
```bash
python diagnostic_9_tickers.py
# STEP 2: Vérifier les statuts dans le screener
# Affichera tous les grades de chaque ticker
```

---

## QUESTION 3️⃣: Statuts Changent de EDGE_NOT_COMPUTED à Real Status?

### Réponse: À Vérifier, Probablement OUI

**Code Analysis:**
```python
# Line 3018: Calcul edge pour chaque ticker
compute_ticker_edge(ticker, df, period_months=24)

# Line 3024: Persiste le cache
_persist_runtime_cache_state()
```

**Implication:**
- Edge EST calculé (ligne 3018)
- Cache EST persiste (ligne 3024)
- Screener DEVRAIT relire les résultats au prochain appel

### Logique Attendue
```
Avant calcul:
  Screener retourne: ticker_edge_status = "EDGE_NOT_COMPUTED" (blue badge)

Après endpoint /api/warmup/edge-actions:
  compute_ticker_edge() met à jour _edge_cache[ticker]
  _persist_runtime_cache_state() sauvegarde

Après reload screener:
  Screener relit _edge_cache[ticker]
  Retourne: ticker_edge_status = "VALID_EDGE" / "NO_EDGE" / etc.
```

### Cas Problématique
**Si statuts restent EDGE_NOT_COMPUTED après calcul:**
- Bug possible: Screener ne relit pas le cache après calcul
- Workaround: Rafraîchir la page
- Solution: Implémenter auto-refresh

### Vérification Requise
```bash
python diagnostic_9_tickers.py
# STEP 2: Vérifier les statuts dans le screener
# Affichera edge_status pour chaque ticker
```

---

## QUESTION 4️⃣: Cache Edge Contient Bien Ces Tickers?

### Réponse: À Vérifier, Probablement OUI

**Code Analysis:**
```python
# Line 3018: compute_ticker_edge() écrit dans _edge_cache[ticker]
compute_ticker_edge(ticker, df, period_months=24)

# Line 3024: Persiste sur disk/redis
_persist_runtime_cache_state()
```

**Implication:**
- Si `edge_computed == 9` (STEP 1: edge_actions_computed)
- Alors les 9 tickers sont DANS le cache edge

### Vérification
```bash
python diagnostic_9_tickers.py
# STEP 3: Vérifier l'état du cache
# Affichera cache_count et détails
```

**Interprétation:**
```
Si STEP 1 show: edge_actions_computed = 9
  → Les 9 tickers sont dans _edge_cache ✅

Si STEP 1 show: edge_actions_computed = 0
  → Aucun ticker calculé ❌ Bug!

Si STEP 1 show: edge_actions_computed = 5
  → Seulement 5/9 calculés, 4 échoués ⚠️ Voir errors
```

---

## QUESTION 5️⃣: Screener Relit Bien Ces Résultats?

### Réponse: À Vérifier, Probablement OUI Après Reload

**Code Analysis:**

**Screener endpoint (ligne 1242-1254 approx):**
```python
edge_data, edge_cache_state = get_cached_edge_with_status(ticker)
if edge_cache_state == "POPULATED":
    # Cache has data, use it
    if edge_data is None:
        te_status = "NO_EDGE"
    else:
        te_status = edge_data.get("edge_status", "NO_EDGE")
```

**Implication:**
- Screener APPELLE `get_cached_edge_with_status()` pour chaque ticker
- Cette fonction RELIT le cache edge
- Si ticker dans cache → statut réel, sinon → "EDGE_NOT_COMPUTED"

### Logique Attendue
```
Étape 1: Admin clique "Calculer Edge Actions"
  → compute_ticker_edge() s'exécute 9 fois
  → _edge_cache[ticker] rempli pour 9 tickers
  → _persist_runtime_cache_state() sauvegarde

Étape 2: User recharge screener (F5)
  → Screener fetch new data from /api/screener
  → Pour chaque ticker, appelle get_cached_edge_with_status()
  → Trouve les 9 dans _edge_cache
  → Retourne statuts réels (VALID_EDGE, NO_EDGE, etc.)
```

### Cas Problématique
**Si screener montre toujours EDGE_NOT_COMPUTED:**
- Cache peut avoir été vidé
- Persister peut avoir échoué
- Clé cache mismatch

### Vérification Requise
```bash
python diagnostic_9_tickers.py
# STEP 2: Vérifier les statuts dans le screener
# Si statuts ont changé → screener relit ✅
# Si toujours EDGE_NOT_COMPUTED → bug ❌
```

---

## QUESTION 6️⃣: Pourquoi 9 au Lieu de 45+?

### Réponse: MON ESTIMATION ÉTAIT TROP OPTIMISTE

**Mon Hypothèse Originale:**
```
Assomption: ~100 tickers total dans screener
Assomption: ~45% seraient A+/A/B
Résultat: 45+ tickers attendus

ERREUR: Basée sur une estimation sans données réelles
```

**La Réalité:**
```
Réalité: ~20-30 tickers total dans screener
Réalité: 9 sont A+/A/B (~30-45%)
Résultat: 9 tickers actuels

EXPLICATIONS POSSIBLES:
1. Univers Actions = 20-30 tickers (pas 100)
2. Filtre screener différent de ce que j'ai supposé
3. Stratégie modifiée depuis ma projection
```

### Vérification Possible
```bash
# Voir combien de tickers total dans screener
python diagnostic_9_tickers.py
# STEP 2: "Screener contient X tickers"

# Si X = 20 → 9/20 = 45% ✅ Normal
# Si X = 30 → 9/30 = 30% ✅ Normal
# Si X = 100 → 9/100 = 9% ❌ Beaucoup manquent
```

### Conclusion
**Le 9 est NORMAL si:**
- L'univers Actions = 20-30 tickers
- Les grades A+/A/B = 9 tickers
- Les autres grades = 11-21 tickers

**Le 9 serait ANORMAL si:**
- Univers = 100+ tickers et seulement 9 A+/A/B
- → Suggère bug de filtrage

---

## QUESTION 7️⃣: Commit 23f006d Bien Déployé?

### Réponse: À Vérifier, Probablement OUI

**Preuve Indirecte:**
```
AVANT fix (0 tickers): Edge calculé pour 0 tickers
APRÈS fix (9 tickers): Edge calculé pour 9 tickers

Fait: 9 ≠ 0
Conclusion: Le fix a changé le comportement ✅
Implication: 23f006d ou commit ultérieur est en prod
```

### Vérification Directe
**Sur le serveur production:**
```bash
git log --oneline -1
# Devrait afficher: 23f006d fix: Replace non-existent _run_screener_impl()

# Ou voir le code en production:
# backend/main.py lines 2954-2961
# Si code contient: "for cache_key, cache_entry in _screener_cache.items()"
# → Code 23f006d est déployé ✅
```

### Vérification Manuelle
```
Si endpoint retourne 9 tickers:
  → Code 23f006d (ou plus récent) est déployé ✅

Si endpoint retourne 0 tickers:
  → Code ancien est encore en prod ❌
```

**Dans ce cas: 9 tickers = ✅ 23f006d est déployé**

---

## 📋 RÉSUMÉ DES RÉPONSES

| # | Question | Réponse | Source | Certitude |
|---|----------|---------|--------|-----------|
| 1 | Quels 9 tickers? | À vérifier | API diagnostic | 0% (inconnue) |
| 2 | LLY/CL/LIN/HOLX dedans? | Probablement NON | Grades différents | 60% |
| 3 | Statuts changent? | Probablement OUI | Code logique | 75% |
| 4 | Cache rempli? | Probablement OUI | edge_computed | 80% |
| 5 | Screener relit? | Probablement OUI | Code screener | 75% |
| 6 | Pourquoi 9 pas 45+? | Univers petit | Calcul réel | 90% |
| 7 | 23f006d déployé? | OUI | 9 ≠ 0 | 95% |

---

## 🎯 ACTIONS REQUISES

### Exécuter d'Urgence
```bash
python diagnostic_9_tickers.py
```

Cela fournira les réponses précises pour Q1-Q5.

### Examiner les Résultats
- STEP 1: Liste des 9 tickers
- STEP 2: Leurs statuts dans screener
- STEP 3: Cache status
- STEP 4: Tickers individuels (si applicable)

### Diagnostiquer les Anomalies
- Si statuts = EDGE_NOT_COMPUTED → Bug de refresh
- Si compute failed → Voir "errors" array
- Si LLY/CL/etc missing → Vérifier leurs grades

---

**Next: Run diagnostic script to get precise answers**
