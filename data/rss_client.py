"""
RSS news client — completely free.
Parses BBC, Reuters, AP, Guardian, Al Jazeera feeds.
Returns structured news items for the analyst and RAG ingester.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import feedparser
import aiohttp
from loguru import logger


RSS_FEEDS = {
    "bbc_world":    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc_politics": "http://feeds.bbci.co.uk/news/politics/rss.xml",
    "nyt_world":    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "reuters_world":"https://feeds.reuters.com/reuters/worldNews",
    "reuters_biz":  "https://feeds.reuters.com/reuters/businessNews",
    "ap_top":       "https://feeds.apnews.com/rss/apf-topnews",
    "guardian_world":"https://www.theguardian.com/world/rss",
    "aljazeera":    "https://www.aljazeera.com/xml/rss/all.xml",
}


@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    url: str
    published: datetime
    keywords: list[str]


def _extract_keywords(text: str) -> list[str]:
    """Simple keyword extraction — no paid NLP needed."""
    stopwords = {"the","a","an","is","in","on","at","to","for","of","and","or","but","with"}
    words = text.lower().split()
    return list({w.strip(".,!?") for w in words if len(w) > 4 and w not in stopwords})[:20]


async def fetch_feed(source: str, url: str) -> list[NewsItem]:
    """Fetch and parse a single RSS feed asynchronously."""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    content = await resp.text()

            feed = feedparser.parse(content)
            items = []
            for entry in feed.entries[:20]:  # latest 20 per feed
                try:
                    published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") and entry.published_parsed else datetime.utcnow()
                    title = entry.get("title", "")
                    summary = entry.get("summary", entry.get("description", ""))[:500]
                    items.append(NewsItem(
                        source=source,
                        title=title,
                        summary=summary,
                        url=entry.get("link", ""),
                        published=published,
                        keywords=_extract_keywords(f"{title} {summary}"),
                    ))
                except Exception:
                    continue
            logger.debug(f"RSS {source}: {len(items)} items")
            return items
        except Exception as e:
            if attempt == 2:  # Last attempt
                logger.warning(f"RSS feed failed [{source}] after 3 attempts: {e}")
                return []
            await asyncio.sleep(2 ** attempt)


async def fetch_all_news() -> list[NewsItem]:
    """Fetch all RSS feeds concurrently."""
    tasks = [fetch_feed(src, url) for src, url in RSS_FEEDS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_items = []
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)
    all_items.sort(key=lambda x: x.published, reverse=True)
    logger.info(f"Total news items fetched: {len(all_items)}")
    return all_items


def filter_news_for_market(news: list[NewsItem], question: str) -> list[NewsItem]:
    """Return news items relevant to a market question."""
    question_words = set(_extract_keywords(question))
    scored = []
    for item in news:
        item_words = set(item.keywords)
        overlap = len(question_words & item_words)
        if overlap > 0:
            scored.append((overlap, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:5]]  # top 5 relevant
