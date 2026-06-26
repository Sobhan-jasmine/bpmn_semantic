"""Module 4 - Clarifier.

Generates natural-language questions when process description
is incomplete or ambiguous.
"""
from typing import Dict, Any, List


class Clarifier:
    """Asks clarifying questions when needed."""
    
    async def clarify(
        self,
        ambiguities: List[str],
        candidates: List[Dict[str, Any]] = None
    ) -> str:
        """Generate clarifying question."""
        # TODO: Integrate with LLM Provider (Module 7)
        return "Could you provide more details?"
