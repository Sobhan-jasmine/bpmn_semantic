"""Module 12 - Embedding Service.

Provides vector embeddings for semantic similarity lookups.
"""
from typing import List
import numpy as np
from config import settings

if settings.USE_LOCAL_EMBEDDING:
    from sentence_transformers import SentenceTransformer
else:
    import httpx


class EmbeddingService:
    """Service for generating embeddings."""
    
    def __init__(self):
        if settings.USE_LOCAL_EMBEDDING:
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        else:
            self.base_url = settings.EMBEDDING_API_URL
    
    async def embed(
        self,
        texts: List[str]
    ) -> np.ndarray:
        """Generate embeddings for texts."""
        if settings.USE_LOCAL_EMBEDDING:
            return self.model.encode(texts, normalize_embeddings=True)
        else:
            # Call remote API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={"texts": texts}
                )
                return np.array(response.json())
    
    async def similarity_search(
        self,
        query_text: str,
        candidates: List[str],
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar candidates to query."""
        query_embedding = await self.embed([query_text])
        candidate_embeddings = await self.embed(candidates)
        
        # Compute cosine similarity
        similarities = np.dot(candidate_embeddings, query_embedding.T).flatten()
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [
            (candidates[i], similarities[i])
            for i in top_indices
        ]
