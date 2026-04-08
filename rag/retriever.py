"""
RAG Retriever — pulls relevant context for the analyst.
Returns formatted strings ready to drop into the superforecaster prompt.
"""
from loguru import logger
from rag.chroma_store import query_similar


def retrieve_similar(query: str, n_results: int = 5) -> list[str]:
    """
    Retrieve documents similar to the query.
    Returns formatted strings for prompt injection.
    """
    try:
        results = query_similar(query, n_results=n_results)
        formatted = []
        for r in results:
            meta = r["metadata"]
            doc_type = meta.get("type", "unknown")
            if doc_type == "resolution":
                formatted.append(f"[Past resolution] {r['text']}")
            elif doc_type == "news":
                source = meta.get("source", "unknown")
                date = meta.get("published", "")[:10]
                formatted.append(f"[{source} {date}] {r['text'][:200]}")
            else:
                formatted.append(r["text"][:200])
        return formatted
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return []


def retrieve_resolutions(category: str, n_results: int = 5) -> list[str]:
    """Retrieve past market resolutions for a specific category."""
    try:
        results = query_similar(
            category,
            n_results=n_results,
            where={"type": "resolution"},
        )
        return [r["text"] for r in results]
    except Exception as e:
        logger.warning(f"Resolution retrieval failed: {e}")
        return []
