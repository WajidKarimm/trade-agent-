"""
Telegram bot — free alerts for trades, arb, halts.
Setup: create a bot via @BotFather, get token + chat_id.
Add both to .env — zero cost.
"""
from loguru import logger
from config.settings import get_settings


class TelegramBot:
    def __init__(self):
        self.settings = get_settings()
        self._bot = None

    def _get_bot(self):
        if self._bot is None:
            token = self.settings.telegram_bot_token
            if not token or token == "your_bot_token_from_botfather":
                return None
            try:
                from telegram import Bot
                self._bot = Bot(token=token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
            except Exception as e:
                logger.warning(f"Telegram bot init failed: {e}")
        return self._bot

    async def send(self, message: str) -> bool:
        """Send a message to the configured chat."""
        bot = self._get_bot()
        if bot is None:
            logger.debug(f"Telegram not configured. Message: {message}")
            return False
        try:
            chat_id = self.settings.telegram_chat_id
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
            return True
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
            return False
