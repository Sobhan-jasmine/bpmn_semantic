"""Module 7 - LLM Provider.

Swappable adapter over LLM API (AvalAI/OpenAI-compatible).
"""
import httpx
from typing import Dict, Any, Optional
from config import settings


class LLMService:
    """Interface to LLM provider."""
    
    def __init__(self):
        self.base_url = settings.LLM_PROVIDER_URL
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
    
    async def complete(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """Call LLM for completion."""
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                *messages
            ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]


llm_service = LLMService()
