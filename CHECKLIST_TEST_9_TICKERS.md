# CHECKLIST: TESTER LES 9 TICKERS + LLY

**Demande:** Vérification concrète (pas probabilités)  
**Estimation:** 10-15 minutes (incluant test)  
**Status:** 🟢 PRÊT

---

## ✅ AVANT DE COMMENCER

- [ ] Backend accessible sur `http://localhost:8000`
- [ ] Vous avez Python 3.8+
- [ ] Vous avez `requests` library (`pip install requests`)
- [ ] Commit 23f006d est deployed (check: 9 tickers retournés)

---

## 🧪 TEST AUTOMATISÉ (RECOMMANDÉ)

### Step 1: Démarrer Backend

```bash
cd backend
python main.py
```

**Attendre le message:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 2: Lancer le Test

**Dans un autre terminal:**

```bash
cd .. && python test_lly_edge_compute.py
```

**Résultat attendu:**
```
ÉTAPE 1: Récupérer les 9 tickers
  ✅ Response reçue
  
ÉTAPE 2: Calculer Edge pour LLY
  ✅ Response reçue
  
ÉTAPE 3: Vérifier LLY dans le Screener
  ✅ LLY TROUVÉ
  
ÉTAPE 4: Vérifier CL, LIN, HOLX
  CL dans les 9? [OUI/NON]
  ...

RÉSUMÉ
  [Tous les détails]
```

### Step 3: Vérifier les Résultats

**Questions à répondre:**

```
1. Les 9 tickers:
   [Coller la liste ici]

2. LLY status:
   ☐ Dans les 9
   ☐ Pas dans les 9
   ☐ Status: [VALID_EDGE/NO_EDGE/etc]

3. CL status:
   ☐ Dans les 9
   ☐ Pas dans les 9
   ☐ Status: [VALID_EDGE/NO_EDGE/etc]

4. LIN status:
   ☐ Dans les 9
   ☐ Pas dans les 9
   ☐ Status: [VALID_EDGE/NO_EDGE/etc]

5. HOLX status:
   ☐ Dans les 9
   ☐ Pas dans les 9
   ☐ Status: [VALID_EDGE/NO_EDGE/etc]

6. Screener montre LLY changé?
   ☐ OUI (status changed from EDGE_NOT_COMPUTED)
   ☐ NON (still EDGE_NOT_COMPUTED)
   ☐ NOT FOUND

7. Fix fonctionne?
   ☐ OUI (9 ≠ 0, tout ok)
   ☐ NON (bug trouvé)
```

---

## 🖥️ TEST MANUEL (OPTIONNEL)

### Step 1: Ouvrir Trade Plan pour LLY

1. Aller au **Screener**
2. Chercher **LLY**
3. Cliquer sur **LLY** pour ouvrir Trade Plan

### Step 2: Vérifier le Badge

- [ ] Badge visible?
  - Si "◆ EDGE NOT COMPUTED" (bleu) → Continue
  - Si "VALID_EDGE" / "NO_EDGE" / etc → Edge déjà calculé

### Step 3: Observer le Bouton

- [ ] Bouton "💠 Calculer Edge LLY" visible?
  - Si OUI → Conditions remplies ✅
  - Si NON → Admin key manquante?

### Step 4: Cliquer le Bouton

- [ ] Clicker "💠 Calculer Edge LLY"
- [ ] Voir "🔄 Calcul edge…" (loading)?
- [ ] Après ~3 secondes: "✓ Edge calculé pour LLY"?
- [ ] Trade Plan se ferme?

### Step 5: Vérifier le Refresh

1. Recharger Screener (F5)
2. Chercher LLY
3. [ ] Badge a changé?
   - De "◆ EDGE NOT COMPUTED" → "VALID_EDGE" / "NO_EDGE" / etc
   - ✅ OK si changé
   - ⚠️ Problème si toujours EDGE_NOT_COMPUTED

---

## 📊 RÉSUMÉ DES RÉSULTATS

### Si Test Réussit ✅

```
ÉTAPE 1: ✅ 9 tickers retournés
ÉTAPE 2: ✅ LLY calculé avec status réel
ÉTAPE 3: ✅ Screener montre LLY changé
ÉTAPE 4: ✅ CL/LIN/HOLX aussi calculés

CONCLUSION: Fix 23f006d FONCTIONNE ✅
            Bouton LLY FONCTIONNE ✅
            PRÊT PRODUCTION ✅

Action: git commit et push
```

### Si Bug Trouvé ❌

```
[Décrire le bug]
[Étape où ça échoue]
[Message d'erreur]

Action: Analyser et corriger
```

---

## 🔧 TROUBLESHOOTING

### Bug 1: "Connection refused" sur port 8000
**Cause:** Backend pas lancé  
**Fix:** `cd backend && python main.py`

### Bug 2: "ModuleNotFoundError: requests"
**Cause:** Library pas installée  
**Fix:** `pip install requests`

### Bug 3: "AttributeError: _run_screener_impl"
**Cause:** Fix 23f006d pas deployed  
**Fix:** Vérifier commit 23f006d est le HEAD

### Bug 4: Statuts restent "EDGE_NOT_COMPUTED"
**Cause:** Cache pas reread par screener  
**Fix:** Redémarrer backend ou recharger page (F5)

### Bug 5: Admin key invalide
**Cause:** Admin key manquante ou incorrecte  
**Fix:** Vérifier key dans test_lly_edge_compute.py (ligne ~10)

---

## ✨ FIN

**Après le test:**

1. Recopier les résultats ci-dessus
2. Créer un rapport: `RAPPORT_TEST_RESULTS.md`
3. Commit si tout ok:
   ```bash
   git add RAPPORT_FINAL_9_TICKERS_VERIFICATION.md
   git commit -m "Verified: 9 tickers work correctly, LLY compute button ready"
   git push origin main
   ```

---

**Durée estimée:** 10-15 minutes  
**Facilité:** ⭐⭐⭐ (Très simple, juste exécuter le script)  
**Status:** 🟢 PRÊT
