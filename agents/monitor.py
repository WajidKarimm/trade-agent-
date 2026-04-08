"""
Monitor Agent — the watchdog.
Runs continuously between cycles.
Watches open positions, P&L, drawdown.
Triggers stop-loss and sends Telegram alerts.
"""
from datetime import datetime
from loguru import logger

from config.settings import get_settings
from config.constants import MAX_STAKE_PCT_BANKROLL
from storage.db import get_open_trades, get_trade_stats
from storage.models import PortfolioState


# Hardcoded circuit breakers — LLM cannot override these
MAX_DAILY_LOSS_PCT = 0.10       # stop trading if we lose 10% in a day
MAX_DRAWDOWN_PCT   = 0.20       # halt if total drawdown exceeds 20%
MIN_WIN_RATE_AFTER = 20         # start checking win rate after 20 trades
MIN_WIN_RATE       = 0.45       # halt if win rate drops below 45%


class MonitorAgent:
    def __init__(self, bankroll_usd: float = 100.0):
        self.settings = get_settings()
        self.bankroll_usd = bankroll_usd
        self._halted = False
        self._halt_reason = ""
        self._notifier = None

    def _get_notifier(self):
        if self._notifier is None:
            try:
                from notifications.alerts import AlertManager
                self._notifier = AlertManager()
            except Exception as e:
                logger.warning(f"Notifications unavailable: {e}")
        return self._notifier

    def is_halted(self) -> bool:
        return self._halted

    def halt_reason(self) -> str:
        return self._halt_reason

    def check_circuit_breakers(self) -> tuple[bool, str]:
        """
        Check all circuit breakers. Returns (should_halt, reason).
        Called before every trade cycle.
        """
        if self._halted:
            return True, self._halt_reason

        stats = get_trade_stats()
        total_trades = stats["total_trades"]
        total_pnl = stats["total_pnl_usd"]
        win_rate = stats["win_rate"]

        # 1. Daily loss check
        if total_pnl < -(self.bankroll_usd * MAX_DAILY_LOSS_PCT):
            reason = f"Daily loss limit hit: P&L=${total_pnl:.2f}"
            self._trigger_halt(reason)
            return True, reason

        # 2. Drawdown check
        if total_pnl < -(self.bankroll_usd * MAX_DRAWDOWN_PCT):
            reason = f"Max drawdown exceeded: P&L=${total_pnl:.2f}"
            self._trigger_halt(reason)
            return True, reason

        # 3. Win rate check (only after enough trades)
        if total_trades >= MIN_WIN_RATE_AFTER and win_rate < MIN_WIN_RATE:
            reason = f"Win rate {win_rate:.1%} below minimum {MIN_WIN_RATE:.0%} after {total_trades} trades"
            self._trigger_halt(reason)
            return True, reason

        return False, ""

    def _trigger_halt(self, reason: str) -> None:
        """Trigger an emergency halt."""
        self._halted = True
        self._halt_reason = reason
        logger.critical(f"TRADING HALTED: {reason}")
        notifier = self._get_notifier()
        if notifier:
            try:
                import asyncio
                asyncio.create_task(notifier.send_halt_alert(reason))
            except Exception as e:
                logger.error(f"Failed to send halt alert: {e}")

    def get_status_summary(self) -> dict:
        """Return a summary dict for the dashboard."""
        stats = get_trade_stats()
        open_trades = get_open_trades()
        return {
            "halted": self._halted,
            "halt_reason": self._halt_reason,
            "mode": "LIVE" if self.settings.live_mode else "PAPER",
            "total_trades": stats["total_trades"],
            "win_rate": stats["win_rate"],
            "total_pnl_usd": stats["total_pnl_usd"],
            "open_positions": len(open_trades),
            "open_exposure_usd": sum(t["stake_usd"] for t in open_trades),
            "bankroll_usd": self.bankroll_usd,
            "checked_at": datetime.utcnow().isoformat(),
        }

    async def notify_trade(self, question: str, side: str, stake: float,
                           edge: float, mode: str) -> None:
        """Send Telegram notification for a new trade."""
        notifier = self._get_notifier()
        if notifier:
            try:
                await notifier.send_trade_alert(question, side, stake, edge, mode)
            except Exception as e:
                logger.warning(f"Trade notification failed: {e}")

    async def notify_arb(self, question: str, profit_cents: float,
                         arb_type: str) -> None:
        """Send Telegram notification for arb opportunity."""
        notifier = self._get_notifier()
        if notifier:
            try:
                await notifier.send_arb_alert(question, profit_cents, arb_type)
            except Exception as e:
                logger.warning(f"Arb notification failed: {e}")
