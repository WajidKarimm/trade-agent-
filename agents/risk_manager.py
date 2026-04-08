"""
Risk Manager Agent — pure deterministic logic, zero LLM.
Takes analyst signals and arb opportunities.
Runs them through Kelly sizing + hardcoded limits.
Outputs TradeDecision (approved/rejected with reason).
"""
from loguru import logger

from config.settings import get_settings
from risk.kelly import kelly_stake, expected_value
from risk.limits import check_all_limits
from risk.portfolio import get_portfolio_state
from storage.models import (
    AnalystSignal, ArbOpportunity, TradeDecision,
    Side, SignalType, MarketSnapshot
)


class RiskManagerAgent:
    def __init__(self, bankroll_usd: float = 100.0):
        self.settings = get_settings()
        self.bankroll_usd = bankroll_usd

    def evaluate_signal(
        self,
        signal: AnalystSignal,
        market: MarketSnapshot,
    ) -> TradeDecision:
        """Evaluate an analyst signal and return a trade decision."""
        portfolio = get_portfolio_state(self.bankroll_usd)

        # Determine entry price based on side
        entry_price = market.yes_price if signal.side == Side.YES else market.no_price
        my_prob = signal.my_prob_yes if signal.side == Side.YES else (1.0 - signal.my_prob_yes)

        # Kelly sizing
        stake = kelly_stake(
            my_prob=my_prob,
            market_price=entry_price,
            bankroll_usd=self.bankroll_usd,
            kelly_fraction=self.settings.kelly_fraction,
        )

        # Cap at per-market max
        stake = min(stake, self.settings.max_stake_per_market_usd)

        # Run all limit checks
        approved, reason = check_all_limits(
            stake_usd=stake,
            edge=signal.edge,
            confidence=signal.confidence,
            days_to_resolve=market.days_to_resolve,
            open_exposure_usd=portfolio.open_exposure_usd,
            bankroll_usd=self.bankroll_usd,
        )

        ev = expected_value(my_prob, entry_price)

        if approved:
            logger.success(
                f"APPROVED | {signal.side.value} ${stake:.2f} | "
                f"edge={signal.edge:.3f} ev={ev:.3f} | {market.question[:50]}"
            )
        else:
            logger.info(f"REJECTED | {reason} | {market.question[:50]}")

        return TradeDecision(
            market_id=signal.market_id,
            question=signal.question,
            approved=approved,
            side=signal.side,
            stake_usd=stake,
            edge=signal.edge,
            confidence=signal.confidence,
            signal_type=SignalType.ANALYST,
            rejection_reason=reason,
        )

    def evaluate_arb(
        self,
        opp: ArbOpportunity,
        market: MarketSnapshot,
    ) -> TradeDecision:
        """
        Arb opportunities get special treatment — lower bar, smaller stake.
        Dutch book arb is mathematically guaranteed; cross-venue has execution risk.
        """
        portfolio = get_portfolio_state(self.bankroll_usd)

        # For arb: use a fixed fraction of bankroll (don't need Kelly)
        if opp.arb_type == SignalType.ARB_DUTCH:
            # Dutch book: guaranteed — use 2% of bankroll or max stake, whichever is smaller
            stake = min(self.bankroll_usd * 0.02, self.settings.max_stake_per_market_usd)
            confidence = 0.99  # mathematically certain
            edge = opp.profit_cents / 100.0
        else:
            # Cross-venue: execution friction reduces certainty — smaller stake
            stake = min(self.bankroll_usd * 0.01, self.settings.max_stake_per_market_usd / 2)
            confidence = 0.75
            edge = (opp.profit_cents - 2.0) / 100.0  # subtract estimated fees

        if edge <= 0:
            return TradeDecision(
                market_id=opp.market_id,
                question=opp.question,
                approved=False,
                side=Side.YES,
                stake_usd=stake,
                edge=edge,
                confidence=confidence,
                signal_type=opp.arb_type,
                rejection_reason="Edge disappears after fee estimation",
            )

        # Check exposure limits
        approved, reason = check_all_limits(
            stake_usd=stake,
            edge=edge,
            confidence=confidence,
            days_to_resolve=market.days_to_resolve,
            open_exposure_usd=portfolio.open_exposure_usd,
            bankroll_usd=self.bankroll_usd,
        )

        if approved:
            logger.success(
                f"ARB APPROVED | {opp.arb_type.value} | ${stake:.2f} | "
                f"profit={opp.profit_cents:.1f}¢ | {opp.question[:50]}"
            )

        return TradeDecision(
            market_id=opp.market_id,
            question=opp.question,
            approved=approved,
            side=Side.YES,  # arb buys both sides; executor handles this
            stake_usd=stake,
            edge=edge,
            confidence=confidence,
            signal_type=opp.arb_type,
            rejection_reason=reason,
        )
