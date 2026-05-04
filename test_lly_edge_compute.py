#!/usr/bin/env python3
"""
TEST PRATIQUE: Vérifier que le bouton "Calculer Edge LLY" fonctionne
1. Appelle l'endpoint /api/strategy-edge/compute?ticker=LLY
2. Vérifie les 9 tickers retournés par /api/warmup/edge-actions
3. Affiche les statuts
4. Teste si LLY manque des 9 et pourquoi
"""

import requests
import json
import time
from typing import Dict, List, Any

API_BASE_URL = "http://localhost:8000"
ADMIN_KEY = "test-admin-key"  # Remplacer par votre vraie clé
HEADERS = {"X-Admin-Key": ADMIN_KEY}

def test_9_tickers() -> Dict[str, Any]:
    """Étape 1: Récupérer les 9 tickers calculés par Admin"""
    print("\n" + "="*80)
    print("ÉTAPE 1: Récupérer les 9 tickers du bouton Admin")
    print("="*80)

    url = f"{API_BASE_URL}/api/warmup/edge-actions"
    params = {"grades": "A+,A,B"}

    try:
        response = requests.post(url, params=params, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            data = response.json()
            tickers = data.get("edge_actions_tickers", [])
            count = data.get("edge_actions_count", 0)
            computed = data.get("edge_actions_computed", 0)

            print(f"\n✅ Response reçue:")
            print(f"   - Tickers trouvés: {count}")
            print(f"   - Tickers calculés: {computed}")
            print(f"   - Tickers failed: {len([e for e in data.get('errors', []) if 'edge_actions:' in e])}")
            print(f"\n📋 LES {count} TICKERS:")
            for i, ticker in enumerate(tickers, 1):
                print(f"   {i}. {ticker}")

            return data
        else:
            print(f"❌ Erreur: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def test_lly_individual() -> Dict[str, Any]:
    """Étape 2: Calculer edge pour LLY individuellement"""
    print("\n" + "="*80)
    print("ÉTAPE 2: Calculer Edge pour LLY (Endpoint Individual)")
    print("="*80)

    url = f"{API_BASE_URL}/api/strategy-edge/compute"
    params = {"ticker": "LLY"}

    try:
        response = requests.post(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Response reçue:")
            print(json.dumps(data, indent=2))

            status = data.get("edge_status", "UNKNOWN")
            print(f"\n📊 RÉSULTAT POUR LLY:")
            print(f"   - Status: {status}")
            print(f"   - Trades: {data.get('trades', 'N/A')}")
            print(f"   - PF: {data.get('pf', 'N/A')}")
            print(f"   - Test PF: {data.get('test_pf', 'N/A')}")
            print(f"   - Expectancy: {data.get('expectancy', 'N/A')}")
            print(f"   - Overfit: {data.get('overfit', 'N/A')}")
            print(f"   - Duration: {data.get('duration_ms', 'N/A')}ms")

            return data
        else:
            print(f"❌ Erreur: {response.status_code}")
            print(f"   {response.text}")
            return {}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {}


def check_screener_lly() -> Dict[str, Any]:
    """Étape 3: Vérifier le statut de LLY dans le screener"""
    print("\n" + "="*80)
    print("ÉTAPE 3: Vérifier LLY dans le Screener")
    print("="*80)

    url = f"{API_BASE_URL}/api/screener"
    params = {"strategy": "standard", "fast": "true"}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            print(f"\n✅ Screener retourne {len(results)} tickers")

            # Chercher LLY
            lly_data = None
            for result in results:
                if result.get("ticker") == "LLY":
                    lly_data = result
                    break

            if lly_data:
                print(f"\n✅ LLY TROUVÉ dans le screener:")
                print(f"   - Edge Status: {lly_data.get('ticker_edge_status', 'UNKNOWN')}")
                print(f"   - Setup Grade: {lly_data.get('setup_grade', 'UNKNOWN')}")
                print(f"   - Score: {lly_data.get('score', 'UNKNOWN')}")
                print(f"   - Tradable: {lly_data.get('tradable', 'UNKNOWN')}")
                print(f"   - Final Decision: {lly_data.get('final_decision', 'UNKNOWN')}")

                return lly_data
            else:
                print(f"\n❌ LLY NOT FOUND in screener results")
                # Afficher les premiers 10
                print(f"\n   Premiers 10 tickers du screener:")
                for i, result in enumerate(results[:10], 1):
                    print(f"   {i}. {result.get('ticker', 'UNKNOWN')}")
                return {}

        else:
            print(f"❌ Erreur screener: {response.status_code}")
            return {}

    except Exception as e:
        print(f"❌ Exception screener: {str(e)}")
        return {}


def check_other_tickers(edge_actions_data: Dict) -> None:
    """Étape 4: Vérifier CL, LIN, HOLX"""
    print("\n" + "="*80)
    print("ÉTAPE 4: Vérifier CL, LIN, HOLX")
    print("="*80)

    tickers_to_check = ["CL", "LIN", "HOLX"]
    in_9 = edge_actions_data.get("edge_actions_tickers", [])

    for ticker in tickers_to_check:
        in_list = "✅ OUI" if ticker in in_9 else "❌ NON"
        print(f"\n{ticker} dans les 9? {in_list}")

        # Tester individuellement
        print(f"   Calcul edge pour {ticker}...")
        url = f"{API_BASE_URL}/api/strategy-edge/compute"
        params = {"ticker": ticker}

        try:
            response = requests.post(url, params=params, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                data = response.json()
                status = data.get("edge_status", "UNKNOWN")
                print(f"   → Status: {status}")
            else:
                print(f"   → Erreur: {response.status_code}")
        except Exception as e:
            print(f"   → Exception: {str(e)}")

        time.sleep(0.5)


def main():
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*20 + "TEST: CALCULER EDGE POUR LLY" + " "*30 + "║")
    print("╚" + "═"*78 + "╝")

    print(f"\nAPI: {API_BASE_URL}")
    print(f"Admin Key: {ADMIN_KEY if ADMIN_KEY != 'test-admin-key' else '(à remplacer)'}")

    # Étape 1: Les 9 tickers
    edge_actions = test_9_tickers()
    if not edge_actions:
        print("\n❌ Impossible de continuer sans les 9 tickers")
        return

    # Étape 2: Calculer LLY
    lly_edge = test_lly_individual()

    # Étape 3: Vérifier LLY dans screener
    lly_screener = check_screener_lly()

    # Étape 4: Vérifier autres
    check_other_tickers(edge_actions)

    # Résumé
    print("\n" + "="*80)
    print("RÉSUMÉ")
    print("="*80)

    in_9 = edge_actions.get("edge_actions_tickers", [])
    print(f"\n✅ Les 9 tickers: {in_9}")

    print(f"\n❓ LLY dans les 9?")
    if "LLY" in in_9:
        print(f"   ✅ OUI")
        print(f"   → LLY a déjà été calculé par le bouton Admin")
    else:
        print(f"   ❌ NON")
        print(f"   → Raison: Probablement score < 58 (REJECT)")
        print(f"   → Solution: Bouton 'Calculer Edge LLY' dans Trade Plan")

    print(f"\n✅ Edge Calculé pour LLY?")
    if lly_edge and lly_edge.get("status") == "ok":
        print(f"   ✅ OUI")
        print(f"   → Status: {lly_edge.get('edge_status')}")
    else:
        print(f"   ❌ NON")
        print(f"   → Raison: {lly_edge.get('message', 'Unknown')}")

    print(f"\n✅ Screener montre LLY?")
    if lly_screener:
        print(f"   ✅ OUI")
        print(f"   → Status: {lly_screener.get('ticker_edge_status')}")
        if lly_screener.get('ticker_edge_status') == "EDGE_NOT_COMPUTED":
            print(f"   → Encore EDGE_NOT_COMPUTED (pas encore refresh)")
        else:
            print(f"   → Changé depuis EDGE_NOT_COMPUTED ✅")
    else:
        print(f"   ❌ NON")

    print(f"\n📋 CONCLUSION:")
    print(f"   1. Si LLY ❌ dans 9 ET statut ❌ EDGE_NOT_COMPUTED:")
    print(f"      → Bouton 'Calculer Edge LLY' devrait être visible ✅")
    print(f"   2. Si LLY ✅ dans 9:")
    print(f"      → Déjà calculé, pas besoin bouton ✅")
    print(f"   3. Après calcul:")
    print(f"      → Recharger Screener (F5)")
    print(f"      → LLY badge devrait changer ✅")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
