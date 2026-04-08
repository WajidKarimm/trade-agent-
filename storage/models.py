"""
Pydantic data models — the lingua franca between all agents.
Every agent speaks these types. No raw dicts across boundaries.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Side(str, Enum):
    YES = "YES"
    NO = "NO"


class TradeMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class SignalType(str, Enum):
    ANALYST = "ANALYST"       # Claude probability estimate
    ARB_DUTCH = "ARB_DUTCH"   # Dutch book (YES+NO < 1.0)
    ARB_CROSS = "ARB_CROSS"   # Cross-venue price gap


class MarketSnapshot(BaseModel):
    """Live state of a single Polymarket market."""
    market_id: str
    question: str
    yes_price: float          # 0.0 – 1.0 (cents / 100)
    no_price: float
    volume_usd: float
    liquidity_usd: float
    resolve_by: datetime
    category: str = ""
    description: str = ""
    resolved: bool = False
    outcome: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def spread(self) -> float:
        return self.yes_price + self.no_price

    @property
    def days_to_resolve(self) -> float:
        delta = self.resolve_by - datetime.utcnow()
        return max(0.0, delta.total_seconds() / 86400)


class AnalystSignal(BaseModel):
    """Output from the Analyst agent."""
    market_id: str
    question: str
    my_prob_yes: float        # Claude's probability estimate
    market_prob_yes: float    # current market price
    edge: float               # my_prob - market_prob (signed)
    confidence: float         # 0.0 – 1.0
    side: Side                # which side has the edge
    reasoning: str            # Claude's reasoning (for audit log)
    news_context: str = ""    # retrieved RAG context
    signal_type: SignalType = SignalType.ANALYST
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ArbOpportunity(BaseModel):
    """Output from the Arb Scanner."""
    market_id: str
    question: str
    arb_type: SignalType      # ARB_DUTCH or ARB_CROSS
    yes_price: float
    no_price: float
    profit_cents: float       # guaranteed profit in cents per $1 wagered
    venue_a: str = "polymarket"
    venue_b: str = ""         # populated for cross-venue arb
    price_venue_b: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeDecision(BaseModel):
    """Output from the Risk Manager — the final go/no-go."""
    market_id: str
    question: str
    approved: bool
    side: Side
    stake_usd: float
    edge: float
    confidence: float
    signal_type: SignalType
    rejection_reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeRecord(BaseModel):
    """Final record of a trade — paper or live."""
    id: Optional[int] = None
    market_id: str
    question: str
    side: Side
    stake_usd: float
    entry_price: float
    edge: float
    confidence: float
    signal_type: SignalType
    mode: TradeMode
    tx_hash: str = ""         # populated for live trades
    fill_price: Optional[float] = None
    pnl_usd: Optional[float] = None
    resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class PortfolioState(BaseModel):
    """Current portfolio snapshot."""
    total_bankroll_usd: float
    open_exposure_usd: float
    unrealized_pnl_usd: float
    realized_pnl_usd: float
    win_rate: float
    total_trades: int
    open_positions: int
    updated_at: datetime = Field(default_factory=datetime.utcnow)
