"""
Phase 3A: Signal Quality Enhancement for Crypto Scalp

Enhances crypto scalp signals with:
- Separate LONG/SHORT strength calculation
- Signal strength classification (STRONG/NORMAL/WEAK/REJECT)
- Confidence score (0-100)
- Explicit reasons and warnings
- preferred_side determination

Uses only existing fields from analyze_crypto_scalp_symbol() response.
No new data sources. Defensive approach (penalties only).
"""

from typing import Dict, List, Any, Optional


class EnhancedSignal:
    """Result of signal enhancement."""

    def __init__(
        self,
        long_strength: int,
        short_strength: int,
        preferred_side: str,
        signal_strength: str,
        confidence_score: int,
        signal_reasons: List[str],
        signal_warnings: List[str],
        paper_allowed: bool,
    ):
        self.long_strength = long_strength
        self.short_strength = short_strength
        self.preferred_side = preferred_side
        self.signal_strength = signal_strength
        self.confidence_score = confidence_score
        self.signal_reasons = signal_reasons
        self.signal_warnings = signal_warnings
        self.paper_allowed = paper_allowed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "long_strength": self.long_strength,
            "short_strength": self.short_strength,
            "preferred_side": self.preferred_side,
            "signal_strength": self.signal_strength,
            "confidence_score": self.confidence_score,
            "signal_reasons": self.signal_reasons,
            "signal_warnings": self.signal_warnings,
            "paper_allowed": self.paper_allowed,
        }


def enhance_scalp_signal(
    long_score: int,
    short_score: int,
    scalp_grade: str,
    tier: int,
    data_status: str,
    volatility_status: str,
    spread_status: str,
    spread_bps: int,
    estimated_roundtrip_cost_pct: float,
    paper_allowed: bool,
    blocked_reasons: List[str],
    signals: List[str],
    warnings: List[str],
) -> EnhancedSignal:
    """
    Enhance crypto scalp signal with strength, confidence, and clarity.

    Args:
        long_score: LONG directional bias (0-100) from crypto_scalp_score
        short_score: SHORT directional bias (0-100) from crypto_scalp_score
        scalp_grade: Grade from crypto_scalp_score (SCALP_A+/A/B/REJECT)
        tier: Liquidity tier (1/2/3)
        data_status: FRESH/STALE/UNAVAILABLE
        volatility_status: NORMAL/HIGH/LOW
        spread_status: OK/WARNING/UNAVAILABLE
        spread_bps: Bid-ask spread in basis points
        estimated_roundtrip_cost_pct: Total transaction cost
        paper_allowed: True if grade allows paper trading
        blocked_reasons: List of blocking reasons
        signals: Existing signals from compute_scalp_score
        warnings: Existing warnings from compute_scalp_score

    Returns:
        EnhancedSignal with all enhancement fields
    """

    # Initialize warning collection (copy existing, add new)
    all_warnings = list(warnings) if warnings else []

    # ─ STEP 1: Calculate long_strength and short_strength with penalties ──
    long_strength = long_score
    short_strength = short_score

    # Data quality penalty
    if data_status == "STALE":
        long_strength = max(long_strength - 15, 0)
        short_strength = max(short_strength - 15, 0)
        all_warnings.append("Data is stale (>2h old)")
    elif data_status == "UNAVAILABLE":
        long_strength = max(long_strength - 25, 0)
        short_strength = max(short_strength - 25, 0)
        all_warnings.append("Data unavailable")

    # Volatility penalty
    if volatility_status == "HIGH":
        long_strength = max(long_strength - 10, 0)
        short_strength = max(short_strength - 10, 0)
        all_warnings.append("High volatility")
    elif volatility_status == "LOW":
        long_strength = max(long_strength - 5, 0)
        short_strength = max(short_strength - 5, 0)
        all_warnings.append("Low volatility")

    # Cost penalty (tiered)
    if estimated_roundtrip_cost_pct > 2.0:
        long_strength = max(long_strength - 20, 0)
        short_strength = max(short_strength - 20, 0)
        all_warnings.append("Very high costs (>2.0%)")
    elif estimated_roundtrip_cost_pct > 1.0:
        long_strength = max(long_strength - 10, 0)
        short_strength = max(short_strength - 10, 0)
        all_warnings.append("High costs (1.0-2.0%)")
    elif estimated_roundtrip_cost_pct > 0.5:
        long_strength = max(long_strength - 5, 0)
        short_strength = max(short_strength - 5, 0)

    # Spread penalty
    if spread_status == "WARNING":
        long_strength = max(long_strength - 5, 0)
        short_strength = max(short_strength - 5, 0)
        all_warnings.append("Elevated spread")

    # Clamp to valid range
    long_strength = max(0, min(long_strength, 100))
    short_strength = max(0, min(short_strength, 100))

    # ─ STEP 2: Determine preferred_side ──
    max_strength = max(long_strength, short_strength)
    delta = abs(long_strength - short_strength)

    if long_strength >= short_strength + 5:
        preferred_side = "LONG"
    elif short_strength >= long_strength + 5:
        preferred_side = "SHORT"
    else:
        preferred_side = "NONE"
        all_warnings.append("Conflicting signals (LONG/SHORT too close)")

    # ─ STEP 3: Classify signal_strength ──
    signal_strength = _classify_signal_strength(
        long_strength=long_strength,
        short_strength=short_strength,
        scalp_grade=scalp_grade,
        paper_allowed=paper_allowed,
        data_status=data_status,
        blocked_reasons=blocked_reasons,
    )

    # ─ STEP 4: Calculate confidence_score ──
    confidence_score = _calculate_confidence(
        scalp_grade=scalp_grade,
        signal_strength=signal_strength,
        data_status=data_status,
        volatility_status=volatility_status,
        estimated_roundtrip_cost_pct=estimated_roundtrip_cost_pct,
    )

    # ─ STEP 5: Generate reasons ──
    signal_reasons = _generate_reasons(
        long_strength=long_strength,
        short_strength=short_strength,
        scalp_grade=scalp_grade,
        signal_strength=signal_strength,
        data_status=data_status,
        paper_allowed=paper_allowed,
        signals=signals,
    )

    # ─ STEP 6: Add additional warnings ──
    if signal_strength == "WEAK":
        all_warnings.append("Signal strength WEAK")

    if delta < 5 and signal_strength != "REJECT":
        # Already added "Conflicting signals" above
        pass

    return EnhancedSignal(
        long_strength=long_strength,
        short_strength=short_strength,
        preferred_side=preferred_side,
        signal_strength=signal_strength,
        confidence_score=confidence_score,
        signal_reasons=signal_reasons,
        signal_warnings=all_warnings,
        paper_allowed=paper_allowed,
    )


def _classify_signal_strength(
    long_strength: int,
    short_strength: int,
    scalp_grade: str,
    paper_allowed: bool,
    data_status: str,
    blocked_reasons: List[str],
) -> str:
    """
    Classify signal strength: STRONG / NORMAL / WEAK / REJECT

    Veto rules (immediate REJECT):
    - scalp_grade == "SCALP_REJECT"
    - paper_allowed == False
    - blocked_reasons not empty
    - data_status == "UNAVAILABLE" or "STALE"

    Score thresholds:
    - STRONG: max_strength >= 75 AND grade in [A+, A]
    - NORMAL: max_strength >= 60 AND grade in [A+, A, B]
    - WEAK: max_strength >= 45
    - REJECT: otherwise
    """

    # Veto checks
    if scalp_grade == "SCALP_REJECT":
        return "REJECT"

    if paper_allowed is False:
        return "REJECT"

    if blocked_reasons:
        return "REJECT"

    if data_status == "UNAVAILABLE":
        return "REJECT"

    if data_status == "STALE":
        return "REJECT"  # Conservative: stale data = reject

    # Score-based classification
    max_strength = max(long_strength, short_strength)

    if max_strength >= 75 and scalp_grade in ["SCALP_A+", "SCALP_A"]:
        return "STRONG"

    elif max_strength >= 60 and scalp_grade in ["SCALP_A+", "SCALP_A", "SCALP_B"]:
        return "NORMAL"

    elif max_strength >= 45:
        return "WEAK"

    else:
        return "REJECT"


def _calculate_confidence(
    scalp_grade: str,
    signal_strength: str,
    data_status: str,
    volatility_status: str,
    estimated_roundtrip_cost_pct: float,
) -> int:
    """
    Calculate confidence score (0-100, clamped 20-95).

    Formula:
    1. Grade-based base (75 for A+, 60 for A, 45 for B, 20 for REJECT)
    2. Signal strength adjustment (+15 STRONG, +5 NORMAL, -5 WEAK, =20 REJECT)
    3. Data quality penalty (-20 STALE, -25 UNAVAILABLE)
    4. Volatility penalty (-10 HIGH, -5 LOW)
    5. Cost penalty (-15 >2%, -8 1-2%, -3 0.5-1%)
    6. Clamp to [20, 95]
    """

    # Step 1: Grade-based confidence
    if scalp_grade == "SCALP_A+":
        confidence = 75
    elif scalp_grade == "SCALP_A":
        confidence = 60
    elif scalp_grade == "SCALP_B":
        confidence = 45
    else:  # SCALP_REJECT
        confidence = 20

    # Step 2: Signal strength adjustment
    if signal_strength == "STRONG":
        confidence += 15
    elif signal_strength == "NORMAL":
        confidence += 5
    elif signal_strength == "WEAK":
        confidence -= 5
    elif signal_strength == "REJECT":
        confidence = 20  # Floor for REJECT

    # Step 3: Data quality penalty
    if data_status == "STALE":
        confidence -= 20
    elif data_status == "UNAVAILABLE":
        confidence -= 25

    # Step 4: Volatility penalty
    if volatility_status == "HIGH":
        confidence -= 10
    elif volatility_status == "LOW":
        confidence -= 5

    # Step 5: Cost penalty (tiered)
    if estimated_roundtrip_cost_pct > 2.0:
        confidence -= 15
    elif estimated_roundtrip_cost_pct > 1.0:
        confidence -= 8
    elif estimated_roundtrip_cost_pct > 0.5:
        confidence -= 3

    # Step 6: Clamp to [20, 95]
    confidence = max(20, min(confidence, 95))

    return confidence


def _generate_reasons(
    long_strength: int,
    short_strength: int,
    scalp_grade: str,
    signal_strength: str,
    data_status: str,
    paper_allowed: bool,
    signals: List[str],
) -> List[str]:
    """
    Generate explicit reasons for the signal.

    Rules:
    - Use existing signals list if available
    - Max 3 reasons
    - Only field-based reasons if signals unavailable
    - No technical details (RSI/MACD) unless in signals list
    """

    reasons = []

    # If REJECT, no reasons
    if signal_strength == "REJECT":
        return []

    # If no existing signals, generate field-based reasons
    if not signals:
        # Grade-based reason
        if scalp_grade == "SCALP_A+":
            reasons.append("Grade A+ (highest confidence)")
        elif scalp_grade == "SCALP_A":
            reasons.append("Grade A (good confidence)")
        elif scalp_grade == "SCALP_B":
            reasons.append("Grade B (acceptable for paper)")

        # Directional reason
        if long_strength > short_strength + 5:
            reasons.append("LONG side stronger")
        elif short_strength > long_strength + 5:
            reasons.append("SHORT side stronger")

        # Data reason
        if data_status == "FRESH":
            reasons.append("Data fresh and up-to-date")
    else:
        # Use existing signals (from compute_scalp_score)
        # Take first 2-3 signals
        reasons = signals[:3]

    return reasons[:3]  # Max 3 reasons
