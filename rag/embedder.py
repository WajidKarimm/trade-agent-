"""
Local embedder using sentence-transformers.
Completely free — runs on CPU, no API calls.
Model: all-MiniLM-L6-v2 (fast, good quality, 80MB download once)
"""
from typing import Optional
from loguru import logger

_model = None


def get_model():
    """Lazy-load the embedding model (downloads once, cached locally)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model (first run downloads ~80MB)...")
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.success("Embedding model loaded")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns vector of 384 dimensions."""
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts efficiently."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32)
    return embeddings.tolist()
