"""
Analyst Agent — the Claude-powered superforecaster.
This is the ONLY place in the codebase that calls the Anthropic API.
Uses RAG context + news to form calibrated probability estimates.
"""
import json
from pathlib import Path
from typing import Optional
import anthropic
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from config.constants import MAX_ANALYST_RETRIES
from storage.models import MarketSnapshot, AnalystSignal, Side, SignalType
from data.news_client import fetch_market_news


def _load_prompt(name: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / name
    return path.read_text()


def _format_news_context(news_items: list) -> str:
    if not news_items:
        return "No recent news found."
    lines = []
    for item in news_items[:8]:
        lines.append(f"- [{item.source}] {item.title} ({item.published.strftime('%Y-%m-%d')})")
    return "\n".join(lines)


def _format_rag_context(rag_results: list[str]) -> str:
    if not rag_results:
        return "No similar historical markets found."
    return "\n".join(f"- {r}" for r in rag_results[:5])


class AnalystAgent:
    def __init__(self):
        self.settings = get_settings()
        self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        self.prompt_template = _load_prompt("superforecaster.txt")
        self._rag_retriever = None

    def _get_retriever(self):
        if self._rag_retriever is None:
            try:
                from rag.retriever import retrieve_similar
                self._rag_retriever = retrieve_similar
            except Exception as e:
                logger.warning(f"RAG not available: {e}")
        return self._rag_retriever

    @retry(stop=stop_after_attempt(MAX_ANALYST_RETRIES), wait=wait_exponential(min=2, max=30))
    async def analyse_market(
        self,
        market: MarketSnapshot,
        news_items: Optional[list] = None,
    ) -> Optional[AnalystSignal]:
        """
        Analyse a market and return a probability signal.
        Fetches news and RAG context automatically.
        """
        # Fetch news if not provided
        if news_items is None:
            news_items = await fetch_market_news(market.question)

        news_context = _format_news_context(news_items)

        # Try RAG retrieval
        rag_context = "No historical context available."
        retriever = self._get_retriever()
        if retriever:
            try:
                rag_results = retriever(market.question, n_results=5)
                rag_context = _format_rag_context(rag_results)
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Build prompt
        prompt = self.prompt_template.format(
            question=market.question,
            category=market.category,
            market_price_yes=market.yes_price,
            resolve_by=market.resolve_by.strftime("%Y-%m-%d"),
            days_to_resolve=market.days_to_resolve,
            description=market.description[:300] if market.description else "N/A",
            news_context=news_context,
            rag_context=rag_context,
        )

        logger.info(f"Analyst → {market.question[:60]}...")

        # Call Claude
        message = self.client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()

        # Parse JSON response
        try:
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Analyst JSON parse failed: {e}\nRaw: {raw[:200]}")
            return None

        prob_yes = float(data["probability_yes"])
        confidence = float(data["confidence"])
        reasoning = data.get("reasoning", "")

        # Determine edge and side
        edge = prob_yes - market.yes_price
        side = Side.YES if edge > 0 else Side.NO
        # If we're buying NO, the relevant edge is: our prob_no - market_no_price
        if side == Side.NO:
            prob_no = 1.0 - prob_yes
            edge = prob_no - market.no_price

        signal = AnalystSignal(
            market_id=market.market_id,
            question=market.question,
            my_prob_yes=prob_yes,
            market_prob_yes=market.yes_price,
            edge=abs(edge),
            confidence=confidence,
            side=side,
            reasoning=reasoning,
            news_context=news_context,
            signal_type=SignalType.ANALYST,
        )

        logger.info(
            f"Signal | edge={signal.edge:.3f} conf={confidence:.2f} "
            f"side={side.value} | {market.question[:50]}"
        )
        return signal

    async def filter_markets(self, markets: list[MarketSnapshot]) -> list[MarketSnapshot]:
        """
        Use Claude to pick the best markets to analyse this cycle.
        Saves API calls by skipping low-quality markets.
        """
        import json as _json
        filter_prompt = _load_prompt("market_filter.txt")
        markets_data = [
            {"id": m.market_id, "question": m.question,
             "volume": m.volume_usd, "category": m.category}
            for m in markets[:50]
        ]
        prompt = filter_prompt.format(markets_json=_json.dumps(markets_data, indent=2))

        try:
            message = self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            selected_ids = set(_json.loads(raw))
            filtered = [m for m in markets if m.market_id in selected_ids]
            logger.info(f"Market filter: {len(markets)} → {len(filtered)} selected")
            return filtered
        except Exception as e:
            logger.warning(f"Market filter failed ({e}), using all markets")
            return markets[:20]  # fallback: top 20 by volume
