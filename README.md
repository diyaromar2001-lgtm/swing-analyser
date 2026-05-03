# Swing Analyser

Swing Analyser est un assistant de décision pour swing trading avec deux univers séparés :
- Actions
- Crypto

L'objectif est de filtrer fortement les opportunités, de conserver une hiérarchie de décision prudente, et de n'autoriser des trades que lorsqu'un contexte de marché et un edge historique sont suffisamment robustes.

## URLs officielles

- Frontend officiel : [https://swing-analyser-kappa.vercel.app](https://swing-analyser-kappa.vercel.app)
- Backend officiel : [https://swing-analyser-production.up.railway.app](https://swing-analyser-production.up.railway.app)

## Modules principaux

- `Command Center` Actions
- `Advanced View` Actions
- `Strategy Lab` Actions
- `Backtest` Actions
- `Trade Plan` Actions
- `Trade Journal`
- `Command Center` Crypto
- `Advanced View` Crypto
- `Strategy Lab` Crypto
- `Backtest` Crypto
- `Trade Plan` Crypto
- `Data Freshness Panel`
- `Edge Engine` Actions 24m / 36m
- `Market Regime Engine` Actions
- `Crypto Regime Engine`

## Fonctionnement général

### Actions

Le flux Actions repose sur :
- chargement OHLCV
- calcul des indicateurs
- filtres hard
- scoring du setup
- régime de marché
- fit stratégique
- edge historique par ticker
- décision finale prudente

Le `Command Center` Actions reste basé sur l'horizon Edge officiel `24m`.
Le mode `36m` est réservé à l'analyse avancée.

### Crypto

Le module Crypto est séparé du module Actions.
Il dispose de :
- son univers
- son régime
- son screener
- son edge
- ses plans de trade

En régime défensif (`CRYPTO_BEAR`, `CRYPTO_NO_TRADE`, `CRYPTO_HIGH_VOLATILITY`), l'app reste en mode surveillance et ne propose pas d'achat.

## Statuts à connaître

- `Actions OK` : caches Actions suffisamment chauds pour afficher les résultats du screener.
- `Crypto OK` : caches Crypto suffisants pour afficher screener, prix et régime fiables.
- `Edge coverage` : couverture du cache edge historique par ticker ou par symbole.
- `REJECT` : setup technique insuffisant.
- `NO_EDGE` : aucune validation historique suffisante.
- `OVERFITTED` : edge suspect, à éviter.
- `CRYPTO_BEAR` / `CRYPTO_NO_TRADE` : régime crypto défensif, surveillance uniquement.

## Limites actuelles

- Les caches du backend Railway sont en mémoire.
- Après un redeploy, un warmup admin est nécessaire.
- L'Edge Actions ne se recalcule pas automatiquement en continu.
- Le module Crypto reste défensif si le régime ou les données BTC/ETH sont incomplets.

## Déploiement

Voir [DEPLOYMENT.md](./DEPLOYMENT.md) pour la procédure après chaque redeploy Railway et le workflow Admin.
