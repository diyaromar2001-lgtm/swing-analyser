# Deployment

## URLs officielles

- Frontend officiel : [https://swing-analyser-kappa.vercel.app](https://swing-analyser-kappa.vercel.app)
- Backend officiel : [https://swing-analyser-production.up.railway.app](https://swing-analyser-production.up.railway.app)
- GitHub repository : [https://github.com/diyaromar2001-lgtm/swing-analyser](https://github.com/diyaromar2001-lgtm/swing-analyser)
- Branche de production : `main`

## Ce qu'il faut vérifier après chaque déploiement Railway

1. Ouvrir le panneau `Admin` dans le frontend officiel.
2. Tester la clé admin avec le bouton `Tester la clé`.
3. Lancer `Warmup Actions complet 5 batchs`.
4. Lancer `Warmup Crypto`.
5. Cliquer `Vérifier cache`.
6. Attendre l'état :
   - `Actions OK`
   - `Crypto OK`

Le bouton `Admin` est visible dans la barre supérieure du frontend officiel.
La clé est stockée uniquement dans `localStorage` sous `admin_api_key`.

## Statuts à interpréter

### Actions OK

Actions est considéré comme prêt lorsque les caches sont suffisamment chauds, typiquement :
- `ohlcv_cache_count > 150`
- `price_cache_count > 150`
- `screener_results_count > 0`

### Crypto OK

Crypto est considéré comme prêt lorsque :
- `crypto_price_cache_count > 0`
- `crypto_screener_cache_count > 0`
- `crypto_regime_cache_status = warm`

### Edge coverage

La couverture Edge indique la part de l'univers pour laquelle un edge historique est disponible.
- Sur Actions, le `Command Center` officiel reste basé sur l'horizon `24m`.
- Le `36m` est réservé à l'analyse avancée.

### Régimes défensifs

- `CRYPTO_BEAR`
- `CRYPTO_NO_TRADE`
- `CRYPTO_HIGH_VOLATILITY`

Dans ces cas, Crypto doit être lu comme une watchlist technique, pas comme une invitation à acheter.

### Statuts de setup et edge

- `REJECT` : setup technique insuffisant
- `NO_EDGE` : edge historique absent ou trop faible
- `OVERFITTED` : edge suspect, à éviter

## Workflow de warmup recommandé

### Actions

1. `Warmup Actions batch 1`
2. `Warmup Actions batch 2`
3. `Warmup Actions batch 3`
4. `Warmup Actions batch 4`
5. `Warmup Actions batch 5`
6. Optionnellement relancer `Vérifier cache`

### Crypto

1. `Warmup Crypto`
2. `Vérifier cache`
3. Vérifier que `Crypto OK` apparaît bien

## Limites actuelles

- Les caches Railway sont en mémoire.
- Un redeploy peut vider les caches.
- Le warmup admin est nécessaire après redeploy.
- L'Edge Actions ne se recalcule pas automatiquement en continu.
- Crypto reste défensif si les données BTC/ETH ou le régime ne sont pas fiables.

## Ancienne URL Vercel

L'ancienne URL suivante ne doit pas être considérée comme officielle :

- `frontend-seven-snowy-63.vercel.app`

Action recommandée :
1. Ouvrir le projet Vercel qui sert cette URL.
2. Le supprimer, l'archiver, ou configurer une redirection vers l'URL officielle.
3. Garder uniquement [https://swing-analyser-kappa.vercel.app](https://swing-analyser-kappa.vercel.app) comme frontend de référence.

## Notes techniques

- Le frontend utilise des requêtes vers le backend Railway.
- Les décisions de production Actions restent basées sur `24m`.
- Le mode `36m` est une vue d'analyse avancée, pas la source de décision officielle.
