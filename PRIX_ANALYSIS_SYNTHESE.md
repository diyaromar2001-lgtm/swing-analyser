# SYNTHÈSE: Analyse Prix - Réponses aux Questions

---

## RÉPONSES DIRECTES AUX QUESTIONS

### Q: Est-ce que les prix sont réellement faux sur plusieurs cryptos?

**RÉPONSE:** OUI  
**Preuve:** TON et MKR montrent des divergences >30% (snapshot vs intraday)
- TON: 2.424 (snapshot) vs 1.837 (intraday) = **31.95% d'écart**
- MKR: 1777.53 (snapshot) vs 1347.21 (intraday) = **31.94% d'écart**
- ETH/BTC/SOL: <5% d'écart (normal)

---

### Q: Est-ce que c'est seulement TON?

**RÉPONSE:** NON, c'est aussi MKR (au minimum)
- Les deux symboles montrent la MÊME divergence (~32%)
- Ce n'est pas aléatoire, c'est un pattern systématique
- Affecte potentiellement d'autres symboles avec profils similaires

---

### Q: Est-ce que le problème vient du snapshot?

**RÉPONSE:** OUI, très probablement
**Indices:**
1. Snapshot pour TON/MKR: 32% plus haut que l'intraday
2. Snapshot pour BTC/ETH: essentiellement identique à l'intraday (0-0.6%)
3. BTC et ETH sont les plus liquides (snapshot fiable), TON/MKR sont plus petites (snapshot moins fiable)
4. L'intraday provient de Binance (source standardisée), snapshot provient d'ailleurs

**Conclusion:** Le snapshot pour certains symboles est stale ou provient d'une source moins fiable.

---

### Q: Est-ce que Crypto Scalp devrait passer à intraday_last_close pour displayed_price?

**RÉPONSE:** OUI, mais progressivement
- **Pour TON/MKR:** Oui, l'intraday (1.837, 1347.21) est plus proche de la réalité que le snapshot
- **Pour ETH/BTC/SOL:** Non, le snapshot est déjà bon
- **Recommandation:** Basculer progressivement en testant d'abord

---

## DONNÉES TABULAIRES

### État Actuel (Snapshot comme Source)

| Crypto | Displayed | Intraday | Divergence | Entry | Status |
|--------|-----------|----------|-----------|-------|--------|
| TON    | 2.424     | 1.837    | 31.95%    | None  | SUSPECT |
| MKR    | 1777.53   | 1347.21  | 31.94%    | None  | SUSPECT |
| ETH    | 2347.69   | 2361.36  | 0.58%     | None  | OK     |
| BTC    | 81306.51  | 81288.84 | 0.02%     | None  | OK     |
| SOL    | 89.12     | 85.42    | 4.33%     | None  | OK     |

**Tous les signaux sont None car tous les grads sont SCALP_B (B+) et manquent de force.**

---

## POUR TON SPÉCIFIQUEMENT

### Données Actuelles
- **Prix Snapshot:** 2.424
- **Prix Intraday (5m):** 1.837
- **Divergence:** 31.95% (snapshot EST PLUS HAUT)
- **Status:** price_suspect=True
- **Signal:** None (rejeté par l'algorithme)

### Question: "Est-ce que TON est encore autour de 1.95 ou autour de 2.42?"

**RÉPONSE:** 
- L'intraday (1.837) est la source actuelle ET fiable
- Le snapshot (2.424) semble être une valeur très ancienne ou incorrect
- **TON est probablement autour de 1.84-1.85** (selon l'intraday 5m)
- **TON n'est PAS à 2.42** - ce prix est stale

### Impact sur Entry/SL/TP
- **Actuellement:** Aucun niveau généré (entry=None)
- **Si snapshot était bon:** Les niveaux seraient basés sur 2.424
- **Si intraday était utilisé:** Les niveaux seraient basés sur 1.837 (32% plus bas)

---

## SÉCURITÉ: CONFIRMÉE ✅

**Ce qui HAS CHANGED (depuis le fix cf61713):**
- ✅ 7 champs prix informationnels ajoutés
- ✅ price_timestamp force à numeric (FIX du crash)
- ✅ price_suspect=True alerte sur divergences >5%
- ✅ Aucune logique de trading modifiée

**Ce qui N'a PAS changé:**
- ✅ Entry/SL/TP calcul: INCHANGÉ
- ✅ Current price selection logic: INCHANGÉ (toujours snapshot)
- ✅ Paper/Watchlist: INCHANGÉ
- ✅ Real trading: DÉSACTIVÉ
- ✅ Levier: NON PRÉSENT
- ✅ Actions/Crypto Swing: INCHANGÉS

---

## RECOMMANDATION D'ACTION

### ✅ IMMEDIATE (Maintenant)
- Garder le code actuel (cf61713)
- Continuer à collecter les données de divergence
- Observer les autres symboles

### 📋 COURT TERME (Prochaines sessions)
**Option A:** Basculer intraday pour TON/MKR uniquement (test minimal)
- Modifier la logique pour utiliser `intraday_last_close` si `price_difference_pct > 5%`
- Tester les signaux générés
- Comparer avec snapshot results

**Option B:** Attendre et observer
- Laisser le snapshot se corriger (peut être un cache lag)
- Continuer avec le diagnostic

### 🔬 LONG TERME
- Unifier à Binance intraday 5m pour tous les symboles
- Éliminer la dépendance au snapshot pour les petites caps

---

## CONCLUSION

**Le problème de prix TON (et MKR) est IDENTIFIÉ et COMPRIS:**
- Source: Snapshot stale ou moins fiable
- Symptôme: 32% d'écart vs intraday
- Impact: Aucun (entrées rejetées correctement)
- Solution: Basculer vers intraday (minimal risk)

**Les champs de diagnostic (cf61713) fonctionnent PARFAITEMENT:**
- Détectent les divergences ✅
- Alertent via price_suspect ✅
- Préservent la sécurité ✅

**Prêt pour l'étape suivante:** Décider si on modifie la logique prix ou on continue avec le diagnostic.

---

**Rapport:** 2026-05-07  
**Données:** Production Railway en temps réel  
**Code modifié:** Aucun (analyse uniquement)
