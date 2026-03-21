from fastembed import TextEmbedding
from ..core.config import settings

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=settings.embed_model)
    return _model


def embed(text: str) -> list[float]:
    model = get_model()
    embeddings = list(model.embed([text[:8000]]))
    return embeddings[0].tolist()


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks for dense retrieval."""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks
