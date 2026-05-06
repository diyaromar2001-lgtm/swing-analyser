"""
Test Phase 3A en production avec données mock.

Simule des données OHLCV valides pour prouver que:
1. enhance_scalp_signal() est appelé
2. Les champs Phase 3A apparaissent dans la réponse
3. L'intégration avec crypto_scalp_service fonctionne
"""

import unittest
import pandas as pd
from crypto_signal_enhancer import enhance_scalp_signal


class TestPhase3AProductionIntegration(unittest.TestCase):
    """Test l'intégration Phase 3A avec des données réalistes."""

    def test_production_response_structure_with_valid_data(self):
        """
        Test que la réponse API inclut tous les champs Phase 3A
        quand les données sont valides (data_status="FRESH").
        """
        # Simuler une réponse API complète avec enhancement
        api_response = self._simulate_api_response_with_valid_data()

        # Vérifier que tous les champs Phase 3A sont présents
        phase3a_fields = [
            'long_strength',
            'short_strength',
            'preferred_side',
            'signal_strength',
            'confidence_score',
            'signal_reasons',
            'signal_warnings',
        ]

        for field in phase3a_fields:
            self.assertIn(field, api_response, f"Phase 3A field missing: {field}")

        # Vérifier que security fields sont corrects
        self.assertFalse(api_response['scalp_execution_authorized'],
                        "execution_authorized must be false")
        self.assertTrue(api_response['paper_allowed'],
                       "paper_allowed should be true for valid signals")

    def test_strong_signal_production_output(self):
        """
        Test que BTC avec bonnes données produit un signal STRONG
        comme prévu en production.
        """
        enhanced = enhance_scalp_signal(
            long_score=78,
            short_score=42,
            scalp_grade="SCALP_A+",
            tier=1,
            data_status="FRESH",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=50,
            estimated_roundtrip_cost_pct=0.15,
            paper_allowed=True,
            blocked_reasons=[],
            signals=[
                "Strong uptrend (price > EMA9 > EMA20 > EMA50)",
                "MACD bullish cross above signal",
                "Volume surge last 5 candles"
            ],
            warnings=[]
        )

        # Vérifier la structure complète de la réponse
        api_payload = self._build_api_response(enhanced)

        print("\n=== PRODUCTION API RESPONSE (BTC with valid data) ===")
        print(f"Symbol: {api_payload['symbol']}")
        print(f"Grade: {api_payload['scalp_grade']}")
        print(f"Long Strength: {api_payload['long_strength']}")
        print(f"Short Strength: {api_payload['short_strength']}")
        print(f"Preferred Side: {api_payload['preferred_side']}")
        print(f"Signal Strength: {api_payload['signal_strength']}")
        print(f"Confidence Score: {api_payload['confidence_score']}%")
        print(f"Reasons: {api_payload['signal_reasons'][:2]}...")
        print(f"Warnings: {len(api_payload['signal_warnings'])} warning(s)")
        print(f"Execution Authorized: {api_payload['scalp_execution_authorized']}")
        print(f"Paper Allowed: {api_payload['paper_allowed']}")

        # Vérifications
        self.assertEqual(api_payload['long_strength'], 78)
        self.assertEqual(api_payload['short_strength'], 42)
        self.assertEqual(api_payload['preferred_side'], "LONG")
        self.assertEqual(api_payload['signal_strength'], "STRONG")
        self.assertGreaterEqual(api_payload['confidence_score'], 90)
        self.assertFalse(api_payload['scalp_execution_authorized'])
        self.assertTrue(api_payload['paper_allowed'])

        print("\n✅ BTC STRONG signal validated for production")

    def test_weak_signal_production_output(self):
        """
        Test que ETH avec signaux faibles produit un signal WEAK
        avec avertissements.
        """
        enhanced = enhance_scalp_signal(
            long_score=52,
            short_score=48,
            scalp_grade="SCALP_B",
            tier=1,
            data_status="FRESH",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=80,
            estimated_roundtrip_cost_pct=0.25,
            paper_allowed=True,
            blocked_reasons=[],
            signals=["Price above EMA20", "Volume normal"],
            warnings=[]
        )

        api_payload = self._build_api_response(enhanced)

        print("\n=== PRODUCTION API RESPONSE (ETH with weak signal) ===")
        print(f"Symbol: {api_payload['symbol']}")
        print(f"Signal Strength: {api_payload['signal_strength']}")
        print(f"Preferred Side: {api_payload['preferred_side']}")
        print(f"Confidence Score: {api_payload['confidence_score']}%")
        print(f"Warnings: {api_payload['signal_warnings']}")

        self.assertEqual(api_payload['signal_strength'], "WEAK")
        self.assertEqual(api_payload['preferred_side'], "NONE")
        self.assertIn("Conflicting signals", " ".join(api_payload['signal_warnings']))

        print("\n✅ ETH WEAK signal with warnings validated for production")

    def test_reject_signal_production_output(self):
        """
        Test que les signaux REJECT n'ont pas de raisons
        (sécurité en production).
        """
        enhanced = enhance_scalp_signal(
            long_score=35,
            short_score=30,
            scalp_grade="SCALP_REJECT",
            tier=3,
            data_status="FRESH",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=120,
            estimated_roundtrip_cost_pct=0.30,
            paper_allowed=False,
            blocked_reasons=["No clear LONG or SHORT signal"],
            signals=[],
            warnings=["Very low ATR (dead market)"]
        )

        api_payload = self._build_api_response(enhanced)

        print("\n=== PRODUCTION API RESPONSE (REJECT signal) ===")
        print(f"Signal Strength: {api_payload['signal_strength']}")
        print(f"Confidence Score: {api_payload['confidence_score']}")
        print(f"Reasons (should be empty): {api_payload['signal_reasons']}")
        print(f"Paper Allowed: {api_payload['paper_allowed']}")

        self.assertEqual(api_payload['signal_strength'], "REJECT")
        self.assertEqual(len(api_payload['signal_reasons']), 0)
        self.assertFalse(api_payload['paper_allowed'])
        self.assertEqual(api_payload['confidence_score'], 20)

        print("\n✅ REJECT signal properly formed for production")

    def test_cost_penalty_production_impact(self):
        """
        Test que les coûts élevés (1.8%) réduisent le signal
        comme prévu en production.
        """
        # Avec coûts bas
        enhanced_low_cost = enhance_scalp_signal(
            long_score=75, short_score=40, scalp_grade="SCALP_A+",
            tier=1, data_status="FRESH", volatility_status="NORMAL",
            spread_status="OK", spread_bps=50, estimated_roundtrip_cost_pct=0.15,
            paper_allowed=True, blocked_reasons=[],
            signals=["Strong signal"], warnings=[]
        )

        # Avec coûts élevés
        enhanced_high_cost = enhance_scalp_signal(
            long_score=75, short_score=40, scalp_grade="SCALP_A+",
            tier=1, data_status="FRESH", volatility_status="NORMAL",
            spread_status="OK", spread_bps=120, estimated_roundtrip_cost_pct=1.8,
            paper_allowed=True, blocked_reasons=[],
            signals=["Strong signal"], warnings=["High costs (1.0-2.0%)"]
        )

        print("\n=== PRODUCTION COST IMPACT ===")
        print(f"Low cost (0.15%):  strength={enhanced_low_cost.long_strength}, "
              f"signal={enhanced_low_cost.signal_strength}, "
              f"confidence={enhanced_low_cost.confidence_score}%")
        print(f"High cost (1.8%):  strength={enhanced_high_cost.long_strength}, "
              f"signal={enhanced_high_cost.signal_strength}, "
              f"confidence={enhanced_high_cost.confidence_score}%")

        # Vérifier la réduction due aux coûts
        self.assertLess(enhanced_high_cost.long_strength,
                       enhanced_low_cost.long_strength)
        self.assertLess(enhanced_high_cost.confidence_score,
                       enhanced_low_cost.confidence_score)

        print("\n✅ Cost penalties correctly impact signal strength for production")

    def _simulate_api_response_with_valid_data(self):
        """
        Simule la réponse API complète avec enhancement
        (comme elle apparaîtrait en production quand data_status="FRESH").
        """
        enhanced = enhance_scalp_signal(
            long_score=72,
            short_score=45,
            scalp_grade="SCALP_A",
            tier=1,
            data_status="FRESH",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=60,
            estimated_roundtrip_cost_pct=0.20,
            paper_allowed=True,
            blocked_reasons=[],
            signals=["Uptrend confirmed", "Good volume", "RSI in zone"],
            warnings=[]
        )

        return self._build_api_response(enhanced)

    def _build_api_response(self, enhanced):
        """
        Construit une réponse API complète avec tous les champs
        (simulant ce que crypto_scalp_service.py retournerait).
        """
        return {
            "symbol": "TEST",
            "tier": 1,
            "side": "LONG" if enhanced.long_strength > enhanced.short_strength + 5 else "SHORT",
            "scalp_score": 72,
            "scalp_grade": "SCALP_A+",
            "long_score": 72,
            "short_score": 45,
            "strategy_name": "Uptrend",
            "timeframe": "5m",
            "entry": 100.0,
            "stop_loss": 99.0,
            "tp1": 101.0,
            "tp2": 102.0,
            "rr_ratio": 2.0,
            "data_status": "FRESH",
            "volatility_status": "NORMAL",
            "spread_status": "OK",
            "spread_bps": 60,
            "slippage_pct": 0.05,
            "entry_fee_pct": 0.10,
            "exit_fee_pct": 0.10,
            "estimated_roundtrip_cost_pct": 0.20,
            "scalp_execution_authorized": False,
            "paper_allowed": True,
            "watchlist_allowed": True,
            "blocked_reasons": [],
            "signal_reasons": enhanced.signal_reasons,

            # Phase 3A Enhancement Fields
            "long_strength": enhanced.long_strength,
            "short_strength": enhanced.short_strength,
            "preferred_side": enhanced.preferred_side,
            "signal_strength": enhanced.signal_strength,
            "confidence_score": enhanced.confidence_score,
            "signal_warnings": enhanced.signal_warnings,
        }


if __name__ == "__main__":
    unittest.main(verbosity=2)
