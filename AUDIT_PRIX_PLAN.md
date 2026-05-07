# AUDIT COMPLET PRIX ET DONNÉES DE MARCHÉ
**Status:** PLAN D'AUDIT - EN COURS D'EXÉCUTION  
**Date:** 2026-05-07  
**Scope:** Actions Swing + Crypto Swing + Crypto Scalp + TradePlan + Journal + Performance

---

## PHASE 1: CARTOGRAPHIE DES SOURCES DE PRIX

### Module A: ACTIONS SWING

**Fichiers concernés:**
- main.py (endpoints /api/actions/*)
- strategy.py (calcul des scores)
- indicators.py (calcul des indicateurs)
- tickers.py (liste des actions)
- ticker_edge.py (cache edge)

**À vérifier:**

#### A1. Prix affiché (Frontend)
- [ ] Source du prix affiché dans l'UI Actions Swing
- [ ] Provider (yfinance? CoinGecko? autre?)
- [ ] Cache utilisé
- [ ] Timestamp
- [ ] Marché ouvert/fermé
- [ ] Prix delayed ou real-time
- [ ] Endpoint API correspondant

#### A2. Prix utilisé pour calcul des scores
- [ ] RSI, MACD, trend, momentum
- [ ] Support/résistance
- [ ] Volume
- [ ] Prix historique ou snapshot
- [ ] Bougies daily ou intraday
- [ ] Formules exactes

#### A3. Prix utilisé pour entry/SL/TP
- [ ] Source exacte
- [ ] Provider
- [ ] Timestamp
- [ ] Comment sont calculés les niveaux
- [ ] Pris en account du spread/slippage

#### A4. Caches Actions
- [ ] Nom des caches
- [ ] TTL
- [ ] Contenu
- [ ] Persistant ou mémoire
- [ ] Utilisé par quel endpoint

---

### Module B: CRYPTO SWING

**Fichiers concernés:**
- crypto_service.py
- crypto_data.py
- crypto_regime_engine.py
- crypto_edge.py

**À vérifier:**

#### B1. Prix affiché
- [ ] Source du prix affiché
- [ ] Provider (Binance? CoinGecko? Coinbase?)
- [ ] Cache
- [ ] Timestamp
- [ ] Snapshot ou daily close
- [ ] Endpoint API

#### B2. Prix utilisé pour scores
- [ ] Utilise snapshot ou daily close?
- [ ] Indicateurs calculés sur quel prix
- [ ] Bougies utilisées (daily? 4h?)
- [ ] Provider principal
- [ ] Fallback provider

#### B3. Prix utilisé pour entry/SL/TP
- [ ] Source
- [ ] Provider
- [ ] Calcul ATR sur quel prix
- [ ] Calcul trend sur quel prix

#### B4. Caches Crypto Swing
- [ ] _ohlcv_daily_cache
- [ ] _ohlcv_4h_cache
- [ ] _price_cache
- [ ] Régime cache
- [ ] Edge cache

---

### Module C: CRYPTO SCALP

**Fichiers concernés:**
- crypto_scalp_service.py
- crypto_scalp_score.py
- crypto_data.py

**À vérifier:**

#### C1. Prix affiché
- [ ] Displayed_price source
- [ ] Snapshot_price vs intraday_last_close
- [ ] price_source variable
- [ ] price_timestamp
- [ ] price_suspect
- [ ] price_difference_pct

#### C2. Prix utilisé pour scores
- [ ] ATR calculé sur quel interval (5m? 1m? 15m?)
- [ ] RSI calculé sur quel interval
- [ ] Support/résistance sur quel interval
- [ ] Provider des données intraday
- [ ] Fallback chain

#### C3. Prix utilisé pour entry/SL/TP
- [ ] Basé sur snapshot ou intraday
- [ ] Comme calculés les niveaux
- [ ] Calcul du spread/slippage

#### C4. Caches Crypto Scalp
- [ ] _ohlcv_1m_cache
- [ ] _ohlcv_5m_cache
- [ ] _ohlcv_15m_cache
- [ ] TTL de chaque cache
- [ ] Provider utilisé

---

### Module D: TRADEPLAN / JOURNAL / PERFORMANCE

**Fichiers concernés:**
- trade_journal.py
- crypto_paper_fill_simulator.py
- crypto_paper_metrics.py

**À vérifier:**

#### D1. Prix au moment de création
- [ ] Quel prix utilisé pour entry
- [ ] Stocké dans la BD ou recalculé
- [ ] Provider à ce moment-là
- [ ] Timestamp

#### D2. Prix à la fermeture
- [ ] Quel prix utilisé
- [ ] Manuel ou automatique
- [ ] Affecte les trades anciens si prix change

#### D3. PnL et Performance
- [ ] Basé sur prix stockés ou prix live
- [ ] Formules exactes
- [ ] Impact d'un prix stale

---

## PHASE 2: IDENTIFIER LES PROVIDERS

### Providers Utilisés

#### Binance
- [ ] Utilisé pour: Actions / Crypto / Scalp
- [ ] Type: OHLCV daily/intraday / snapshot
- [ ] Fonctionne en local: OUI
- [ ] Fonctionne sur Railway: NON (HTTP 451)
- [ ] Rate limit: ?
- [ ] Paires: SYMBOLUSDT (pour crypto)
- [ ] Problèmes connus: HTTP 451 blocage

#### CoinGecko
- [ ] Utilisé pour: Prix crypto + marché cap
- [ ] Type: Prix actuel + données fondamentales
- [ ] Fonctionne: OUI (API public)
- [ ] Rate limit: 50 appels/minute
- [ ] Mapping symbole: coingecko_id

#### CoinBase
- [ ] Utilisé pour: Fallback intraday 5m
- [ ] Type: Candles 5m
- [ ] Fonctionne: OUI
- [ ] Pairs: SYMBOL-USD
- [ ] Problème MKR: Retourne perpetuals (1300) pas spot (1867)

#### Kraken
- [ ] Utilisé pour: Fallback intraday 5m
- [ ] Type: Candles 5m
- [ ] Paires mapping: XXBTZUSD, XETHZUSD, SOL...
- [ ] Problèmes: SOL skipped par design

#### OKX
- [ ] Utilisé pour: Fallback intraday 5m
- [ ] Type: Candles 5m
- [ ] Pairs: SYMBOL-USD
- [ ] Données limitées pour certains symboles

#### Yahoo Finance / yfinance
- [ ] Utilisé pour: Actions pricing
- [ ] Type: OHLCV daily
- [ ] Marché ouvert/fermé: Gère
- [ ] Delayed pricing: Possible

---

## PHASE 3: VÉRIFIER LES CACHES

### Cache Structure

```
Name                  | TTL    | Content          | Module       | Risk
----------------------|--------|------------------|--------------|----------
_price_cache          | 60s    | Snapshot prices  | crypto_data  | Stale >60s
_ohlcv_daily_cache    | 3600s  | Daily candles    | crypto_data  | Stale >1h
_ohlcv_4h_cache       | 900s   | 4h candles       | crypto_data  | Stale >15m
_ohlcv_1m_cache       | 300s   | 1m candles       | crypto_data  | Stale >5m
_ohlcv_5m_cache       | 600s   | 5m candles       | crypto_data  | Stale >10m
_ohlcv_15m_cache      | 900s   | 15m candles      | crypto_data  | Stale >15m
_markets_cache        | 300s   | Market data      | crypto_data  | Stale >5m
_global_cache         | 900s   | Global data      | crypto_data  | Stale >15m
_crypto_regime_cache  | ?      | Regime calcs     | regime_eng   | ?
_crypto_edge_cache    | ?      | Edge calcs       | edge         | ?
ticker_edge_cache     | ?      | Actions edge     | ticker_edge  | ?
```

### Questions Caches
- [ ] Tous les caches sont en mémoire (pas persistant)
- [ ] TTL cohérents avec les données affichées
- [ ] Risque stale price après Railway redeploy
- [ ] Nombre d'éléments en cache actuellement
- [ ] Overflow risk si trop de symboles

---

## PHASE 4: TESTER LES PRICES RÉELLES

### Cryptos à Tester

Test Set:
1. BTC - Grande cap, tous providers
2. ETH - Grande cap, tous providers
3. SOL - Cap moyenne, providers variés
4. TON - Cas suspect, disparité 32%
5. MKR - Cas suspect, Coinbase perpetuals
6. BNB - Grande cap stablecoin-like
7. XRP - Cap moyenne
8. AVAX - Cap moyenne
9. LINK - Oracle, important
10. AAVE - DeFi, important

Pour chacun:
- [ ] Prix affiché dans Crypto Scalp
- [ ] Prix API retourné
- [ ] snapshot_price
- [ ] intraday_last_close
- [ ] price_source
- [ ] price_suspect
- [ ] Provider exact utilisé
- [ ] Timestamp
- [ ] CoinGecko ref price
- [ ] Coinbase 5m close
- [ ] Kraken 5m close
- [ ] OKX 5m close
- [ ] Écart %
- [ ] Verdict

---

### Actions à Tester

À définir selon ce qui est dans le screener.

Test Set suggéré:
- 5 actions marché ouvert (US)
- 3 actions marché fermé/delayed (US)
- 2 actions européennes
- 3 actions du screener actuel

Pour chacun:
- [ ] Prix affiché dans Actions Swing
- [ ] Provider
- [ ] Timestamp
- [ ] Marché ouvert/fermé
- [ ] Delayed ou real-time
- [ ] Comparaison Yahoo Finance / Broker
- [ ] Écart %

---

## PHASE 5: DIAGNOSTIC TON ET MKR

### TON Deep Dive

- [ ] Snapshot Railway: 2.424
- [ ] Intraday Railway: 1.837
- [ ] Source intraday exacte
- [ ] Provider mapping
- [ ] Dernière bougie 5m timestamp
- [ ] 5 dernières bougies closes
- [ ] CoinGecko: 2.43
- [ ] Coinbase: 2.434
- [ ] Kraken: 2.429
- [ ] OKX: 2.40
- [ ] Comparison TradingView
- [ ] Verdict: snapshot correct ou intraday faux

### MKR Deep Dive

- [ ] Snapshot Railway: 1777.53
- [ ] Intraday Railway: 1347.21
- [ ] Source intraday: Coinbase perpetuals?
- [ ] Provider mapping: MKR-USD correct?
- [ ] CoinGecko: 1866.96 (spot réel)
- [ ] Coinbase: 1300.86 (perpetuals?)
- [ ] Kraken: ERROR
- [ ] OKX: ERROR
- [ ] Coinbase dernier close 5m
- [ ] Coinbase 5 derniers closes
- [ ] Verdict: Coinbase MKR-USD = perpetuals ou stale

---

## PHASE 6: VÉRIFIER IMPACT INDICATEURS

### Questions

- [ ] Indicateurs calculés sur snapshot ou OHLCV?
- [ ] Si snapshot incorrect, indicateurs aussi faux?
- [ ] Ou indicateurs utilisent source différente?
- [ ] Entry/SL/TP basés sur indicateurs ou direct prix?
- [ ] Impact ATR si prix stale?
- [ ] Impact RSI si prix stale?
- [ ] Impact support/resistance?

---

## PHASE 7: COHÉRENCE ENTRE MODULES

### Pour un symbole crypto donné (par ex. BTC)

Comparer:
- [ ] Prix Crypto Swing vs Crypto Scalp
- [ ] Prix Crypto Swing vs Analysis endpoint
- [ ] Prix TradePlan création vs prix current
- [ ] Prix Journal trade entry
- [ ] Prix Performance PnL calc

Résultat attendu:
- [ ] Tous les mêmes (cohérent)
- [ ] Ou différent providers (incohérent à documenter)

---

## PHASE 8: ARCHITECTURE CIBLE (SANS CODER)

### Schéma

À définir après audit:
- Qui utilise quel provider
- Qui utilise quel cache
- Quel fallback où
- Comment gérer divergence
- Comment marquer suspect
- Comment bloquer/avertir

---

## PHASE 9: PLAN CORRECTION PROGRESSIF

### Étapes

1. Audit complet (cette phase)
2. Afficher source/timestamp/suspect dans API (minimal code)
3. Corriger mappings problématiques
4. Choisir provider/fallback par symbole
5. Bloquer/avertir si divergence trop grande
6. Seulement après validation: ajuster Paper/Watchlist

---

## CHECKLIST EXÉCUTION

### Maintenant (Phase Audit)

- [ ] Lire crypto_data.py: sources, providers, fallback chain
- [ ] Lire crypto_service.py: Crypto Swing price logic
- [ ] Lire crypto_scalp_service.py: Crypto Scalp price logic
- [ ] Lire trade_journal.py: Stored prices logic
- [ ] Lire indicators.py: Comment les indicateurs utilisent les prix
- [ ] Vérifier yfinance pour Actions
- [ ] Créer script de test prices réelles
- [ ] Tester 10 cryptos + 10 actions
- [ ] Documenter TON et MKR en détail
- [ ] Rédiger rapport complet

### Après Audit (Futur)

- [ ] Validation utilisateur du rapport
- [ ] Décision sur correction
- [ ] Plan implémentation progressif
- [ ] Tests avant production

---

## SÉCURITÉ PENDANT L'AUDIT

✅ Aucun code modifié  
✅ Aucune correction directe  
✅ Lecture seule sur fichiers  
✅ Tests additionnels uniquement  
✅ Aucun Real trading  
✅ Aucun levier  
✅ Actions/Crypto Swing/Scalp protégés  

---

**Status:** Plan d'audit créé  
**Prochaine étape:** Exécution Phase 1-9
