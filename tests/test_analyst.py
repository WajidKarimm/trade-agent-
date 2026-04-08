"""Tests for the analyst agent (mocked Claude responses)."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from storage.models import MarketSnapshot, Side


def make_market() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="test-market-001",
        question="Will the Fed cut rates in June 2025?",
        yes_price=0.45,
        no_price=0.55,
        volume_usd=50000.0,
        liquidity_usd=10000.0,
        resolve_by=datetime.utcnow() + timedelta(days=3),
        category="Economics",
        description="Federal Reserve rate decision",
    )


MOCK_CLAUDE_RESPONSE = json.dumps({
    "probability_yes": 0.62,
    "confidence": 0.72,
    "key_factors": ["Recent inflation data", "Fed minutes", "Employment numbers"],
    "bull_case": "Inflation cooling faster than expected",
    "bear_case": "Labor market remains too strong",
    "reasoning": "Based on recent macro data, a rate cut appears more likely than market implies."
})


@pytest.mark.asyncio
async def test_analyst_returns_signal():
    """Analyst should return a valid signal for a healthy market."""
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=MOCK_CLAUDE_RESPONSE)]
        mock_client.messages.create.return_value = mock_message

        with patch("agents.analyst.fetch_market_news", new_callable=AsyncMock, return_value=[]):
            from agents.analyst import AnalystAgent
            agent = AnalystAgent()
            market = make_market()
            signal = await agent.analyse_market(market, news_items=[])

    assert signal is not None
    assert signal.my_prob_yes == pytest.approx(0.62)
    assert signal.confidence == pytest.approx(0.72)
    assert signal.edge > 0  # 0.62 > market price 0.45
    assert signal.side == Side.YES


@pytest.mark.asyncio
async def test_analyst_detects_no_side():
    """When our prob is lower than market, analyst should flag NO side."""
    low_prob_response = json.dumps({
        "probability_yes": 0.25,
        "confidence": 0.80,
        "key_factors": ["factor"],
        "bull_case": "small",
        "bear_case": "large",
        "reasoning": "Market overestimates probability."
    })

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=low_prob_response)]
        mock_client.messages.create.return_value = mock_message

        with patch("agents.analyst.fetch_market_news", new_callable=AsyncMock, return_value=[]):
            from agents.analyst import AnalystAgent
            agent = AnalystAgent()
            market = make_market()
            signal = await agent.analyse_market(market, news_items=[])

    assert signal is not None
    assert signal.side == Side.NO
