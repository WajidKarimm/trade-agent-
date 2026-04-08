"""
Kalshi client — used ONLY for cross-venue arbitrage detection.
Reads public market prices to compare with Polymarket.
Free read API, no auth needed for public data.
"""
from typing import Optional
import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings


class KalshiClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.kalshi_base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_market_price(self, ticker: str) -> Optional[float]:
        """
        Get the YES price for a Kalshi market by ticker.
        Returns float 0.0-1.0 or None if market not found.
        """
        try:
            async with self.session.get(
                f"{self.base_url}/markets/{ticker}"
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                data = await resp.json()
                market = data.get("market", {})
                # Kalshi returns yes_ask in cents (0-100)
                yes_ask = market.get("yes_ask", None)
                if yes_ask is None:
                    return None
                return float(yes_ask) / 100.0
        except Exception as e:
            logger.warning(f"Kalshi fetch failed for {ticker}: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def search_markets(self, keyword: str) -> list[dict]:
        """
        Search for Kalshi markets matching a keyword.
        Used to find equivalent markets for cross-venue arb.
        """
        try:
            async with self.session.get(
                f"{self.base_url}/markets",
                params={"status": "open", "limit": 50}
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                markets = data.get("markets", [])
                keyword_lower = keyword.lower()
                matches = [
                    m for m in markets
                    if keyword_lower in m.get("title", "").lower()
                    or keyword_lower in m.get("ticker", "").lower()
                ]
                return matches
        except Exception as e:
            logger.warning(f"Kalshi search failed: {e}")
            return []
