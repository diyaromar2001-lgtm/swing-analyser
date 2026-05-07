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

from typing import Dict, List, Any, Optional, Literal


def determine_scalp_side(long_score: float, short_score: float) -> Literal["LONG", "SHORT", "NONE"]:
    """
    Centralized rule for determining tradeable side.

    Used consistently across crypto_scalp_service and crypto_signal_enhancer.

    Prudent threshold (conservative):
    - LONG if: long_score >= 50 AND long_score >= short_score + 10
    - SHORT if: short_score >= 50 AND short_score >= long_score + 10
    - NONE otherwise (conflicting or unclear direction)

    Args:
        long_score: Long directional bias (0-100)
        short_score: Short directional bias (0-100)

    Returns:
        "LONG", "SHORT", or "NONE"
    """
    if long_score >= 50 and long_score >= short_score + 10:
        return "LONG"
    elif short_score >= 50 and short_score >= long_score + 10:
        return "SHORT"
    else:
        return "NONE"


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
    data_quality_status: str,
    data_quality_blocked: bool,
    spread_bps: int,
    estimated_roundtrip_cost_pct: float,
    paper_allowed: bool,
    blocked_reasons: List[str],
    signals: List[str],
    warnings: List[str],
) -> EnhancedSignal:
    """
    Enhance crypto scalp signal with strength, confidence, and clarity (Phase 3A).

    Separates HARD BLOCKERS (critical failures) from SOFT WARNINGS (penalties):
    - Hard blockers: data_quality BLOCKED, grade REJECT, data UNAVAILABLE/STALE
    - Soft warnings: ATR, Volume, Data Quality WARNING, no clear direction

    Args:
        long_score: LONG directional bias (0-100) from crypto_scalp_score
        short_score: SHORT directional bias (0-100) from crypto_scalp_score
        scalp_grade: Grade from crypto_scalp_score (SCALP_A+/A/B/REJECT)
        tier: Liquidity tier (1/2/3)
        data_status: FRESH/STALE/UNAVAILABLE
        volatility_status: NORMAL/HIGH/LOW
        spread_status: OK/WARNING/UNAVAILABLE
        data_quality_status: OK/WARNING/BLOCKED (intraday vs snapshot divergence)
        data_quality_blocked: True if divergence > 10%
        spread_bps: Bid-ask spread in basis points
        estimated_roundtrip_cost_pct: Total transaction cost
        paper_allowed: Preliminary check from service (refined here)
        blocked_reasons: List of HARD BLOCKERS only (not soft warnings)
        signals: Existing signals from compute_scalp_score
        warnings: Existing SOFT WARNINGS (ATR, Volume, DQ WARNING, etc.)

    Returns:
        EnhancedSignal with all enhancement fields
    """

    # Initialize warning collection (copy existing, add new)
    all_warnings = list(warnings) if warnings else []

    # ─ STEP 1A: Determine preferred_side BEFORE applying penalties ──
    # Use centralized rule to determine direction clarity
    # This ensures consistent thresholds across service and enhancer
    # Rule: LONG if long_score >= 50 AND delta >= 10, etc.
    preferred_side = determine_scalp_side(long_score, short_score)

    # Add warning if direction is unclear (NONE)
    if preferred_side == "NONE":
        all_warnings.append("Conflicting signals or unclear direction")

    # ─ STEP 1B: Calculate long_strength and short_strength with soft penalties ──
    long_strength = long_score
    short_strength = short_score

    # Apply soft warning penalties from warnings list
    # These reduce strength but don't auto-reject
    for warning in (warnings or []):
        warning_lower = warning.lower()

        # Very low ATR penalty
        if "very low atr" in warning_lower or "dead market" in warning_lower:
            long_strength = max(long_strength - 15, 0)
            short_strength = max(short_strength - 15, 0)

        # Volume declining penalty
        if "volume declining" in warning_lower:
            long_strength = max(long_strength - 10, 0)
            short_strength = max(short_strength - 10, 0)

        # Data quality warning penalty
        if "data quality warning" in warning_lower or "intraday divergence" in warning_lower:
            long_strength = max(long_strength - 10, 0)
            short_strength = max(short_strength - 10, 0)

        # Low volatility penalty
        if "low volatility" in warning_lower and "very low" not in warning_lower:
            long_strength = max(long_strength - 5, 0)
            short_strength = max(short_strength - 5, 0)

        # No clear direction soft warning
        if "no clear" in warning_lower and "long or short" in warning_lower:
            # Reduce slightly but don't eliminate entirely
            long_strength = max(long_strength - 10, 0)
            short_strength = max(short_strength - 10, 0)

    # Hard data quality penalty (if status is STALE/UNAVAILABLE - not BLOCKED which is hard blocker)
    if data_status == "STALE":
        long_strength = max(long_strength - 15, 0)
        short_strength = max(short_strength - 15, 0)
    elif data_status == "UNAVAILABLE":
        long_strength = max(long_strength - 25, 0)
        short_strength = max(short_strength - 25, 0)

    # Cost penalty (tiered)
    if estimated_roundtrip_cost_pct > 2.0:
        long_strength = max(long_strength - 15, 0)
        short_strength = max(short_strength - 15, 0)
    elif estimated_roundtrip_cost_pct > 1.0:
        long_strength = max(long_strength - 10, 0)
        short_strength = max(short_strength - 10, 0)
    elif estimated_roundtrip_cost_pct > 0.5:
        long_strength = max(long_strength - 5, 0)
        short_strength = max(short_strength - 5, 0)

    # Spread penalty
    if spread_status == "WARNING":
        long_strength = max(long_strength - 5, 0)
        short_strength = max(short_strength - 5, 0)

    # Clamp to valid range
    long_strength = max(0, min(long_strength, 100))
    short_strength = max(0, min(short_strength, 100))

    # ─ STEP 3: Classify signal_strength ──
    signal_strength = _classify_signal_strength(
        long_strength=long_strength,
        short_strength=short_strength,
        scalp_grade=scalp_grade,
        data_status=data_status,
        data_quality_blocked=data_quality_blocked,
        blocked_reasons=blocked_reasons,
        preferred_side=preferred_side,  # Enforce: if NONE, max is WEAK
    )

    # ─ STEP 4: Calculate confidence_score ──
    confidence_score = _calculate_confidence(
        scalp_grade=scalp_grade,
        signal_strength=signal_strength,
        data_status=data_status,
        volatility_status=volatility_status,
        estimated_roundtrip_cost_pct=estimated_roundtrip_cost_pct,
        preferred_side=preferred_side,
        data_quality_status=data_quality_status,
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

    # ─ STEP 7: Finalize paper_allowed based on comprehensive rules ──
    # Paper trading requires: data FRESH, no DQ BLOCKED, good grade, clear side,
    # confidence >= 40, signal NORMAL/STRONG, no hard blockers
    final_paper_allowed = (
        data_status == "FRESH"
        and not data_quality_blocked
        and scalp_grade in ("SCALP_A+", "SCALP_A", "SCALP_B")
        and preferred_side in ("LONG", "SHORT")
        and confidence_score >= 40
        and signal_strength in ("NORMAL", "STRONG")
        and not blocked_reasons  # No hard blockers
        and paper_allowed  # Respect preliminary check from service
    )

    return EnhancedSignal(
        long_strength=long_strength,
        short_strength=short_strength,
        preferred_side=preferred_side,
        signal_strength=signal_strength,
        confidence_score=confidence_score,
        signal_reasons=signal_reasons,
        signal_warnings=all_warnings,
        paper_allowed=final_paper_allowed,
    )


def _classify_signal_strength(
    long_strength: int,
    short_strength: int,
    scalp_grade: str,
    data_status: str,
    data_quality_blocked: bool,
    blocked_reasons: List[str],
    preferred_side: str = "NONE",  # LONG, SHORT, or NONE
) -> str:
    """
    Classify signal strength: STRONG / NORMAL / WEAK / REJECT

    Critical rule: If preferred_side=NONE (unclear direction), max is WEAK (never NORMAL/STRONG).

    Hard blocker rules (immediate REJECT):
    - scalp_grade == "SCALP_REJECT"
    - data_quality_blocked == True (>10% divergence)
    - data_status == "UNAVAILABLE" or "STALE"
    - blocked_reasons contains critical hard blockers

    Score-based classification (if no hard blockers):
    - STRONG: max_strength >= 75 AND grade in [A+, A] AND preferred_side in [LONG, SHORT]
    - NORMAL: max_strength >= 55 AND grade in [A+, A, B] AND preferred_side in [LONG, SHORT]
    - WEAK: max_strength >= 35
    - REJECT: otherwise
    """

    # Hard blocker checks - these are critical failures
    if scalp_grade == "SCALP_REJECT":
        return "REJECT"

    if data_quality_blocked:
        return "REJECT"  # Data quality BLOCKED is a critical hard blocker

    if data_status == "UNAVAILABLE":
        return "REJECT"

    if data_status == "STALE":
        return "REJECT"  # Conservative: stale data = reject

    if blocked_reasons and "Grade" in " ".join(blocked_reasons):
        # Grade-based hard blockers
        return "REJECT"

    # Score-based classification (soft warnings are applied as penalties, not auto-rejects)
    max_strength = max(long_strength, short_strength)

    # CRITICAL: If preferred_side is NONE (unclear direction), cap at WEAK
    if preferred_side == "NONE":
        # Unclear direction - max is WEAK, never NORMAL/STRONG
        if max_strength >= 35:
            return "WEAK"
        else:
            return "REJECT"

    # Direction is clear (LONG or SHORT) - allow full range
    if max_strength >= 75 and scalp_grade in ["SCALP_A+", "SCALP_A"]:
        return "STRONG"

    elif max_strength >= 55 and scalp_grade in ["SCALP_A+", "SCALP_A", "SCALP_B"]:
        return "NORMAL"

    elif max_strength >= 35:
        return "WEAK"

    else:
        return "REJECT"


def _calculate_confidence(
    scalp_grade: str,
    signal_strength: str,
    data_status: str,
    volatility_status: str,
    estimated_roundtrip_cost_pct: float,
    preferred_side: str,
    data_quality_status: str,
) -> int:
    """
    Calculate confidence score (0-100) using progressive formula.

    Creates variation based on grade, direction clarity, and soft penalties.
    No uniform floor at 20 - confidence reflects actual signal quality.

    Formula:
    1. Grade + Side base (A+/LONG 80, A/LONG 65, B/LONG 50, LONG/NONE 35, etc.)
    2. Soft penalties:
       - Very low ATR: -15
       - Volume declining: -10
       - Data Quality WARNING: -10
       - Low volatility (if not already from ATR): -5
       - No clear direction (side=NONE): -5 to -15
       - Data STALE: -15
       - Data UNAVAILABLE: -25
       - High costs: -5 to -15
    3. Signal strength adjustment (if not already REJECT):
       - STRONG: +10
       - NORMAL: +0
       - WEAK: -10
    4. Clamp to [0, 100]
    """

    # Step 1: Grade + Side base confidence
    # Higher base for clear directions, lower for NONE
    if scalp_grade == "SCALP_A+":
        if preferred_side in ("LONG", "SHORT"):
            confidence = 80
        else:  # NONE
            confidence = 35
    elif scalp_grade == "SCALP_A":
        if preferred_side in ("LONG", "SHORT"):
            confidence = 65
        else:  # NONE
            confidence = 25
    elif scalp_grade == "SCALP_B":
        if preferred_side in ("LONG", "SHORT"):
            confidence = 50
        else:  # NONE
            confidence = 20
    else:  # SCALP_REJECT
        confidence = 20

    # Step 2: Signal strength adjustment (before penalties for transparency)
    if signal_strength == "STRONG":
        confidence += 10
    elif signal_strength == "NORMAL":
        confidence += 0  # No adjustment
    elif signal_strength == "WEAK":
        confidence -= 10
    elif signal_strength == "REJECT":
        confidence = max(confidence, 20)  # Floor at 20 for REJECT, but don't reduce if already < 20

    # Step 3: Data quality penalties
    if data_status == "STALE":
        confidence -= 15
    elif data_status == "UNAVAILABLE":
        confidence -= 25

    if data_quality_status == "WARNING":
        confidence -= 10  # Soft penalty for data quality warning (5-10% divergence)

    # Step 4: Volatility penalty
    if volatility_status == "HIGH":
        confidence -= 10
    elif volatility_status == "LOW":
        confidence -= 5

    # Step 5: Cost penalty (tiered)
    if estimated_roundtrip_cost_pct > 2.0:
        confidence -= 15
    elif estimated_roundtrip_cost_pct > 1.0:
        confidence -= 10
    elif estimated_roundtrip_cost_pct > 0.5:
        confidence -= 5

    # Step 6: Clamp to [0, 100]
    confidence = max(0, min(confidence, 100))

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
