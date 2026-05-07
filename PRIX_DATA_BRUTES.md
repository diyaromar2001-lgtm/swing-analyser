# DONNÉES BRUTES: Analyse Prix Production
**Date:** 2026-05-07  
**Source:** Railway production endpoint  
**Format:** Raw JSON extracted + tableau récapitulatif

---

## TON - Données Complètes

```
Symbol:              TON
displayed_price:     2.424
snapshot_price:      2.424
intraday_last_close: 1.837
price_source:        snapshot
price_timestamp:     1778107484.1949847
price_suspect:       True
price_difference_pct: 31.95
data_status:         FRESH
scalp_score:         48
scalp_grade:         SCALP_B
entry:               None
stop_loss:           None
tp1:                 None
tp2:                 None
```

**Analyse:**
- Divergence critique (31.95%)
- Prix utilisé: snapshot (2.424)
- Prix réel (intraday): 1.837
- **Écart: -32% (snapshot trop haut)**
- Algorithme rejette (price_suspect=True, no signal)

---

## MKR - Données Complètes

```
Symbol:              MKR
displayed_price:     1777.53
snapshot_price:      1777.53
intraday_last_close: 1347.21
price_source:        snapshot
price_timestamp:     1778107482.5287287
price_suspect:       True
price_difference_pct: 31.94
data_status:         FRESH
scalp_score:         52
scalp_grade:         SCALP_B
entry:               None
stop_loss:           None
tp1:                 None
tp2:                 None
```

**Analyse:**
- Divergence critique (31.94%)
- Prix utilisé: snapshot (1777.53)
- Prix réel (intraday): 1347.21
- **Écart: -32% (snapshot trop haut)**
- Algorithme rejette (price_suspect=True, no signal)

---

## ETH - Données Complètes

```
Symbol:              ETH
displayed_price:     2347.69
snapshot_price:      2347.69
intraday_last_close: 2361.36
price_source:        snapshot
price_timestamp:     1778107483.8715117
price_suspect:       False
price_difference_pct: 0.58
data_status:         FRESH
scalp_score:         43
scalp_grade:         SCALP_B
entry:               None
stop_loss:           None
tp1:                 None
tp2:                 None
```

**Analyse:**
- Divergence normale (0.58%)
- Prix utilisé: snapshot (2347.69)
- Prix réel (intraday): 2361.36
- **Écart: +0.6% (snapshot très proche, acceptable)**
- Algorithme accepte prix (price_suspect=False)

---

## BTC - Données Complètes

```
Symbol:              BTC
displayed_price:     81306.51
snapshot_price:      81306.51
intraday_last_close: 81288.84
price_source:        snapshot
price_timestamp:     1778107484.0379567
price_suspect:       False
price_difference_pct: 0.02
data_status:         FRESH
scalp_score:         46
scalp_grade:         SCALP_B
entry:               None
stop_loss:           None
tp1:                 None
tp2:                 None
```

**Analyse:**
- Divergence minimale (0.02%)
- Prix utilisé: snapshot (81306.51)
- Prix réel (intraday): 81288.84
- **Écart: -0.02% (snapshot quasi-parfait)**
- Algorithme accepte prix (price_suspect=False)

---

## SOL - Données Complètes

```
Symbol:              SOL
displayed_price:     89.12
snapshot_price:      89.12
intraday_last_close: 85.42
price_source:        snapshot
price_timestamp:     1778107496.0111163
price_suspect:       False
price_difference_pct: 4.33
data_status:         FRESH
scalp_score:         43
scalp_grade:         SCALP_B
entry:               None
stop_loss:           None
tp1:                 None
tp2:                 None
```

**Analyse:**
- Divergence mineure (4.33%)
- Prix utilisé: snapshot (89.12)
- Prix réel (intraday): 85.42
- **Écart: -4.3% (snapshot légèrement haut, acceptable)**
- Algorithme accepte prix (price_suspect=False)

---

## TABLEAU RÉCAPITULATIF COMPACT

```
SYMBOL | SNAPSHOT    | INTRADAY    | DIVERGENCE | SUSPECT | STATUS
-------+-------------+-------------+------------+---------+----------
TON    | 2.424       | 1.837       | 31.95%     | YES     | REJECT
MKR    | 1777.53     | 1347.21     | 31.94%     | YES     | REJECT
ETH    | 2347.69     | 2361.36     | 0.58%      | NO      | OK
BTC    | 81306.51    | 81288.84    | 0.02%      | NO      | OK
SOL    | 89.12       | 85.42       | 4.33%      | NO      | OK
```

---

## COMPARAISON: SI ON UTILISAIT INTRADAY AU LIEU DE SNAPSHOT

```
SYMBOL | CURRENT(SNAP) | ALTERNATIVE(INTRA) | CHANGE
-------+---------------+--------------------+-----------
TON    | 2.424         | 1.837              | -32%
MKR    | 1777.53       | 1347.21            | -32%
ETH    | 2347.69       | 2361.36            | +0.6%
BTC    | 81306.51      | 81288.84           | -0.02%
SOL    | 89.12         | 85.42              | -4.3%
```

**Impact sur entry/SL/TP:**
- TON: 32% plus bas avec intraday
- MKR: 32% plus bas avec intraday
- ETH: quasi-identique
- BTC: quasi-identique
- SOL: 4.3% plus bas avec intraday

---

## DISTRIBUTION DES DIVERGENCES

```
Catégorie                | Symboles    | Divergence
------------------------+-------------+-----------
CRITIQUE (>30%)          | TON, MKR    | ~32%
ACCEPTABLE (5-30%)       | Aucun       | -
NORMAL (<5%)             | ETH, BTC    | <1%
MINEUR (0-5%)            | SOL         | 4.33%
```

---

## OBSERVATIONS STATISTIQUES

**Moyenne divergence:** (31.95 + 31.94 + 0.58 + 0.02 + 4.33) / 5 = **13.76%**

**Médiane divergence:** 4.33%

**Mode (most common):** <5% (3 symboles sur 5)

**Outliers:** TON et MKR (32% chacun)

**Pattern:** 
- Les deux outliers sont exactement identiques (31.95% vs 31.94%)
- Ce n'est PAS aléatoire
- C'est un signal de problème systématique

---

## INTERPRÉTATION

**Scenario 1: Snapshot Stale (Most Likely)**
- Snapshot pour TON/MKR n'a pas été mis à jour récemment
- Intraday 5m est plus actuel
- Explication: Source snapshot = données d'hier, source intraday = données d'aujourd'hui

**Scenario 2: Snapshot Mauvaise Source (Possible)**
- Snapshot provient d'une exchange différente (pas Binance)
- Explication: Différences de prix entre exchanges

**Scenario 3: Conversion Erreur (Unlikely)**
- Erreur de conversion ou calcul sur le prix snapshot
- Mais si c'était une erreur, ce serait aléatoire, pas identique pour 2 symboles

**Scenario 4: Cache Issue (Possible)**
- Cache backend ne s'est pas rafraîchi pour certains symboles
- Explication: Bug dans la logique de mise à jour du cache

---

## RECOMANDATIONS D'ACTION

### Immediate (0-1h)
1. Vérifier la source du snapshot pour TON et MKR
2. Vérifier quand le snapshot a été mis à jour en dernier
3. Comparer avec les données Binance actuelles (confirmé par une tierce source)

### Court terme (1-24h)
1. Implémenter la logique: SI price_difference_pct > 5% ALORS utiliser intraday au lieu de snapshot
2. Tester la génération de signaux avec cette logique
3. Comparer résultats (intraday vs snapshot)

### Long terme (1+ semaine)
1. Unifier à une source unique (Binance intraday pour tous)
2. Deprecier le snapshot ou le fusionner avec intraday
3. Standardiser la collection de données

---

## NOTES DE DEBUGGAGE

Si tu veux tester rapidement:
```bash
# Récupère les données JSON brutes pour un symbole
curl -s https://swing-analyser-production.up.railway.app/api/crypto/scalp/analyze/TON | python3 -m json.tool

# Extrait juste les champs prix
curl -s https://swing-analyser-production.up.railway.app/api/crypto/scalp/analyze/TON | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('displayed:', d.get('displayed_price')); print('snapshot:', d.get('snapshot_price')); print('intraday:', d.get('intraday_last_close')); print('divergence:', d.get('price_difference_pct'))"
```

---

## DOCUMENT À CONSERVER

Ce fichier contient toutes les données brutes pour référence.  
À utiliser avec les documents d'analyse pour validation croisée.

---

**Format:** Données brutes + tableau  
**Date:** 2026-05-07  
**Validité:** Snapshot à moment T (données peuvent changer avec les prix)
