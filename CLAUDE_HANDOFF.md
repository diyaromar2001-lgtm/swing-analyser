# CLAUDE_HANDOFF.md

## 1. Résumé global du projet

**Projet**: Swing Analyser / Analyse Swing  
**Repo**: https://github.com/diyaromar2001-lgtm/swing-analyser  
**Branche**: `main`  
**Frontend officiel**: https://swing-analyser-kappa.vercel.app  
**Backend officiel**: https://swing-analyser-production.up.railway.app  
**Stack**: backend Python/FastAPI, frontend Next.js/TypeScript, backend Railway, frontend Vercel

L’application est un **scanner swing trading** Actions + Crypto. Elle sert à:
- filtrer les setups,
- expliquer pourquoi un trade est ou n’est pas autorisé,
- garder une vue quotidienne via le Command Center,
- fournir une vue détaillée via Advanced View,
- documenter les setups via le Trade Journal,
- réchauffer les caches via l’Admin Panel.

Ce n’est **pas** un bot de trading automatique.
Elle ne doit **jamais** exécuter un trade à la place de l’utilisateur.
Elle sert à **surveiller, filtrer, documenter et éviter les mauvais trades**.

### Modules principaux
- **Command Center**: vue quotidienne, décision opérationnelle.
- **Advanced View**: vue d’analyse détaillée.
- **Trade Plan**: vérifie entrée / stop / TP / autorisation.
- **Trade Journal**: watchlist / planned / open / closed.
- **Admin Panel**: clé admin, warmup, cache status.
- **Edge v1**: moteur officiel d’autorisation.
- **Edge v2 Actions**: recherche uniquement.
- **Crypto Research V2**: recherche uniquement.
- **Warmup / cache**: mémoire + persistance best-effort.

---

## 2. Règles de sécurité à ne jamais casser

### Règles absolues
- Ne jamais rendre **Edge v2** décisionnel.
- Ne jamais rendre **Crypto Research V2** décisionnel.
- Ne jamais modifier automatiquement `BUY / WAIT / SKIP` via research.
- Ne jamais modifier `tradable` via research.
- Ne jamais modifier `final_decision` via research.
- Ne jamais modifier `ticker_edge_status` v1 via research.
- Ne jamais permettre à un trade `WATCHLIST` de devenir `OPEN`.
- Ne jamais permettre à un trade `SKIP / WAIT / NO_EDGE / OVERFITTED` de devenir `OPEN`.
- Ne jamais autoriser un trade crypto en `CRYPTO_BEAR / CRYPTO_NO_TRADE / CRYPTO_HIGH_VOLATILITY`.
- Ne jamais appeler `clear-cache` dans le flux normal.
- Ne jamais remplacer un cache non vide par `[]`.
- Ne jamais exposer la clé admin en clair dans les logs.

### Autorisation réelle d’un trade
Un trade réel n’est possible que si:
- Edge v1 est validé,
- `final_decision` est `BUY / BUY NEAR ENTRY / BUY NOW`,
- `tradable = true`,
- `risk filters OK`,
- pas d’overfit,
- Trade Plan affiche `Autorisation d’exécution : Autorisé`.

---

## 3. Historique des grandes étapes réalisées

### Sécurité admin
- Ajout de `ADMIN_API_KEY`.
- Protection par header `X-Admin-Key`.
- Endpoints protégés:
  - `clear-cache`
  - `warmup`
  - `optimizer`
  - `strategy lab`
  - `backtest`
  - `edge compute`
  - `crypto debug`
- Si clé absente en local: warning seulement.
- Si clé définie en prod: `401` si header absent/faux.

### Admin Panel
- Ajout du bouton Admin.
- Stockage de la clé dans `localStorage` sous `admin_api_key`.
- Test de clé via `/api/admin/ping`.
- Warmup Actions batch.
- Warmup Crypto.
- Vérifier cache.
- Danger zone séparée.

### Cache / warmup
- Ajout de `/api/cache-status?scope=all`.
- Ajout de `/api/warmup?scope=actions|crypto`.
- Ajout du warmup Actions par batch.
- Ajout de `/api/warmup/actions-missing`.
- Ajout de `/api/warmup/status?scope=all`.
- Ajout de la persistance best-effort via `backend/cache_persistence.py`.
- Correction des `500/502` Railway sur plusieurs chemins de warmup.
- Warmup Actions rendu progressif et chunké.
- Warmup Crypto rendu safe.
- `crypto/regime` ne timeout plus et renvoie un fallback degraded/cached quand nécessaire.

### Crypto null states
- Correction des `toFixed/null`.
- `formatCryptoPrice()` retourne `—`.
- BTC/ETH absents => pas de `$0`.
- Warning si BTC/ETH indisponibles.
- `NO TRADE CRYPTO` forcé si contexte incomplet.

### Trade Plan safety
- Bouton “prendre trade” verrouillé.
- Actions: autorisé seulement si edge validé + BUY + setup A/A+ + pas overfit + risk OK.
- Crypto: bloqué si régime défensif, edge non validé, overfit, `SKIP/WAIT`.
- Ajout du bloc `Autorisation d’exécution`.
- Ajout du bloc `Ce qu’il manque pour devenir autorisé`.

### Trade Journal
- Backend SQLite dédié dans `backend/trade_journal.py`.
- Endpoints journal protégés par admin key.
- Statuts: `WATCHLIST / PLANNED / OPEN / CLOSED`.
- `WATCHLIST` ne peut pas devenir `OPEN`.
- Backend refuse l’ouverture si non autorisé.
- Ajout des notes visibles dans la table.
- Ajout du Portfolio Risk.

### Edge v2 Actions
- Audits montrant que le ticker-level Edge v1 était trop strict.
- Edge v2 research basé sur:
  - Strategy Portfolio Edge
  - Sector Edge
  - Regime Edge
  - Ticker Edge
  - Setup Quality
- Endpoint `/api/research/edge-v2`.
- Correction des payloads JSON `NaN/inf`.
- Toggle Edge v1 / Edge v2 Research dans Advanced View Actions.
- Edge v2 reste research-only.
- Correction d’un refresh loop Edge v2.

### Crypto Research V2
- Audit crypto par stratégie.
- Audit crypto par symbole.
- Panneau Crypto Research V2 dans Crypto Advanced.
- Core Watchlist: BTC, ETH, SOL, BNB, LINK.
- Promising Research: AVAX, ARB, DOGE, INJ.
- Speculative: TON, UNI, ICP, DOT, ADA, NEAR, XRP, LTC, BCH, SUI, ATOM, FIL, APT.
- Avoid / Blocked: OP, SEI, POL.
- Crypto Research V2 reste research-only.
- Carte Crypto Research V2 dans CryptoTradePlan.

### UI simplification
- Barre du haut simplifiée.
- Boutons visibles:
  - Admin
  - Actions
  - Crypto
  - Command
  - Advanced
  - Trades
  - Standard
  - Tableau
  - Edge 24m
  - Edge v1
  - Rafraîchir
- Menu Recherche:
  - Conservative
  - Signaux
  - Tracking
  - Backtest
  - Strategy Lab
  - Edge 36m
  - Edge v2 Research
  - API
  - Edge ?

---

## 4. Commits importants

Les commits récents importants vus dans `git log --oneline -30`:

- `c601061` `fix: harden remaining warmup crashes`
- `1d0e7ef` `fix: surface trade journal notes in table`
- `e6ba767` `fix: make actions warmup progressive`
- `40dfff8` `fix: stabilize prod warmup cache persistence`
- `b15a03e` `feat: simplify top navigation menus`
- `744554e` `feat: explain trade readiness in plans`
- `2313cff` `feat: polish crypto research v2 advanced ui`
- `4b1fa1b` `feat: add missing actions warmup path`
- `2258ccd` `fix: stabilize advanced view and crypto messaging`
- `73831da` `fix: clarify cache status criteria in admin ui`
- `eb8be2a` `fix: sanitize edge v2 research payload`
- `0493d7b` `feat: add edge v2 research view`
- `d29ec88` `fix: block unsafe journal opens`
- `1817557` `feat: add persistent trade journal and portfolio risk`
- `bb2294e` `feat: add daily trading checklist to command center`
- `c52271d` `fix: remove dangerous recalc from main ui`
- `3228fd2` `fix: make cache repair safe in ui`
- `91fa60f` `fix: prevent dashboard loading loop`
- `c155bb6` `fix: lock trade plan execution ctas`
- `6bb40c1` `fix: send admin headers for protected ui actions`
- `f044d92` `feat: add admin warmup panel`
- `b425275` `fix: refresh crypto regime warmup cache`
- `abdf4c0` `fix: unify screener cache keys`
- `425d109` `feat: batch warmup actions caches`
- `e07afc9` `fix: force actions warmup to bypass empty fast cache`
- `1a30871` `feat: add admin warmup and cache diagnostics`
- `b731835` `fix: secure admin endpoints and harden crypto null states`
- `fca5eac` `docs: clarify urls and deployment workflow`
- `311bcb7` `docs: define official deployment url`

---

## 5. État actuel validé en prod

### Warmup Actions
Dernier test valide:
- batch 1 OK
- batch 2 OK
- batch 3 OK
- batch 4 OK
- pas de 500
- pas de 502
- pas de restart

État observé:
- `ohlcv_cache_count = 199`
- `price_cache_count = 199`
- `screener_results_count = 107`
- `regime_cache_status = warm`

Conclusion:
- Actions OK atteint.
- Si Actions OK, ne plus relancer le warmup.
- Ne pas forcer batch 5 si batch 4 suffit.
- Ne pas lancer `actions-missing` sauf si nécessaire.

### Warmup Crypto
Dernier test valide:
- `POST /api/warmup?scope=crypto&include_edge=false` OK
- `crypto_ohlcv_cache_count = 24`
- `crypto_ohlcv_4h_cache_count = 24`
- `crypto_price_cache_count = 24`
- `crypto_screener_cache_count = 1`
- `crypto_regime_cache_status = warm`
- `/api/crypto/regime` répond OK avec `data_status = OK`
- régime live: `CRYPTO_BEAR`

Conclusion:
- Crypto = surveillance, pas trade.

### actions-missing
Dernier test valide:
- `POST /api/warmup/actions-missing?limit=20` OK
- traite progressivement
- ne crash plus
- ne doit pas être utilisé si Actions OK

### Journal
- Watchlist fonctionne.
- APT / INJ ajoutés en watchlist.
- Notes maintenant visibles dans la table après fix.
- WATCHLIST ne peut pas devenir OPEN.

---

## 6. Endpoints importants

### Publics
- `GET /api/screener?strategy=standard&fast=true`
- `GET /api/crypto/screener?fast=true`
- `GET /api/regime-engine`
- `GET /api/crypto/regime`
- `GET /api/prices`
- `GET /api/crypto/prices`
- `GET /api/cache-status?scope=all`
- `GET /api/data-freshness?scope=actions|crypto`
- `GET /api/warmup/status?scope=all`
- `GET /api/research/edge-v2`

### Admin protégés
- `GET /api/admin/ping`
- `POST /api/warmup?scope=actions&batch=N&batch_size=50&include_edge=false`
- `POST /api/warmup/actions-missing?limit=20`
- `POST /api/warmup?scope=crypto&include_edge=false`
- `POST /api/clear-cache`
- `POST /api/strategy-edge/compute`
- `POST /api/crypto/edge/compute`
- `GET /api/optimizer`
- `GET /api/strategy-lab`
- `GET /api/backtest`
- `GET /api/crypto/backtest`
- Trade journal endpoints

---

## 7. Variables / secrets

- `ADMIN_API_KEY` côté Railway.
- Header utilisé: `X-Admin-Key`.
- Frontend stocke la clé dans `localStorage` sous `admin_api_key`.
- La clé admin a été mentionnée accidentellement dans une conversation: il est recommandé de la changer côté Railway et de la régénérer côté navigateur.
- Ne jamais logguer la clé.

---

## 8. Routine d’utilisation actuelle

### Début de session
1. Ouvrir l’app.
2. Aller dans Admin et tester la clé.
3. Vérifier le cache.
4. Si Actions OK, ne pas relancer le warmup.
5. Si Actions à vérifier:
   - batch 1
   - batch 2
   - batch 3
   - vérifier cache
   - batch 4 si nécessaire
   - arrêter dès Actions OK.
6. Crypto:
   - warmup seulement si cache missing ou dégradé,
   - si `CRYPTO_BEAR`, observation uniquement.

### Trading
1. Actions -> Command Center.
2. Regarder “Trade autorisé aujourd’hui”.
3. Ouvrir Trade Plan.
4. Vérifier “Autorisation d’exécution”.
5. Si non autorisé: watchlist seulement.
6. Si autorisé: préparer dans le journal.
7. Ne jamais forcer un trade.

### Crypto
- Crypto Research V2 = surveillance.
- `CRYPTO_BEAR` = pas d’achat.
- BTC/ETH = régime.
- SOL/BNB/LINK = alts core à surveiller.
- AVAX/ARB/DOGE/INJ = research prometteur.
- OP/SEI/POL = avoid/blocked.

---

## 9. Bugs restants / limites

### Restants / à surveiller
- La persistance Railway reste best-effort et dépend du stockage réellement conservé par l’hébergeur.
- Si Railway redémarre sans volume persistant, les caches peuvent repartir froids.
- `market_context_cache_status = stale` n’est pas bloquant actuellement.
- `edge_cache_coverage` Actions peut rester à 0 si Edge n’est pas recalculé; ce n’est pas bloquant pour le cache OK.
- Crypto live est `CRYPTO_BEAR`, donc pas de signaux tradables attendus.
- Le flux Journal open/close complet doit encore être testé avec un vrai trade autorisé quand il y en aura un.
- Backtest / Strategy Lab restent à tester plus profondément, mais ne font pas partie du flux quotidien.

### À ne pas corriger maintenant sauf bug bloquant
- Ne pas refaire les stratégies.
- Ne pas assouplir les filtres sans raison forte.
- Ne pas rendre research décisionnel.
- Ne pas modifier le Command Center.

---

## 10. Prochaine roadmap recommandée

### Court terme
- Changer `ADMIN_API_KEY` car elle a été exposée accidentellement dans une conversation.
- Vérifier visuellement Trade Journal notes après déploiement.
- Ne plus toucher au backend avant lundi sauf bug bloquant.
- Utiliser l’app en conditions réelles et noter:
  - quels setups sont bloqués,
  - pourquoi,
  - lesquels évoluent bien,
  - si le système est trop strict ou simplement prudent.

### Cette semaine
- Tester le flux complet du journal:
  - Watchlist -> Planned -> Open -> Close
  - PnL
  - notes
  - risque portefeuille
- Améliorer l’affichage du journal si nécessaire.
- Vérifier la persistance après un vrai restart Railway.

### Plus tard
- Revoir les stratégies seulement après plusieurs jours d’observation.
- Étudier Edge v2 comme score d’aide uniquement, jamais sans validation OOS.
- Étudier Crypto 4H plus souple, mais toujours research-only.
- Ajouter éventuellement un job Railway/cron warmup si nécessaire.

---

## 11. Instructions pour Claude Code

1. Commence toujours par lire ce document.
2. Lance `git status`.
3. Lance `git log --oneline -30`.
4. Ne modifie pas les stratégies sans demande explicite.
5. Ne touche pas aux règles de sécurité.
6. Si une demande est ambiguë, privilégie la sécurité et la stabilité.
7. Avant tout changement, identifie si c’est UI, backend, stratégie ou sécurité.
8. Toujours faire `npm run build` si le frontend est modifié.
9. Toujours faire `python -m py_compile ...` si le backend est modifié.
10. Toujours résumer:
    - fichiers modifiés,
    - tests faits,
    - commit.

