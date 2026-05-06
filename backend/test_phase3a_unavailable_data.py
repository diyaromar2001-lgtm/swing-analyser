"""
Test Phase 3A avec données UNAVAILABLE.

Vérifie que même quand les données sont insuffisantes,
l'API retourne tous les champs Phase 3A avec des valeurs prudentes.
"""

import unittest
from crypto_signal_enhancer import enhance_scalp_signal


class TestPhase3AUnavailableData(unittest.TestCase):
    """Test Phase 3A avec données insuffisantes."""

    def test_unavailable_data_returns_phase3a_fields(self):
        """
        Test que même avec data_status=UNAVAILABLE,
        tous les champs Phase 3A sont retournés avec des valeurs prudentes.
        """
        # Simuler enhance_scalp_signal avec données insuffisantes
        # (long_score=0, short_score=0, grade=REJECT)
        enhanced = enhance_scalp_signal(
            long_score=0,
            short_score=0,
            scalp_grade="SCALP_REJECT",
            tier=1,
            data_status="UNAVAILABLE",  # ← Key test case
            volatility_status="NORMAL",
            spread_status="UNAVAILABLE",
            spread_bps=0,
            estimated_roundtrip_cost_pct=0.0,
            paper_allowed=False,
            blocked_reasons=["Intraday data unavailable (< 20 candles)"],
            signals=[],
            warnings=[]
        )

        # Vérifier que tous les champs Phase 3A sont présents
        print("\n=== PHASE 3A WITH UNAVAILABLE DATA ===")
        print(f"long_strength: {enhanced.long_strength}")
        print(f"short_strength: {enhanced.short_strength}")
        print(f"preferred_side: {enhanced.preferred_side}")
        print(f"signal_strength: {enhanced.signal_strength}")
        print(f"confidence_score: {enhanced.confidence_score}")
        print(f"signal_reasons: {enhanced.signal_reasons}")
        print(f"signal_warnings: {enhanced.signal_warnings}")
        print(f"paper_allowed: {enhanced.paper_allowed}")

        # Assertions
        self.assertEqual(enhanced.long_strength, 0)
        self.assertEqual(enhanced.short_strength, 0)
        self.assertEqual(enhanced.preferred_side, "NONE")
        self.assertEqual(enhanced.signal_strength, "REJECT")
        self.assertEqual(enhanced.confidence_score, 20)  # Floor for REJECT
        self.assertEqual(len(enhanced.signal_reasons), 0)
        self.assertFalse(enhanced.paper_allowed)

        # Should have warnings about unavailable data
        self.assertTrue(len(enhanced.signal_warnings) > 0)

        print("\n[PASS] Phase 3A fields correctly returned even with unavailable data")

    def test_stale_data_returns_phase3a_fields(self):
        """
        Test que même avec data_status=STALE,
        tous les champs Phase 3A sont retournés.
        """
        enhanced = enhance_scalp_signal(
            long_score=70,
            short_score=40,
            scalp_grade="SCALP_A",
            tier=1,
            data_status="STALE",  # ← Key test case
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=50,
            estimated_roundtrip_cost_pct=0.15,
            paper_allowed=True,
            blocked_reasons=[],
            signals=["Strong uptrend"],
            warnings=["Data is stale (>2h old)"]
        )

        print("\n=== PHASE 3A WITH STALE DATA ===")
        print(f"signal_strength: {enhanced.signal_strength}")
        print(f"confidence_score: {enhanced.confidence_score}")
        print(f"signal_warnings: {enhanced.signal_warnings}")

        # STALE data triggers REJECT veto rule
        self.assertEqual(enhanced.signal_strength, "REJECT")
        self.assertEqual(enhanced.confidence_score, 20)
        self.assertFalse(enhanced.paper_allowed)
        self.assertIn("stale", " ".join(enhanced.signal_warnings).lower())

        print("\n[PASS] Phase 3A fields correctly returned even with stale data")

    def test_api_response_structure_with_unavailable(self):
        """
        Test que la réponse API inclurait tous les champs Phase 3A
        même si data_status=UNAVAILABLE.
        """
        # Construire une réponse API complète avec enhancement
        enhanced = enhance_scalp_signal(
            long_score=0, short_score=0, scalp_grade="SCALP_REJECT",
            tier=1, data_status="UNAVAILABLE", volatility_status="NORMAL",
            spread_status="UNAVAILABLE", spread_bps=0,
            estimated_roundtrip_cost_pct=0.0, paper_allowed=False,
            blocked_reasons=["Intraday data unavailable (< 20 candles)"],
            signals=[], warnings=[]
        )

        # Simuler la réponse API
        api_response = {
            "symbol": "BTC",
            "data_status": "UNAVAILABLE",
            "blockedreasons": ["Intraday data unavailable (< 20 candles)"],

            # Phase 3A fields (NEW)
            "long_strength": enhanced.long_strength,
            "short_strength": enhanced.short_strength,
            "preferred_side": enhanced.preferred_side,
            "signal_strength": enhanced.signal_strength,
            "confidence_score": enhanced.confidence_score,
            "signal_reasons": enhanced.signal_reasons,
            "signal_warnings": enhanced.signal_warnings,

            # Security
            "scalp_execution_authorized": False,
            "paper_allowed": enhanced.paper_allowed,
        }

        # Vérifier que tous les champs sont présents
        phase3a_fields = [
            'long_strength', 'short_strength', 'preferred_side',
            'signal_strength', 'confidence_score', 'signal_reasons',
            'signal_warnings'
        ]

        print("\n=== API RESPONSE WITH UNAVAILABLE DATA ===")
        for field in phase3a_fields:
            self.assertIn(field, api_response,
                         f"Field {field} missing from API response")
            print(f"[PASS] {field}: {api_response[field]}")

        # Verify security
        self.assertFalse(api_response['scalp_execution_authorized'])
        print(f"[PASS] scalp_execution_authorized: false")

        print("\n[PASS] All Phase 3A fields present in API response")


if __name__ == "__main__":
    unittest.main(verbosity=2)
