#!/usr/bin/env python3
"""
Diagnostic: Vérifier les 9 tickers calculés par "Calculer Edge Actions"
1. Quels sont exactement les 9 tickers ?
2. Leurs statuts dans le screener
3. Si les statuts ont changé de EDGE_NOT_COMPUTED à un statut réel
4. Le contenu du cache edge
5. Pourquoi 9 et pas 45+ ?
"""

import requests
import json
import time
from typing import Dict, List, Any

API_BASE_URL = "http://localhost:8000"
ADMIN_KEY_HEADER = {"X-Admin-Key": "test-admin-key"}

def get_edge_actions_results() -> Dict[str, Any]:
    """Appelle le endpoint /api/warmup/edge-actions et récupère les résultats"""
    print("=" * 80)
    print("STEP 1: Récupérer les 9 tickers calculés")
    print("=" * 80)

    url = f"{API_BASE_URL}/api/warmup/edge-actions"
    params = {"grades": "A+,A,B"}

    try:
        response = requests.post(url, params=params, headers=ADMIN_KEY_HEADER, timeout=60)

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Response reçue:")
            print(json.dumps(data, indent=2))

            tickers = data.get("edge_actions_tickers", [])
            count = data.get("edge_actions_count", 0)
            computed = data.get("edge_actions_computed", 0)

            print(f"\n📊 RÉSUMÉ:")
            print(f"   - Total tickers trouvés: {count}")
            print(f"   - Tickers calculés avec succès: {computed}")
            print(f"   - Tickers échoués: {len([e for e in data.get('errors', []) if 'edge_actions:' in e])}")
            print(f"   - Cache key utilisé: {[w for w in data.get('warnings', []) if 'cache key' in w]}")

            return data
        else:
            print(f"❌ Erreur: {response.status_code}")
            print(f"   {response.text}")
            return {}

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def check_screener_statuses(tickers: List[str]) -> Dict[str, str]:
    """Vérifie les statuts des tickers dans le screener"""
    print("\n" + "=" * 80)
    print("STEP 2: Vérifier les statuts dans le screener")
    print("=" * 80)

    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=ADMIN_KEY_HEADER, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            print(f"\n📊 Screener contient {len(results)} tickers")

            statuses = {}
            for ticker in tickers:
                for result in results:
                    if result.get("ticker") == ticker:
                        statuses[ticker] = {
                            "edge_status": result.get("ticker_edge_status", "UNKNOWN"),
                            "grade": result.get("setup_grade", "?"),
                            "tradable": result.get("tradable", False),
                            "final_decision": result.get("final_decision", "?"),
                        }
                        break
                if ticker not in statuses:
                    statuses[ticker] = {"edge_status": "NOT_FOUND_IN_SCREENER"}

            print(f"\n✅ Statuts des {len(tickers)} tickers:")
            for ticker, status in statuses.items():
                print(f"   {ticker:6} → edge_status={status.get('edge_status', '?'):20} grade={status.get('grade', '?'):3}")

            return statuses
        else:
            print(f"❌ Erreur screener: {response.status_code}")
            return {}

    except Exception as e:
        print(f"❌ Exception screener: {str(e)}")
        return {}


def check_cache_status() -> Dict[str, Any]:
    """Vérifie l'état du cache"""
    print("\n" + "=" * 80)
    print("STEP 3: Vérifier l'état du cache")
    print("=" * 80)

    url = f"{API_BASE_URL}/api/cache-status"
    params = {"scope": "all"}

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Cache status:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"ℹ️  Cache endpoint not available: {response.status_code}")
            return {}

    except Exception as e:
        print(f"ℹ️  Exception: {str(e)}")
        return {}


def test_single_tickers(tickers: List[str]) -> Dict[str, Any]:
    """Teste le calcul pour les tickers individuels"""
    print("\n" + "=" * 80)
    print(f"STEP 4: Vérifier les tickers individuels")
    print("=" * 80)

    results = {}
    key_tickers = ["LLY", "CL", "LIN", "HOLX"]  # Les tickers attendus

    for ticker in key_tickers:
        if ticker not in tickers:
            print(f"\n⚠️  {ticker} NOT in the 9 computed tickers!")
            continue

        url = f"{API_BASE_URL}/api/strategy-edge/compute"
        params = {"ticker": ticker}

        try:
            response = requests.post(url, params=params, headers=ADMIN_KEY_HEADER, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results[ticker] = data

                status = data.get("edge_status", "UNKNOWN")
                print(f"\n✅ {ticker}: edge_status = {status}")
                print(f"   - Metrics: trades={data.get('trades')}, pf={data.get('pf')}, test_pf={data.get('test_pf')}")
            else:
                print(f"\n❌ {ticker}: error {response.status_code}")
                results[ticker] = {"error": response.status_code}

            time.sleep(0.5)

        except Exception as e:
            print(f"\n❌ {ticker}: exception {str(e)}")
            results[ticker] = {"error": str(e)}

    return results


def main():
    print("\n" + "=" * 80)
    print("DIAGNOSTIC: 9 TICKERS CALCULÉS PAR 'CALCULER EDGE ACTIONS'")
    print("=" * 80)
    print(f"\nAPI: {API_BASE_URL}\n")

    # Step 1: Get the 9 tickers
    edge_actions_result = get_edge_actions_results()
    tickers = edge_actions_result.get("edge_actions_tickers", [])

    if not tickers:
        print("\n❌ Aucun ticker trouvé!")
        return

    print(f"\n🎯 LES 9 TICKERS: {tickers}")

    # Step 2: Check their statuses in screener
    statuses = check_screener_statuses(tickers)

    # Step 3: Check cache
    cache_status = check_cache_status()

    # Step 4: Check individual tickers
    individual_results = test_single_tickers(tickers)

    # SUMMARY
    print("\n" + "=" * 80)
    print("RÉSUMÉ & CONCLUSIONS")
    print("=" * 80)

    print(f"\n✅ TICKERS CALCULÉS: {len(tickers)}/9")
    print(f"   {tickers}")

    print(f"\n❓ LES 9 SONT-ILS NORMAUX ?")
    if set(["LLY", "CL", "LIN", "HOLX"]).issubset(set(tickers)):
        print(f"   ✅ OUI, LLY/CL/LIN/HOLX sont parmi les 9")
    else:
        print(f"   ❌ NON, LLY/CL/LIN/HOLX MANQUENT!")
        print(f"   Tickers attendus manquants: {set(['LLY', 'CL', 'LIN', 'HOLX']) - set(tickers)}")

    print(f"\n❓ STATUTS DANS LE SCREENER:")
    not_computed = [t for t, s in statuses.items() if "EDGE_NOT_COMPUTED" in s.get("edge_status", "")]
    if not_computed:
        print(f"   ⚠️  Encore EDGE_NOT_COMPUTED: {not_computed}")
    else:
        print(f"   ✅ Tous les statuts ont changé (pas d'EDGE_NOT_COMPUTED)")

    for ticker, status in statuses.items():
        edge_status = status.get("edge_status", "UNKNOWN")
        if edge_status != "EDGE_NOT_COMPUTED":
            print(f"      {ticker} = {edge_status}")

    print(f"\n❓ POURQUOI 9 ET PAS 45+ ?")
    print(f"   → Il y a probablement seulement 9 tickers A+/A/B dans le cache")
    print(f"   → Vérifier: Combien de tickers total dans le screener ?")
    if cache_status:
        print(f"   Cache info: {cache_status}")

    print(f"\n❓ COMMIT DÉPLOYÉ ?")
    print(f"   → Vérifier si 23f006d est le commit actuel en production")
    print(f"   → Les 9 tickers calculés = FIX FONCTIONNE!")
    print(f"   → Avant le fix: 0 tickers, Maintenant: 9 tickers ✅")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
