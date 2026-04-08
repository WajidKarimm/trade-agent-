"""
Hardcoded constants — these are safety rails.
The LLM cannot modify these at runtime. Change only here, manually.
"""

# Market selection
MAX_RESOLVE_DAYS: int = 5          # only trade markets resolving within N days
MIN_MARKET_VOLUME_USD: float = 500  # skip illiquid markets below this volume
MIN_YES_NO_LIQUIDITY: float = 50    # minimum liquidity on each side

# Arbitrage thresholds
ARB_MIN_PROFIT_CENTS: float = 2.0   # minimum cents profit to flag as arb
ARB_DUTCH_BOOK_MAX: float = 0.98    # YES + NO must sum below this to be arb

# Risk — NEVER remove these guards
MAX_STAKE_PCT_BANKROLL: float = 0.05  # max 5% of bankroll per trade
KELLY_FRACTION: float = 0.25          # use quarter-Kelly to be conservative
MIN_EDGE_TO_TRADE: float = 0.05       # minimum 5% edge required to trade

# Analyst
MIN_CONFIDENCE_TO_TRADE: float = 0.60  # analyst confidence threshold
MAX_ANALYST_RETRIES: int = 3

# Cycle
CYCLE_INTERVAL_SECONDS: int = 900   # 15 minutes
WEBSOCKET_RECONNECT_DELAY: int = 5

# Logging
LOG_LEVEL: str = "INFO"
