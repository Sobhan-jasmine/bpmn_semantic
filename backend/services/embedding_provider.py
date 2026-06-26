"""Embedding provider abstraction.

Provides a common interface for embedding backends and a local
sentence-transformers implementation. The implementation is optional
and will raise a clear error if dependencies are missing.
"""
from typing import List
from config import settings


class EmbeddingProvider:
    """Abstract embedding provider."""

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class LocalSentenceTransformer(EmbeddingProvider):
    def __init__(self, model_name: str = None):
        model_name = model_name or settings.EMBEDDING_MODEL
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Install it or use a remote embedding API."
            ) from e
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        emb = self.model.encode(texts, normalize_embeddings=True)
        # sentence-transformers returns numpy arrays; convert to list
        return emb.tolist()


class RemoteEmbeddingAPI(EmbeddingProvider):
    """Placeholder for remote embedding API implementation.

    Implement this to call your preferred embedding HTTP API and return
    a list of vectors.
    """

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or settings.EMBEDDING_API_URL
        self.api_key = api_key

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("Remote embedding API is not implemented yet.")
