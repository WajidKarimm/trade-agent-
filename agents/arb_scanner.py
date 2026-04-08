"""
Arbitrage Scanner — pure math, zero AI, zero cost.
Two strategies:
  1. Dutch Book: YES + NO both under 50¢ on Polymarket → guaranteed profit
  2. Cross-venue: Same market cheaper on Kalshi → buy there, sell here (or vice versa)
"""
import asyncio
from loguru import logger

from config.constants import ARB_DUTCH_BOOK_MAX, ARB_MIN_PROFIT_CENTS
from data.polymarket_client import PolymarketClient
from data.kalshi_client import KalshiClient
from storage.models import ArbOpportunity, SignalType, MarketSnapshot
from storage.db import log_arb


async def scan_dutch_book(markets: list[MarketSnapshot]) -> list[ArbOpportunity]:
    """
    Dutch Book: if YES_price + NO_price < 1.0, buying both guarantees profit.
    Example: YES=0.45, NO=0.52 → spread=0.97 → 3 cents profit per dollar.
    """
    opportunities = []
    for market in markets:
        spread = market.yes_price + market.no_price
        if spread < ARB_DUTCH_BOOK_MAX:
            profit_cents = (1.0 - spread) * 100
            if profit_cents >= ARB_MIN_PROFIT_CENTS:
                opp = ArbOpportunity(
                    market_id=market.market_id,
                    question=market.question,
                    arb_type=SignalType.ARB_DUTCH,
                    yes_price=market.yes_price,
                    no_price=market.no_price,
                    profit_cents=profit_cents,
                    venue_a="polymarket",
                )
                opportunities.append(opp)
                logger.info(
                    f"DUTCH BOOK ARB | {market.question[:50]} | "
                    f"YES={market.yes_price:.2f} NO={market.no_price:.2f} | "
                    f"Profit={profit_cents:.1f}¢"
                )
                log_arb(
                    market.market_id, market.question, "ARB_DUTCH",
                    market.yes_price, market.no_price, profit_cents
                )
    return opportunities


async def scan_cross_venue(markets: list[MarketSnapshot]) -> list[ArbOpportunity]:
    """
    Cross-venue arb: same market priced differently on Polymarket vs Kalshi.
    If Polymarket YES=0.55, Kalshi YES=0.60 → gap=5¢ → potential arb.
    Note: execution friction (fees, slippage) reduces real profit.
    """
    opportunities = []

    async with KalshiClient() as kalshi:
        for market in markets[:30]:  # check top 30 markets only (API courtesy)
            # Build a Kalshi search query from the market question keywords
            keywords = market.question.split()[:3]
            kalshi_matches = await kalshi.search_markets(" ".join(keywords))

            for km in kalshi_matches[:2]:
                kalshi_ticker = km.get("ticker", "")
                kalshi_price = await kalshi.get_market_price(kalshi_ticker)

                if kalshi_price is None:
                    continue

                gap = abs(market.yes_price - kalshi_price)
                profit_cents = gap * 100

                # Only flag if gap is meaningful after estimated fees (~2%)
                if profit_cents >= 4.0:
                    # Determine which side to buy where
                    if market.yes_price < kalshi_price:
                        description = f"Buy YES on Polymarket ({market.yes_price:.2f}), sell on Kalshi ({kalshi_price:.2f})"
                    else:
                        description = f"Buy YES on Kalshi ({kalshi_price:.2f}), sell on Polymarket ({market.yes_price:.2f})"

                    opp = ArbOpportunity(
                        market_id=market.market_id,
                        question=market.question,
                        arb_type=SignalType.ARB_CROSS,
                        yes_price=market.yes_price,
                        no_price=market.no_price,
                        profit_cents=profit_cents,
                        venue_a="polymarket",
                        venue_b=f"kalshi:{kalshi_ticker}",
                        price_venue_b=kalshi_price,
                    )
                    opportunities.append(opp)
                    logger.info(
                        f"CROSS-VENUE ARB | {market.question[:50]} | "
                        f"Gap={profit_cents:.1f}¢ | {description}"
                    )
                    log_arb(
                        market.market_id, market.question, "ARB_CROSS",
                        market.yes_price, market.no_price, profit_cents,
                        venue_b=f"kalshi:{kalshi_ticker}"
                    )

    return opportunities


async def run_arb_scan(markets: list[MarketSnapshot]) -> list[ArbOpportunity]:
    """Run both arb scanners and return all opportunities found."""
    dutch, cross = await asyncio.gather(
        scan_dutch_book(markets),
        scan_cross_venue(markets),
    )
    all_opps = dutch + cross
    if all_opps:
        logger.success(f"Arb scan complete: {len(all_opps)} opportunities found")
    else:
        logger.info("Arb scan complete: no opportunities found this cycle")
    return all_opps
