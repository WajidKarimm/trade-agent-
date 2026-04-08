"""
Portfolio state tracker — reads from SQLite.
Provides bankroll, open exposure, P&L to the risk layer.
"""
from loguru import logger
from storage.db import get_open_trades, get_trade_stats
from storage.models import PortfolioState, TradeMode


def get_portfolio_state(bankroll_usd: float = 100.0) -> PortfolioState:
    """
    Compute current portfolio state from trade records.
    bankroll_usd: your starting/current capital (set in .env or pass dynamically)
    """
    open_trades = get_open_trades()
    stats = get_trade_stats()

    open_exposure = sum(t["stake_usd"] for t in open_trades)
    unrealized_pnl = 0.0  # would need price feed to compute accurately

    return PortfolioState(
        total_bankroll_usd=bankroll_usd,
        open_exposure_usd=open_exposure,
        unrealized_pnl_usd=unrealized_pnl,
        realized_pnl_usd=stats["total_pnl_usd"],
        win_rate=stats["win_rate"],
        total_trades=stats["total_trades"],
        open_positions=len(open_trades),
    )
