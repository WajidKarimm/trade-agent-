"""Tests for the arbitrage scanner."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from storage.models import MarketSnapshot, SignalType
from agents.arb_scanner import scan_dutch_book


def make_market(market_id: str, yes: float, no: float, volume: float = 1000.0) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        question=f"Test question for {market_id}?",
        yes_price=yes,
        no_price=no,
        volume_usd=volume,
        liquidity_usd=500.0,
        resolve_by=datetime.utcnow() + timedelta(days=3),
    )


@pytest.mark.asyncio
async def test_dutch_book_detected():
    """Should detect when YES + NO < 1.0."""
    markets = [make_market("m1", yes=0.45, no=0.50)]  # sum = 0.95 → 5¢ profit
    with patch("agents.arb_scanner.log_arb"):
        opps = await scan_dutch_book(markets)
    assert len(opps) == 1
    assert opps[0].arb_type == SignalType.ARB_DUTCH
    assert opps[0].profit_cents == pytest.approx(5.0, abs=0.1)


@pytest.mark.asyncio
async def test_no_arb_when_fair():
    """No arb when YES + NO = 1.0."""
    markets = [make_market("m2", yes=0.50, no=0.50)]  # sum = 1.0
    with patch("agents.arb_scanner.log_arb"):
        opps = await scan_dutch_book(markets)
    assert len(opps) == 0


@pytest.mark.asyncio
async def test_no_arb_below_threshold():
    """No arb when profit is below minimum threshold."""
    # sum = 0.99 → 1¢ profit — below ARB_MIN_PROFIT_CENTS (2.0)
    markets = [make_market("m3", yes=0.495, no=0.495)]
    with patch("agents.arb_scanner.log_arb"):
        opps = await scan_dutch_book(markets)
    assert len(opps) == 0


@pytest.mark.asyncio
async def test_multiple_arb_markets():
    """Should detect arb in multiple markets simultaneously."""
    markets = [
        make_market("m4", yes=0.44, no=0.50),  # 6¢ profit
        make_market("m5", yes=0.50, no=0.50),  # no arb
        make_market("m6", yes=0.43, no=0.52),  # 5¢ profit
    ]
    with patch("agents.arb_scanner.log_arb"):
        opps = await scan_dutch_book(markets)
    assert len(opps) == 2
