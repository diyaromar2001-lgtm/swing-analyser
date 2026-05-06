"""
Unit tests for Phase 3A Signal Quality Enhancement

Tests the 5 validated test cases:
1. BTC (A+ grade, strong signals) → STRONG signal
2. ETH (B grade, weak signals) → WEAK signal
3. SOL (STALE data) → REJECT (data penalty)
4. MKR (high costs 1.8%) → reduced strength, lowered confidence
5. RENDER (REJECT grade) → REJECT (veto rule)
"""

import unittest
from crypto_signal_enhancer import enhance_scalp_signal, _classify_signal_strength, _calculate_confidence


class TestPhase3ASignalEnhancer(unittest.TestCase):
    """Test Phase 3A signal enhancement logic."""

    def test_btc_strong_signal(self):
        """
        BTC: Grade A+, long_score 78, short_score 42
        Scenario: Strong uptrend, good momentum, volume support
        Expected: STRONG signal, high confidence (90%+)
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

        assert enhanced.long_strength == 78
        assert enhanced.short_strength == 42
        assert enhanced.preferred_side == "LONG"
        assert enhanced.signal_strength == "STRONG"
        assert enhanced.confidence_score >= 90
        assert enhanced.paper_allowed is True
        assert len(enhanced.signal_reasons) <= 3
        assert len(enhanced.signal_warnings) == 0

    def test_eth_weak_signal(self):
        """
        ETH: Grade B, long_score 52, short_score 48
        Scenario: Marginal signal, conflicting LONG/SHORT
        Expected: WEAK signal, moderate confidence (50-60%)
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
            signals=[
                "Price above EMA20",
                "Volume normal"
            ],
            warnings=[]
        )

        assert enhanced.long_strength >= 45  # Passes WEAK threshold
        assert enhanced.long_strength < 55   # But below NORMAL threshold
        assert enhanced.signal_strength == "WEAK"
        assert enhanced.preferred_side == "NONE"  # Delta < 5, no preference
        assert 35 <= enhanced.confidence_score <= 45  # B grade (45) - WEAK penalty (-5) = 40
        assert "Conflicting signals" in " ".join(enhanced.signal_warnings)

    def test_sol_stale_data_reject(self):
        """
        SOL: Grade A, but data_status = STALE
        Scenario: Good score but data is >2h old
        Expected: REJECT (veto rule: stale data)
        """
        enhanced = enhance_scalp_signal(
            long_score=70,
            short_score=45,
            scalp_grade="SCALP_A",
            tier=2,
            data_status="STALE",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=60,
            estimated_roundtrip_cost_pct=0.20,
            paper_allowed=True,
            blocked_reasons=[],
            signals=["Uptrend confirmed (price > EMA9 > EMA20)"],
            warnings=["Data is stale (>2h old)"]
        )

        assert enhanced.signal_strength == "REJECT"
        assert enhanced.confidence_score <= 20  # Floor for REJECT
        assert len(enhanced.signal_reasons) == 0  # REJECT has no reasons
        assert "stale" in " ".join(enhanced.signal_warnings).lower()

    def test_mkr_high_cost_penalty(self):
        """
        MKR: Grade A+, but high costs (1.8%)
        Scenario: Good signal but roundtrip cost 1.8% erodes profitability
        Expected: Strength reduced by -10, confidence reduced
        """
        enhanced = enhance_scalp_signal(
            long_score=75,
            short_score=40,
            scalp_grade="SCALP_A+",
            tier=2,
            data_status="FRESH",
            volatility_status="NORMAL",
            spread_status="OK",
            spread_bps=90,
            estimated_roundtrip_cost_pct=1.8,  # High cost triggers -10 penalty
            paper_allowed=True,
            blocked_reasons=[],
            signals=["Strong uptrend"],
            warnings=["High costs (1.0-2.0%)"]
        )

        # Cost penalty: >1.0% = -10 points
        expected_strength = 75 - 10
        assert enhanced.long_strength == expected_strength
        assert enhanced.signal_strength == "NORMAL"  # Reduced from STRONG
        assert enhanced.confidence_score < 85  # Reduced from A+ base
        assert "cost" in " ".join(enhanced.signal_warnings).lower()

    def test_render_reject_grade(self):
        """
        RENDER: Grade SCALP_REJECT
        Scenario: Low quality signal, grade is REJECT
        Expected: REJECT (veto rule: grade == REJECT)
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

        assert enhanced.signal_strength == "REJECT"
        assert enhanced.confidence_score <= 20
        assert len(enhanced.signal_reasons) == 0
        assert enhanced.paper_allowed is False

    def test_classify_signal_strength_boundaries(self):
        """Test signal strength classification thresholds."""
        # STRONG: max >= 75
        assert _classify_signal_strength(
            long_strength=75, short_strength=40,
            scalp_grade="SCALP_A+", paper_allowed=True,
            data_status="FRESH", blocked_reasons=[]
        ) == "STRONG"

        # NORMAL: 60-74
        assert _classify_signal_strength(
            long_strength=70, short_strength=40,
            scalp_grade="SCALP_A", paper_allowed=True,
            data_status="FRESH", blocked_reasons=[]
        ) == "NORMAL"

        # WEAK: 45-59
        assert _classify_signal_strength(
            long_strength=50, short_strength=40,
            scalp_grade="SCALP_B", paper_allowed=True,
            data_status="FRESH", blocked_reasons=[]
        ) == "WEAK"

        # REJECT: <45
        assert _classify_signal_strength(
            long_strength=40, short_strength=30,
            scalp_grade="SCALP_B", paper_allowed=True,
            data_status="FRESH", blocked_reasons=[]
        ) == "REJECT"

    def test_veto_rules(self):
        """Test all veto rules force REJECT."""
        # Veto 1: Grade REJECT
        assert _classify_signal_strength(
            long_strength=90, short_strength=80,
            scalp_grade="SCALP_REJECT", paper_allowed=True,
            data_status="FRESH", blocked_reasons=[]
        ) == "REJECT"

        # Veto 2: paper_allowed = False
        assert _classify_signal_strength(
            long_strength=90, short_strength=80,
            scalp_grade="SCALP_A+", paper_allowed=False,
            data_status="FRESH", blocked_reasons=[]
        ) == "REJECT"

        # Veto 3: blocked_reasons not empty
        assert _classify_signal_strength(
            long_strength=90, short_strength=80,
            scalp_grade="SCALP_A+", paper_allowed=True,
            data_status="FRESH", blocked_reasons=["Some blocking reason"]
        ) == "REJECT"

        # Veto 4: data_status = UNAVAILABLE
        assert _classify_signal_strength(
            long_strength=90, short_strength=80,
            scalp_grade="SCALP_A+", paper_allowed=True,
            data_status="UNAVAILABLE", blocked_reasons=[]
        ) == "REJECT"

        # Veto 5: data_status = STALE
        assert _classify_signal_strength(
            long_strength=90, short_strength=80,
            scalp_grade="SCALP_A+", paper_allowed=True,
            data_status="STALE", blocked_reasons=[]
        ) == "REJECT"

    def test_confidence_score_formula(self):
        """Test confidence score calculation."""
        # A+ base (75) + STRONG (+15) = 90
        confidence = _calculate_confidence(
            scalp_grade="SCALP_A+",
            signal_strength="STRONG",
            data_status="FRESH",
            volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.15
        )
        assert confidence == 90

        # A base (60) + NORMAL (+5) = 65
        confidence = _calculate_confidence(
            scalp_grade="SCALP_A",
            signal_strength="NORMAL",
            data_status="FRESH",
            volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.15
        )
        assert confidence == 65

        # REJECT floor (20)
        confidence = _calculate_confidence(
            scalp_grade="SCALP_REJECT",
            signal_strength="REJECT",
            data_status="FRESH",
            volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.15
        )
        assert confidence == 20

        # Clamped at 95 max
        confidence = _calculate_confidence(
            scalp_grade="SCALP_A+",
            signal_strength="STRONG",
            data_status="FRESH",
            volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.0
        )
        assert confidence <= 95

    def test_confidence_penalties(self):
        """Test confidence penalty application."""
        # High volatility: -10
        confidence_normal = _calculate_confidence(
            scalp_grade="SCALP_A", signal_strength="NORMAL",
            data_status="FRESH", volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.15
        )
        confidence_high_vol = _calculate_confidence(
            scalp_grade="SCALP_A", signal_strength="NORMAL",
            data_status="FRESH", volatility_status="HIGH",
            estimated_roundtrip_cost_pct=0.15
        )
        assert confidence_high_vol == confidence_normal - 10

        # Cost >2.0%: -15
        confidence_low_cost = _calculate_confidence(
            scalp_grade="SCALP_A+", signal_strength="NORMAL",
            data_status="FRESH", volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=0.15
        )
        confidence_high_cost = _calculate_confidence(
            scalp_grade="SCALP_A+", signal_strength="NORMAL",
            data_status="FRESH", volatility_status="NORMAL",
            estimated_roundtrip_cost_pct=2.5
        )
        assert confidence_high_cost == confidence_low_cost - 15

    def test_preferred_side_delta_threshold(self):
        """Test preferred_side determination with delta >= 5."""
        enhanced = enhance_scalp_signal(
            long_score=70, short_score=65,  # Delta = 5, exactly at threshold
            scalp_grade="SCALP_A", tier=1, data_status="FRESH",
            volatility_status="NORMAL", spread_status="OK", spread_bps=50,
            estimated_roundtrip_cost_pct=0.15, paper_allowed=True,
            blocked_reasons=[], signals=[], warnings=[]
        )
        assert enhanced.preferred_side == "LONG"

        enhanced = enhance_scalp_signal(
            long_score=70, short_score=66,  # Delta = 4, below threshold
            scalp_grade="SCALP_A", tier=1, data_status="FRESH",
            volatility_status="NORMAL", spread_status="OK", spread_bps=50,
            estimated_roundtrip_cost_pct=0.15, paper_allowed=True,
            blocked_reasons=[], signals=[], warnings=[]
        )
        assert enhanced.preferred_side == "NONE"


if __name__ == "__main__":
    unittest.main(verbosity=2)
