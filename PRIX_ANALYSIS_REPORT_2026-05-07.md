# RAPPORT D'ANALYSE PRIX : Snapshot vs Intraday
**Date:** 2026-05-07  
**Scope:** 5 symboles (TON, ETH, BTC, MKR, SOL)  
**Source:** Production Railway via champs prix ajoutés (cf61713)  
**Statut:** Analyse sans modification de code

---

## RÉSUMÉ EXÉCUTIF

**PROBLÈME IDENTIFIÉ:** Deux cryptos (TON, MKR) montrent des divergences MASSIVES (>30%) entre le prix snapshot et le prix intraday.

**DONNÉES ACTUELLES:**
- **TON:** snapshot=2.424 vs intraday=1.837 → **31.95% d'écart** → price_suspect=True
- **MKR:** snapshot=1777.53 vs intraday=1347.21 → **31.94% d'écart** → price_suspect=True
- **ETH:** snapshot=2347.69 vs intraday=2361.36 → 0.58% (normal)
- **BTC:** snapshot=81306.51 vs intraday=81288.84 → 0.02% (normal)
- **SOL:** snapshot=89.12 vs intraday=85.42 → 4.33% (mineur)

**IMPACT:** Tous les symboles avec divergence >5% ont `entry=None` (aucun signal généré).

---

## TABLEAU COMPARATIF DÉTAILLÉ

| Symbole | Prix Snapshot | Prix Intraday | Divergence | Status | Price Suspect | Entry | SL | TP1 |
|---------|---------------|---------------|-----------|--------|---------------|-------|----|----|
| **TON** | 2.424 | 1.837 | **31.95%** | FRESH | YES | None | None | None |
| **MKR** | 1777.53 | 1347.21 | **31.94%** | FRESH | YES | None | None | None |
| **ETH** | 2347.69 | 2361.36 | 0.58% | FRESH | NO | None | None | None |
| **BTC** | 81306.51 | 81288.84 | 0.02% | FRESH | NO | None | None | None |
| **SOL** | 89.12 | 85.42 | 4.33% | FRESH | NO | None | None | None |

---

## ANALYSE DÉTAILLÉE PAR SYMBOLE

### TON: DIVERGENCE MASSIVE (31.95%)

```
Prix Snapshot (displayed):      2.424
Prix Intraday 5m (last close): 1.837
Divergence:                     31.95%
Price Suspect:                  TRUE
Entry Level:                    NONE (no signal due to suspect prices)
```

**Observations:**
- Snapshot est 32% PLUS HAUT que l'intraday réel
- Cela signifie que le snapshot est stale (ancien) ou erroné
- L'intraday 1.837 est probablement la source de vérité (dernière bougie 5m)
- Algorithme rejette ce symbole car la divergence dépasse 5%
- Si on utilisait snapshot=2.424 comme base, les entry/SL/TP seraient 32% trop hauts

**Question clé:** Est-ce que TON a vraiment augmenté de 2.424 ailleurs, ou le snapshot de Crypto Scalp est-il en retard sur les données intraday (Binance)?

---

### MKR: DIVERGENCE MASSIVE (31.94%)

```
Prix Snapshot (displayed):      1777.53
Prix Intraday 5m (last close): 1347.21
Divergence:                     31.94%
Price Suspect:                  TRUE
Entry Level:                    NONE (no signal due to suspect prices)
```

**Observations:**
- Snapshot est 32% PLUS HAUT que l'intraday
- Identique au pattern TON (suspicious!)
- L'intraday 1347.21 semble être la vraie source
- Algorithme rejette correctement ce symbole

**Question clé:** Deux cryptos avec exactement la même divergence (~32%) suggère un problème systématique de source de données, pas une coïncidence.

---

### ETH: DIVERGENCE MINEURE (0.58%)

```
Prix Snapshot (displayed):      2347.69
Prix Intraday 5m (last close): 2361.36
Divergence:                     0.58%
Price Suspect:                  FALSE
Entry Level:                    NONE (other reasons)
```

**Observations:**
- Divergence est MINEURE et dans la plage normale
- Prix sont essentiellement identiques (0.58%)
- Intraday est même LÉGÈREMENT plus haut (2361.36 vs 2347.69)
- Cela indique une source snapshot saine pour ETH

---

### BTC: DIVERGENCE MINIMALE (0.02%)

```
Prix Snapshot (displayed):      81306.51
Prix Intraday 5m (last close): 81288.84
Divergence:                     0.02%
Price Suspect:                  FALSE
Entry Level:                    NONE (other reasons)
```

**Observations:**
- Divergence est QUASI-ZÉRO (0.02%)
- Snapshot et intraday sont pratiquement identiques
- Source snapshot est saine et actualisée
- Ceci est un comportement normal et sain

---

### SOL: DIVERGENCE ACCEPTABLE (4.33%)

```
Prix Snapshot (displayed):      89.12
Prix Intraday 5m (last close): 85.42
Divergence:                     4.33%
Price Suspect:                  FALSE
Entry Level:                    NONE (other reasons)
```

**Observations:**
- Divergence est JUSTE SOUS 5% (4.33%)
- Snapshot est légèrement plus haut (non critique)
- Dans la plage acceptable (algorithm permet jusqu'à 5%)
- Source snapshot est raisonnablement actualisée

---

## ANALYSE SYSTÉMATIQUE

### Patterns Observés

**Groupe 1: Divergence Critique (>30%)**
- TON: 31.95%
- MKR: 31.94%

**Observations:**
- Les deux ont EXACTEMENT la même divergence (~32%)
- Ce n'est pas une coïncidence - c'est un problème systématique
- Price_suspect=True pour tous les deux
- Entry=None (algorithme les rejette correctement)

**Hypothèses sur la cause:**
1. Le snapshot provient d'une source différente (pas Binance)?
2. Le snapshot est mis à jour moins fréquemment que l'intraday?
3. Il existe une décalage horaire ou timezone entre snapshot et intraday?
4. Un cache stale sur le backend pour certains symboles?

**Groupe 2: Divergence Normale (<5%)**
- ETH: 0.58%
- BTC: 0.02%
- SOL: 4.33%

**Observations:**
- Les divergences sont mineures et attendues
- Reflètent le décalage naturel entre deux sources à des moments différents
- Comportement normal et sain

### Distribution des Prix

**Si on utilisait SNAPSHOT comme source (comportement actuel):**
- TON: 2.424 (suspect, 32% trop haut)
- MKR: 1777.53 (suspect, 32% trop haut)
- ETH: 2347.69 (acceptable)
- BTC: 81306.51 (acceptable)
- SOL: 89.12 (acceptable)

**Si on utilisait INTRADAY comme source (alternative):**
- TON: 1.837 (conforme à la dernière bougie 5m)
- MKR: 1347.21 (conforme à la dernière bougie 5m)
- ETH: 2361.36 (légèrement plus haut que snapshot, mais actuel)
- BTC: 81288.84 (essentiellement identique)
- SOL: 85.42 (plus bas que snapshot, mais plus actuel)

---

## RÉPONSES AUX QUESTIONS DE DIAGNOSTIC

### A. Est-ce que les prix sont réellement faux sur plusieurs cryptos?

**RÉPONSE: OUI, partiellement.**

- **TON:** Prix snapshot (2.424) semble FAUX ou STALE vs intraday (1.837)
- **MKR:** Prix snapshot (1777.53) semble FAUX ou STALE vs intraday (1347.21)
- **ETH/BTC/SOL:** Prix snapshot semble CORRECT et accepté

Le problème affecte au moins 2 symboles (40% de l'échantillon testé).

---

### B. Est-ce que c'est seulement TON?

**RÉPONSE: NON, c'est aussi MKR.**

TON et MKR montrent le même pattern de divergence (31.95% vs 31.94%).

C'est probablement un problème systématique affectant d'autres symboles avec des données similaires (petite cap, volatilité haute, sources de données fragmentées).

---

### C. Est-ce que le problème vient du snapshot?

**RÉPONSE: PROBABLEMENT OUI.**

**Preuves:**
1. L'intraday data vient de Binance (source fiable et standardisée)
2. Le snapshot pour TON/MKR est significativement différent (32% d'écart)
3. BTC et ETH (grandes caps liquides) n'ont PAS ce problème de snapshot
4. Le pattern est identique pour TON et MKR → problème systématique, pas bruit aléatoire

**Conclusion:** Le snapshot pour certains symboles est soit:
- Stale (pas mis à jour fréquemment)
- Provenant d'une source moins fiable
- Décalé temporellement vs l'intraday

---

### D. Est-ce que Crypto Scalp devrait passer à intraday_last_close pour displayed_price et calculs?

**RÉPONSE: OUI, pour ces symboles spécifiques (TON, MKR).**

**Justification:**

**Avantages:**
1. `intraday_last_close` vient de Binance (source standardisée et fiable)
2. C'est la dernière bougie 5m, donc très récent
3. Élimine la divergence de 32% pour TON/MKR
4. Permettrait des signaux valides au lieu de None

**Inconvénients:**
1. Le prix 5m peut être volatile (peut changer à chaque nouvelle bougie)
2. Pour certains symboles (BTC, ETH), le snapshot est déjà bon
3. Il faudrait tester si les signaux générés seraient sains

**Recommandation nuancée:**
- **Phase A (court terme):** Garder snapshot, mais ALERTER sur les divergences (price_suspect=True) → déjà en place
- **Phase B (moyen terme):** Tester avec intraday_last_close pour entry/SL/TP sur TON/MKR uniquement
- **Phase C (long terme):** Unifier la source de prix (Binance intraday pour tous)

---

## IMPACT SUR ENTRY/STOP_LOSS/TP

**Actuellement:**
- Tous les symboles montrent `entry=None`, `stop_loss=None`, `tp1=None`, `tp2=None`
- C'est dû à des raisons de grading et de signal strength (pas juste le prix)

**SI on passait à intraday_last_close comme source:**

| Symbole | Actuel (snapshot) | Alternative (intraday) | Différence |
|---------|-------------------|------------------------|-----------|
| TON | entry=None, base=2.424 | entry=?, base=1.837 | **-32% (32% plus bas)** |
| MKR | entry=None, base=1777.53 | entry=?, base=1347.21 | **-32% (32% plus bas)** |
| ETH | entry=None, base=2347.69 | entry=None, base=2361.36 | +0.6% (minime) |
| BTC | entry=None, base=81306.51 | entry=None, base=81288.84 | -0.02% (minime) |
| SOL | entry=None, base=89.12 | entry=None, base=85.42 | -4.3% (mineur) |

**Pour TON et MKR:** Les niveaux d'entry/SL/TP seraient environ 32% plus bas avec l'intraday.

---

## SÉCURITÉ CONFIRMÉE

✅ Cette analyse:
- N'a modifié AUCUN code
- N'a touché à AUCUNE logique de trading
- N'a touché à Paper/Watchlist
- N'a ajouté AUCUNE exécution réelle
- N'a ajouté AUCUN levier
- N'a touché Actions/Crypto Swing

✅ Les champs prix ajoutés (cf61713):
- Sont purement informationnels
- Permettent le diagnostic sans impacter le trading
- Ont correctement détecté les divergences (price_suspect=True)
- N'ont cassé AUCUNE sécurité

---

## CORRECTION RECOMMANDÉE

**Court terme (maintenant):** 
✅ Garder le code actuel (snapshot + diagnostic) → Stable et sûr

**Moyen terme (Phase 3A/3B):**
→ Option 1: Tester intraday_last_close pour TON/MKR uniquement (minimal risk)
→ Option 2: Implémenter switch dynamique (use intraday si divergence > 5%, sinon snapshot)
→ Option 3: Attendre correction de la source snapshot

**Long terme:**
→ Unifier à Binance intraday 5m pour tous les symboles (source unique, fiable)

---

## PROCHAINES ÉTAPES (PAS MAINTENANT)

1. **Valider:** L'intraday data pour TON/MKR est-elle correcte?
2. **Tester:** Générer les signaux avec intraday au lieu de snapshot
3. **Comparer:** Les signaux sont-ils plus sains?
4. **Décider:** Implémenter le changement ou attendre correction snapshot?

---

## CONCLUSION

Le diagnostic est CLAIR:
- ✅ Les champs prix ajoutés (cf61713) fonctionnent correctement
- ✅ Ils ont détecté des problèmes réels (TON/MKR divergence >30%)
- ✅ L'algorithme les gère correctement (reject avec price_suspect=True)
- ✅ Aucune sécurité compromise
- ⚠️ TON et MKR utilisent des prix potentiellement stale/erronés
- 📋 Recommandation: Analyser puis potentiellement basculer vers intraday_last_close

**Le système est stable. Le problème est documenté et traçable. Aucune action d'urgence requise.**

---

**Rapport généré:** 2026-05-07  
**Source:** Analyse production sans modification de code  
**Statut:** Prêt pour discussion et décision utilisateur
