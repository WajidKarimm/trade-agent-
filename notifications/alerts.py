"""
Alert templates — all notification logic in one place.
Uses TelegramBot as the delivery layer.
"""
from datetime import datetime
from loguru import logger
from notifications.telegram_bot import TelegramBot


class AlertManager:
    def __init__(self):
        self.bot = TelegramBot()

    async def send_trade_alert(
        self,
        question: str,
        side: str,
        stake_usd: float,
        edge: float,
        mode: str,
    ) -> None:
        mode_tag = "📄 PAPER" if mode == "PAPER" else "💰 LIVE"
        msg = (
            f"{mode_tag} TRADE\n"
            f"<b>{question[:80]}</b>\n"
            f"Side: {side} | Stake: ${stake_usd:.2f}\n"
            f"Edge: {edge:.1%} | {datetime.utcnow().strftime('%H:%M UTC')}"
        )
        await self.bot.send(msg)

    async def send_arb_alert(
        self,
        question: str,
        profit_cents: float,
        arb_type: str,
    ) -> None:
        msg = (
            f"⚡ ARB FOUND [{arb_type}]\n"
            f"<b>{question[:80]}</b>\n"
            f"Profit: {profit_cents:.1f}¢ per $1 wagered\n"
            f"{datetime.utcnow().strftime('%H:%M UTC')}"
        )
        await self.bot.send(msg)

    async def send_halt_alert(self, reason: str) -> None:
        msg = (
            f"🚨 TRADING HALTED\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Manual review required."
        )
        await self.bot.send(msg)

    async def send_cycle_summary(self, summary: dict) -> None:
        msg = (
            f"📊 Cycle #{summary.get('cycle')} complete\n"
            f"Arb executed: {summary.get('arb_executed', 0)}\n"
            f"Trades: {summary.get('trades_executed', 0)}\n"
            f"Errors: {len(summary.get('errors', []))}\n"
            f"Duration: {summary.get('duration_seconds', 0):.0f}s"
        )
        await self.bot.send(msg)

    async def send_startup(self, mode: str, bankroll: float) -> None:
        msg = (
            f"🤖 Agent started\n"
            f"Mode: <b>{mode}</b>\n"
            f"Bankroll: ${bankroll:.2f}\n"
            f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        await self.bot.send(msg)
