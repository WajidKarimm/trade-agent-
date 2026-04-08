"""
GDELT news client — free, no API key needed.
GDELT is the world's largest open news database.
Updates every 15 minutes, covers 100+ languages.
Perfect for Polymarket's geopolitical / economic markets.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
from loguru import logger

from data.rss_client import NewsItem, _extract_keywords


GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"


async def fetch_gdelt_news(query: str, days_back: int = 3) -> list[NewsItem]:
    """
    Search GDELT for news related to a query.
    Completely free — no API key.
    Returns structured NewsItem list.
    """
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": 25,
        "format": "json",
        "STARTDATETIME": (datetime.utcnow() - timedelta(days=days_back))
                         .strftime("%Y%m%d%H%M%S"),
        "ENDDATETIME": datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "sort": "DateDesc",
    }

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GDELT_API, params=params, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"GDELT returned {resp.status}")
                        return []
                    data = await resp.json(content_type=None)

            articles = data.get("articles", [])
            items = []
            for a in articles:
                title = a.get("title", "")
                url = a.get("url", "")
                source = a.get("domain", "gdelt")
                try:
                    published = datetime.strptime(
                        a.get("seendate", "")[:14], "%Y%m%dT%H%M%S"
                    )
                except Exception:
                    published = datetime.utcnow()

                items.append(NewsItem(
                    source=source,
                    title=title,
                    summary=title,  # GDELT doesn't return full text
                    url=url,
                    published=published,
                    keywords=_extract_keywords(title),
                ))

            logger.info(f"GDELT '{query}': {len(items)} articles")
            return items

        except Exception as e:
            if attempt == 2:  # Last attempt
                logger.warning(f"GDELT fetch failed for '{query}' after 3 attempts: {e}")
                return []
            await asyncio.sleep(2 ** attempt)


async def fetch_market_news(question: str) -> list[NewsItem]:
    """
    Fetch news relevant to a market question.
    Combines GDELT + RSS for maximum coverage.
    """
    from data.rss_client import fetch_all_news, filter_news_for_market

    # Extract key terms from question for GDELT query
    keywords = _extract_keywords(question)
    gdelt_query = " ".join(keywords[:4])  # GDELT works best with 3-4 terms

    gdelt_task = fetch_gdelt_news(gdelt_query)
    rss_task = fetch_all_news()

    gdelt_news, all_rss = await asyncio.gather(gdelt_task, rss_task)
    rss_relevant = filter_news_for_market(all_rss, question)

    combined = gdelt_news + rss_relevant
    # Deduplicate by URL
    seen = set()
    unique = []
    for item in combined:
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)

    unique.sort(key=lambda x: x.published, reverse=True)
    return unique[:15]  # return top 15
