"""
RAG Ingester — feeds news and market resolutions into Chroma.
Run manually: make ingest
Or automatically triggered by the orchestrator.
"""
import hashlib
from datetime import datetime
from loguru import logger

from data.rss_client import fetch_all_news
from data.news_client import fetch_gdelt_news
from rag.chroma_store import upsert_documents
from storage.db import get_open_trades


def _make_id(text: str) -> str:
    """Stable deterministic ID for a document."""
    return hashlib.md5(text.encode()).hexdigest()


async def ingest_news() -> int:
    """Fetch latest news and store in Chroma."""
    logger.info("Ingesting news into RAG...")

    # Fetch from all free sources
    rss_news = await fetch_all_news()
    gdelt_news = await fetch_gdelt_news("election politics economy", days_back=2)

    all_news = rss_news + gdelt_news
    if not all_news:
        logger.warning("No news fetched for ingestion")
        return 0

    ids, texts, metadatas = [], [], []
    for item in all_news:
        text = f"{item.title}. {item.summary}".strip()
        if len(text) < 20:
            continue
        doc_id = _make_id(text)
        ids.append(doc_id)
        texts.append(text)
        metadatas.append({
            "source": item.source,
            "published": item.published.isoformat(),
            "url": item.url,
            "type": "news",
        })

    upsert_documents(ids, texts, metadatas)
    logger.success(f"Ingested {len(ids)} news articles into RAG")
    return len(ids)


def ingest_market_resolution(
    market_id: str,
    question: str,
    outcome: str,
    category: str,
    resolved_at: str,
) -> None:
    """
    Store a resolved market's outcome for future reference class forecasting.
    This is gold — past resolutions help calibrate future estimates.
    """
    text = f"RESOLVED: {question} → Outcome: {outcome} (Category: {category}, Resolved: {resolved_at})"
    doc_id = _make_id(f"resolution:{market_id}")
    upsert_documents(
        ids=[doc_id],
        texts=[text],
        metadatas=[{
            "market_id": market_id,
            "outcome": outcome,
            "category": category,
            "resolved_at": resolved_at,
            "type": "resolution",
        }],
    )
    logger.info(f"Ingested resolution for market {market_id}: {outcome}")


async def run_ingestion() -> dict:
    """Full ingestion run — called by `make ingest`."""
    news_count = await ingest_news()
    return {
        "news_ingested": news_count,
        "ran_at": datetime.utcnow().isoformat(),
    }
