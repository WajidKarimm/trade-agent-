"""
Chroma vector database — local, free, no cloud.
Stores news articles and past market resolutions.
Used by the retriever to give the analyst historical context.
"""
from pathlib import Path
from typing import Optional
from loguru import logger

from config.settings import get_settings

_client = None
_collection = None
COLLECTION_NAME = "market_knowledge"


def get_collection():
    """Get or create the Chroma collection."""
    global _client, _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        settings = get_settings()
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Chroma collection ready: {_collection.count()} documents")
        return _collection
    except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        raise


def upsert_documents(
    ids: list[str],
    texts: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Add or update documents in the vector store."""
    from rag.embedder import embed_batch
    collection = get_collection()
    embeddings = embed_batch(texts)
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas or [{} for _ in texts],
    )
    logger.debug(f"Upserted {len(ids)} documents into Chroma")


def query_similar(
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> list[dict]:
    """
    Find documents similar to query_text.
    Returns list of {text, metadata, distance} dicts.
    """
    from rag.embedder import embed_text
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        where=where,
    )

    output = []
    for i, doc in enumerate(results["documents"][0]):
        output.append({
            "text": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return output


def get_collection_stats() -> dict:
    """Return stats about the vector store."""
    try:
        collection = get_collection()
        return {"total_documents": collection.count(), "status": "ok"}
    except Exception as e:
        return {"total_documents": 0, "status": str(e)}
