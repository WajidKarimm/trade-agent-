"""Tests for Kelly criterion sizing."""
import pytest
from risk.kelly import kelly_stake, expected_value


def test_kelly_positive_edge():
    """When we have edge, Kelly should return a positive stake."""
    stake = kelly_stake(my_prob=0.65, market_price=0.50, bankroll_usd=100.0)
    assert stake > 0


def test_kelly_no_edge():
    """When market price equals our estimate, Kelly should return 0."""
    stake = kelly_stake(my_prob=0.50, market_price=0.50, bankroll_usd=100.0)
    assert stake == 0.0


def test_kelly_negative_edge():
    """When market is priced higher than our estimate, Kelly returns 0."""
    stake = kelly_stake(my_prob=0.40, market_price=0.60, bankroll_usd=100.0)
    assert stake == 0.0


def test_kelly_respects_max_pct():
    """Kelly stake should never exceed MAX_STAKE_PCT_BANKROLL of bankroll."""
    from config.constants import MAX_STAKE_PCT_BANKROLL
    stake = kelly_stake(my_prob=0.99, market_price=0.01, bankroll_usd=1000.0)
    assert stake <= 1000.0 * MAX_STAKE_PCT_BANKROLL + 0.01  # small float tolerance


def test_kelly_scales_with_bankroll():
    """Stakes should scale proportionally with bankroll."""
    stake_100 = kelly_stake(0.65, 0.50, 100.0)
    stake_200 = kelly_stake(0.65, 0.50, 200.0)
    assert abs(stake_200 - stake_100 * 2) < 0.01


def test_expected_value_positive():
    ev = expected_value(my_prob=0.70, market_price=0.50)
    assert ev > 0


def test_expected_value_negative():
    ev = expected_value(my_prob=0.30, market_price=0.60)
    assert ev < 0


def test_expected_value_zero_edge():
    """At fair price, EV should be near zero."""
    ev = expected_value(my_prob=0.50, market_price=0.50)
    assert abs(ev) < 0.01
