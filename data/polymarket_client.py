"""
Polymarket data client — Gamma API (free, no auth) + CLOB.
Gamma: market metadata, prices, volume.
CLOB: order book, order placement.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from config.constants import MAX_RESOLVE_DAYS, MIN_MARKET_VOLUME_USD
from storage.models import MarketSnapshot


class PolymarketClient:
    def __init__(self):
        self.settings = get_settings()
        self.gamma_url = self.settings.poly_gamma_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "polymarket-agent/1.0"}
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_active_markets(self) -> list[MarketSnapshot]:
        """
        Fetch all active markets from Gamma API (completely free).
        Filters to only markets resolving within MAX_RESOLVE_DAYS.
        """
        cutoff = datetime.utcnow() + timedelta(days=MAX_RESOLVE_DAYS)
        params = {
            "active": "true",
            "closed": "false",
            "limit": 200,
            "order": "volume24hr",
            "ascending": "false",
        }
        async with self.session.get(
            f"{self.gamma_url}/markets", params=params
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        markets = []
        for m in data:
            try:
                resolve_by = datetime.fromisoformat(
                    m.get("endDate", "").replace("Z", "+00:00")
                ).replace(tzinfo=None)

                if resolve_by > cutoff:
                    continue  # too far out — skip

                yes_price = float(m.get("outcomePrices", ["0.5"])[0])
                no_price = 1.0 - yes_price
                volume = float(m.get("volume", 0))

                if volume < MIN_MARKET_VOLUME_USD:
                    continue  # illiquid — skip

                markets.append(MarketSnapshot(
                    market_id=m["id"],
                    question=m.get("question", ""),
                    yes_price=yes_price,
                    no_price=no_price,
                    volume_usd=volume,
                    liquidity_usd=float(m.get("liquidity", 0)),
                    resolve_by=resolve_by,
                    category=m.get("category", ""),
                    description=m.get("description", ""),
                ))
            except Exception as e:
                logger.warning(f"Skipping malformed market {m.get('id')}: {e}")

        logger.info(f"Fetched {len(markets)} active markets within {MAX_RESOLVE_DAYS} days")
        return markets

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_market(self, market_id: str) -> Optional[MarketSnapshot]:
        """Fetch a single market by ID."""
        async with self.session.get(
            f"{self.gamma_url}/markets/{market_id}"
        ) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            m = await resp.json()

        try:
            resolve_by = datetime.fromisoformat(
                m.get("endDate", "").replace("Z", "+00:00")
            ).replace(tzinfo=None)
            yes_price = float(m.get("outcomePrices", ["0.5"])[0])
            return MarketSnapshot(
                market_id=m["id"],
                question=m.get("question", ""),
                yes_price=yes_price,
                no_price=1.0 - yes_price,
                volume_usd=float(m.get("volume", 0)),
                liquidity_usd=float(m.get("liquidity", 0)),
                resolve_by=resolve_by,
                category=m.get("category", ""),
                description=m.get("description", ""),
            )
        except Exception as e:
            logger.error(f"Failed to parse market {market_id}: {e}")
            return None

    async def place_order(
        self,
        market_id: str,
        side: str,
        amount_usd: float,
        price: float,
    ) -> dict:
        """
        Place a live order on Polymarket CLOB.
        Only called when LIVE_MODE=true.
        Uses py-clob-client under the hood.
        """
        if not self.settings.live_mode:
            raise RuntimeError("place_order called in paper mode — this is a bug")

        # py-clob-client integration
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import OrderArgs, OrderType

            client = ClobClient(
                host=self.settings.poly_clob_url,
                key=self.settings.poly_private_key,
                chain_id=137,  # Polygon mainnet
            )
            order_args = OrderArgs(
                token_id=market_id,
                price=price,
                size=amount_usd,
                side=side,
            )
            signed_order = client.create_order(order_args)
            resp = client.post_order(signed_order, OrderType.GTC)
            logger.info(f"Order placed: {resp}")
            return resp
        except ImportError:
            logger.error("py-clob-client not installed. Run: pip install py-clob-client")
            raise
