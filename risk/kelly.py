"""
Kelly Criterion bet sizing.
Uses FRACTIONAL Kelly (25%) to be conservative — standard practice.
Formula: f = (bp - q) / b
  b = odds received (1/price - 1)
  p = our probability estimate
  q = 1 - p
"""
from loguru import logger
from config.constants import KELLY_FRACTION, MAX_STAKE_PCT_BANKROLL


def kelly_stake(
    my_prob: float,
    market_price: float,
    bankroll_usd: float,
    kelly_fraction: float = KELLY_FRACTION,
) -> float:
    """
    Calculate the Kelly-optimal stake in USD.

    Args:
        my_prob: Our probability estimate (0.0 – 1.0)
        market_price: Current market price for the side we're buying (0.0 – 1.0)
        bankroll_usd: Total available capital
        kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)

    Returns:
        Recommended stake in USD (0.0 if no edge)
    """
    if market_price <= 0 or market_price >= 1:
        return 0.0

    # Odds in decimal format: how much we win per dollar wagered
    b = (1.0 / market_price) - 1.0
    p = my_prob
    q = 1.0 - p

    # Kelly formula
    kelly_full = (b * p - q) / b

    if kelly_full <= 0:
        logger.debug(f"Kelly negative ({kelly_full:.3f}) — no edge, skip")
        return 0.0

    # Apply fraction (conservative sizing)
    kelly_frac = kelly_full * kelly_fraction

    # Cap at max bankroll percentage
    kelly_capped = min(kelly_frac, MAX_STAKE_PCT_BANKROLL)

    stake = kelly_capped * bankroll_usd
    logger.debug(
        f"Kelly: prob={p:.3f} price={market_price:.3f} "
        f"full={kelly_full:.3f} frac={kelly_frac:.3f} "
        f"stake=${stake:.2f}"
    )
    return round(stake, 2)


def expected_value(my_prob: float, market_price: float) -> float:
    """
    Expected value of buying at market_price with estimated probability my_prob.
    EV > 0 means we have edge.
    """
    win_payout = (1.0 / market_price) - 1.0  # profit per $1 wagered
    ev = my_prob * win_payout - (1.0 - my_prob)
    return round(ev, 4)
