# PROPOSITION: Gestion des R/R Très Faibles en Paper Trading

**Date:** 10 Mai 2026  
**Contexte:** Observation que certains symboles crypto (ARB, AR, UNI) sont Paper Enabled avec R/R < 1.0  
**Type:** Analyse propositionelle (pas de code/phase 3B/backtest)

---

## 1. OBSERVATION DU PROBLÈME

### Cas Observés
- **ARB:** R/R = 1:3.67 (exemple testé, R/R correct mais voir pattern)
- **AR:** R/R = 0.50 (très faible, trade bloqué)
- **UNI:** R/R = 0.35 (très faible, trade bloqué)

### Symptôme
Ces symboles affichent `paper_allowed = true` ou `watchlist_allowed = true` **malgré** un R/R très faible (< 1.0).

### Question Utilisateur
"Pourquoi un trade avec R/R 0.50 (risquer 100 pour gagner 50) est-il autorisé en Paper?"

---

## 2. RACINE: LOGIQUE ACTUELLE DE `paper_allowed`

### Règles Actuelles (Phase 1)
Un trade est `paper_allowed = true` si:
- ✅ Données fraîches ET
- ✅ Pas de blocage Data Quality (divergence ≤ 10%) ET
- ✅ Grade dans (A+, A, B) ET
- ✅ Side dans (LONG, SHORT) — pas NONE ET
- ✅ Spread acceptable ET
- ✅ Entry/SL/TP existent

**ABSENT:** Aucune vérification de R/R minimum

### Pourquoi?
1. **Phase 1 = Paper Only** → pas de pertes réelles → risque acceptable
2. **R/R était concept Phase 3B** (Edge Validation, backtest, rentabilité historique)
3. **Paper = test signal** → valider signal AVANT chercher rentabilité
4. **Coûts estimés affichés** → utilisateur VOIT le vrai impact (0.3% pour ARB)

### Impact Actuel
- ARB avec R/R 1:3.67 : Trading OK
- AR avec R/R 0.50 : Trading BLOQUÉ (mais pourquoi?)
- UNI avec R/R 0.35 : Trading BLOQUÉ (mais pourquoi?)

**Hypothèse:** Autres blockers (grade SCALP_REJECT, score faible, side=NONE) les bloquent, pas R/R directement.

---

## 3. POURQUOI R/R FAIBLE N'EST PAS BLOQUÉ ACTUELLEMENT

### Raison Architecturale
```
Phase 1 (Paper): Valider signal + test coûts + observer performance
Phase 3B (Edge): Valider rentabilité historique + Kelly + sizing
```

**R/R faible seul ne bloque PAS** car:
- R/R est une métrique locale (ce trade) pas un indicateur d'edge
- Un trade avec R/R 0.50 peut être profitable si:
  - Taux de gain = 80%+ (moyenne 10 gains pour 2 pertes)
  - Mais cela = Phase 3B (backtest + historique)
- Phase 1 dit: "Signal semble bon? Teste-le et observe"

### Problème Observé
Utilisateur s'attend: "R/R < 1.0 = dangereux = bloquer"  
Système dit: "R/R faible = signal peut marcher = test en Paper"

**Risque:** Utilisateur teste en Paper, perd 2-3 trades, frustration.

---

## 4. RECOMMANDATION: TROIS OPTIONS

### OPTION A: Blocage Strict (R/R minimum = 1.0)

**Règle Proposée:**
```
paper_allowed = false  SI  (rr_ratio < 1.0 ET grade dans A+/A/B)
watchlist_allowed = true  (peut toujours observer)
```

**Avantages:**
- ✅ Bloque les trades "déficitaires par design"
- ✅ Cohérent avec notion "rendement doit ≥ risque"
- ✅ Simple à expliquer
- ✅ AR/UNI seraient bloqués de papier

**Inconvénients:**
- ❌ Peut bloquer bons signaux avec taux de gain élevé
- ❌ Élimine trades "petite taille, haute fréquence"
- ❌ Utilisateur ne peut pas tester même en Paper

**Impact Estimé:**
- ARB: Pas d'impact (R/R 1:3.67 > 1.0)
- AR: BLOQUÉ (R/R 0.50 < 1.0) → passe en Watchlist
- UNI: BLOQUÉ (R/R 0.35 < 1.0) → passe en Watchlist
- Screener: -15% à -20% de trades Paper (estimation)

---

### OPTION B: Blocage Agressif (R/R minimum = 1.2)

**Règle Proposée:**
```
paper_allowed = false  SI  (rr_ratio < 1.2)
watchlist_allowed = true
```

**Avantages:**
- ✅ Exige "rendement au moins 20% supérieur au risque"
- ✅ Cohérent avec proverbe trading "Risk 1 to make 2+"
- ✅ Filtre encore plus fort

**Inconvénients:**
- ❌ Très restrictif
- ❌ Élimine beaucoup de bons signaux mid-range
- ❌ Peut frustr utilisateur novice

**Impact Estimé:**
- ARB: OK (R/R 1:3.67 > 1.2) mais marginal
- AR: BLOQUÉ (R/R 0.50 < 1.2)
- UNI: BLOQUÉ (R/R 0.35 < 1.2)
- Screener: -25% à -30% de trades Paper

---

### OPTION C: Warning-Only (Pas de Blocage, Mais Alert)

**Règle Proposée:**
```
paper_allowed = true  (inchangé)
MAIS afficher badge/warning si rr_ratio < 1.0:
  "⚠️ Faible R/R (0.50:1) — Ce signal risque 100 pour ~50 rendement.
   Taux de gain doit être 70%+ pour être rentable. En test Paper."
```

**Avantages:**
- ✅ Aucun blocage
- ✅ Utilisateur informé mais libre de tester
- ✅ Apprend via expérience Paper
- ✅ Pas de perte de signaux

**Inconvénients:**
- ❌ Utilisateur peut ignorer warning
- ❌ Peut tester inefficacement
- ❌ Pas de protection

---

## 5. COMPARAISON IMPACT

| Métrique | Actuel | Option A (RR≥1.0) | Option B (RR≥1.2) | Option C (Warning) |
|----------|--------|------------------|-------------------|-------------------|
| **ARB Testable** | ✅ | ✅ | ✅ | ✅ |
| **AR Testable** | ❌* | ❌ | ❌ | ✅ |
| **UNI Testable** | ❌* | ❌ | ❌ | ✅ |
| **Screener -X%** | Base | -15-20% | -25-30% | 0% |
| **User Freedom** | Oui | Partiel | Faible | Oui |
| **Protection** | Faible | Forte | Très forte | Faible |
| **Complexité Code** | N/A | Faible | Faible | Moyen |
| **Phase 3B Needed** | N/A | Non | Non | Non |
| **Backtest Needed** | N/A | Non | Non | Non |

*AR/UNI bloqués par autres critères (grade SCALP_REJECT, side=NONE), pas R/R

---

## 6. RECOMMANDATION FINALE

### Approche Recommandée: **HYBRID (A + C)**

**Règle:**
```
1. Blocage Léger (Option A): paper_allowed = false SI rr_ratio < 1.0
   → AR, UNI passent en Watchlist (pas testables en Paper)
   
2. Warning (Option C): SI rr_ratio < 1.2 MAIS ≥ 1.0
   → Afficher warning: "⚠️ R/R faible (1:1.1) — Taux de gain critique."
   → Utilisateur peut tester mais conscient du risque
```

### Justification
- ✅ **Équilibre:** Bloque cas extrêmes (0.5, 0.35) sans éliminer 1.0-1.2
- ✅ **Pédagogie:** Apprend utilisateur concepts R/R sans frustration
- ✅ **Sécurité:** Réduit tests inefficaces
- ✅ **Simplicité:** Pas de Phase 3B, pas de backtest, pas de Kelly
- ✅ **UX:** Clear feedback (blocage vs warning)

### Implémentation Estimée
- Ajouter vérification R/R dans logique `paper_allowed` (~5 lignes)
- Ajouter UI warning block si 1.0 ≤ R/R < 1.2 (~20 lignes UI)
- **Effort:** Très faible (1 fichier: strategy.py + UI update)
- **Impact:** -10-15% screener size (acceptable)

---

## 7. ALTERNATIVE: STATU QUO + DOCUMENTATION

**Si option hybrid trop complexe:**

Garder système actuel MAIS ajouter documentation claire:
```
"R/R faible (< 1.0) en Paper est intentionnel:
 Phase 1 teste signal, pas rentabilité.
 Pour rentabilité: activez Phase 3B et backtest (Phase 3B — futur)."
```

**Avantage:** Zéro code  
**Inconvénient:** Utilisateur doit lire doc

---

## 8. DEMANDE D'APPROBATION

Avant codage, j'attends validation sur:

1. **Approche choisie:** A / B / C / Hybrid / Statu Quo?
2. **Seuil R/R:** 1.0? 1.2? Autre?
3. **Warning UI:** Afficher si R/R < 1.0 ou < 1.2?
4. **Timing:** Immédiat ou après clôture autres bugs?
5. **Backlog Phase 3B:** Confirmé pour futur?

---

**Status:** 📋 Proposition prête pour validation utilisateur.  
**Code:** Aucun code écrit (analysis only).  
**Phase 3B:** Non activée.  
**Backtest:** Non activé.
