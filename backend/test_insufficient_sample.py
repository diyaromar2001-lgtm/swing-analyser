"""
Test: INSUFFICIENT_SAMPLE vs NO_EDGE distinction

Validate:
1. 0 trades → INSUFFICIENT_SAMPLE (not NO_EDGE)
2. 6 trades → INSUFFICIENT_SAMPLE (below MIN_TRADES=8)
3. 8 trades, bad metrics (PF < 1.0) → NO_EDGE
4. Authorization still strict: INSUFFICIENT_SAMPLE blocks trading
"""

import sys
sys.path.insert(0, ".")

from crypto_edge import _status_from
from crypto_service import compute_crypto_execution_authorization


def test_insufficient_sample_zero_trades():
    """Test: 0 trades should return INSUFFICIENT_SAMPLE, not NO_EDGE"""
    result = {
        "overfit_warning": False,
        "total_trades": 0,
        "profit_factor": 0.0,
        "test_pf": 0.0,
        "expectancy": 0.0,
        "max_drawdown_pct": 0.0,
    }
    status = _status_from(result)
    assert status == "INSUFFICIENT_SAMPLE", f"Expected INSUFFICIENT_SAMPLE for 0 trades, got {status}"
    print("[OK] Test 1: 0 trades (0) -> INSUFFICIENT_SAMPLE")


def test_insufficient_sample_six_trades():
    """Test: 6 trades (< MIN_TRADES=8) should return INSUFFICIENT_SAMPLE"""
    result = {
        "overfit_warning": False,
        "total_trades": 6,
        "profit_factor": 1.5,  # Good metrics
        "test_pf": 1.2,
        "expectancy": 0.5,
        "max_drawdown_pct": -20.0,
    }
    status = _status_from(result)
    assert status == "INSUFFICIENT_SAMPLE", f"Expected INSUFFICIENT_SAMPLE for 6 trades, got {status}"
    print("[OK] Test 2: 6 trades (with good metrics) -> INSUFFICIENT_SAMPLE")


def test_no_edge_sufficient_sample_bad_metrics():
    """Test: 10 trades but bad PF should return NO_EDGE, not INSUFFICIENT_SAMPLE"""
    result = {
        "overfit_warning": False,
        "total_trades": 10,  # >= 8
        "profit_factor": 0.8,  # BAD (< 1.0)
        "test_pf": 0.5,
        "expectancy": -0.2,
        "max_drawdown_pct": -25.0,
    }
    status = _status_from(result)
    assert status == "NO_EDGE", f"Expected NO_EDGE for 10 trades with PF=0.8, got {status}"
    print("[OK] Test 3: 10 trades with bad metrics (PF<1.0) -> NO_EDGE")


def test_valid_edge_sufficient_sample_good_metrics():
    """Test: 15 trades with good metrics should return VALID_EDGE"""
    result = {
        "overfit_warning": False,
        "total_trades": 15,  # >= 12
        "profit_factor": 1.25,
        "test_pf": 1.05,
        "expectancy": 0.3,
        "max_drawdown_pct": -30.0,
    }
    status = _status_from(result)
    assert status == "VALID_EDGE", f"Expected VALID_EDGE for 15 trades with good metrics, got {status}"
    print("[OK] Test 4: 15 trades with good metrics -> VALID_EDGE")


def test_authorization_blocks_insufficient_sample():
    """Test: INSUFFICIENT_SAMPLE should block trading authorization"""
    auth_result = compute_crypto_execution_authorization(
        symbol="BTC",
        regime="CRYPTO_BULL",
        setup_status="READY",
        setup_grade="A+",
        edge_status="INSUFFICIENT_SAMPLE",  # Should block
        total_trades=0,
        overfit_warning=False,
        rr_ratio=2.0,
        dist_entry_pct=1.0,
        volatility_pct=5.0,
        stop_loss=40000,
        tp1=45000,
        tp2=50000,
        final_decision="BUY NOW",
        regime_data={
            "btc_price": 42500,
            "btc_sma200": 40000,
            "eth_price": 2500,
            "eth_sma200": 2400,
            "crypto_regime": "CRYPTO_BULL",
            "data_status": "OK",
            "confidence": 95,
        },
    )

    # Should NOT be authorized (INSUFFICIENT_SAMPLE is a hard block)
    assert not auth_result["crypto_execution_authorized"], \
        "INSUFFICIENT_SAMPLE should block execution authorization"

    # Should be watchlist eligible
    assert auth_result["crypto_watchlist_eligible"], \
        "INSUFFICIENT_SAMPLE should allow watchlist"

    # Edge check should be in blocked reasons
    blocked = auth_result["crypto_blocked_reasons"]
    edge_blocked = any("insufficient" in r.lower() for r in blocked)
    assert edge_blocked, f"Expected edge insufficient message in blocked reasons, got: {blocked}"

    print("[OK] Test 5: INSUFFICIENT_SAMPLE blocks trading, allows watchlist")


def test_authorization_allows_valid_edge():
    """Test: VALID_EDGE with all conditions met should authorize trading"""
    auth_result = compute_crypto_execution_authorization(
        symbol="BTC",
        regime="CRYPTO_BULL",
        setup_status="READY",
        setup_grade="A+",
        edge_status="VALID_EDGE",  # Should allow
        total_trades=15,
        overfit_warning=False,
        rr_ratio=2.0,
        dist_entry_pct=1.0,
        volatility_pct=5.0,
        stop_loss=40000,
        tp1=45000,
        tp2=50000,
        final_decision="BUY NOW",
        regime_data={
            "btc_price": 42500,
            "btc_sma200": 40000,
            "eth_price": 2500,
            "eth_sma200": 2400,
            "crypto_regime": "CRYPTO_BULL",
            "data_status": "OK",
            "confidence": 95,
        },
    )

    # Should be authorized
    assert auth_result["crypto_execution_authorized"], \
        "VALID_EDGE with all conditions should authorize trading"

    # No blocked reasons
    assert len(auth_result["crypto_blocked_reasons"]) == 0, \
        f"Should have no blocked reasons, got: {auth_result['crypto_blocked_reasons']}"

    print("[OK] Test 6: VALID_EDGE with all conditions -> authorized")


if __name__ == "__main__":
    print("="*60)
    print("Testing INSUFFICIENT_SAMPLE vs NO_EDGE distinction")
    print("="*60)

    test_insufficient_sample_zero_trades()
    test_insufficient_sample_six_trades()
    test_no_edge_sufficient_sample_bad_metrics()
    test_valid_edge_sufficient_sample_good_metrics()
    test_authorization_blocks_insufficient_sample()
    test_authorization_allows_valid_edge()

    print("="*60)
    print("[OK] All tests passed!")
    print("="*60)
