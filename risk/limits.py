"""
Hardcoded risk limits — the LLM NEVER touches these.
These are enforced deterministically in risk_manager.py.
Change values here only, manually, with full understanding.
"""
from config.settings import get_settings
from config.constants import (
    MAX_STAKE_PCT_BANKROLL,
    MIN_EDGE_TO_TRADE,
    MIN_CONFIDENCE_TO_TRADE,
    MAX_RESOLVE_DAYS,
)


def check_all_limits(
    stake_usd: float,
    edge: float,
    confidence: float,
    days_to_resolve: float,
    open_exposure_usd: float,
    bankroll_usd: float,
) -> tuple[bool, str]:
    """
    Run all risk checks. Returns (approved, rejection_reason).
    ALL checks must pass for a trade to be approved.
    """
    settings = get_settings()

    # 1. Minimum edge
    if abs(edge) < MIN_EDGE_TO_TRADE:
        return False, f"Edge {edge:.3f} below minimum {MIN_EDGE_TO_TRADE}"

    # 2. Minimum confidence
    if confidence < MIN_CONFIDENCE_TO_TRADE:
        return False, f"Confidence {confidence:.2f} below minimum {MIN_CONFIDENCE_TO_TRADE}"

    # 3. Market resolve window
    if days_to_resolve > MAX_RESOLVE_DAYS:
        return False, f"Market resolves in {days_to_resolve:.1f} days (max {MAX_RESOLVE_DAYS})"

    # 4. Per-trade stake cap
    max_stake = settings.max_stake_per_market_usd
    if stake_usd > max_stake:
        return False, f"Stake ${stake_usd:.2f} exceeds per-market cap ${max_stake}"

    # 5. Total exposure cap
    max_exposure = settings.max_total_exposure_usd
    if open_exposure_usd + stake_usd > max_exposure:
        return False, f"Would exceed total exposure cap ${max_exposure}"

    # 6. Bankroll percentage
    if bankroll_usd > 0 and stake_usd / bankroll_usd > MAX_STAKE_PCT_BANKROLL:
        pct = stake_usd / bankroll_usd
        return False, f"Stake is {pct:.1%} of bankroll (max {MAX_STAKE_PCT_BANKROLL:.0%})"

    # 7. Minimum stake (don't bother with tiny trades — fees eat them)
    if stake_usd < 1.0:
        return False, f"Stake ${stake_usd:.2f} too small (min $1.00)"

    return True, ""
