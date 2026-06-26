"""External microservice clients."""
import httpx
from typing import Dict, Any, Optional
from config import settings


class SVGRenderService:
    """Module 10 - SVG Render Service client."""
    
    @staticmethod
    async def render(model_json: Dict[str, Any]) -> str:
        """Render BPMN model to SVG."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.SVG_SERVICE_URL,
                json=model_json,
                timeout=30.0
            )
            response.raise_for_status()
            return response.text


class SelectionBoxService:
    """Module 11 - Selection Box Service client."""
    
    @staticmethod
    async def get_selection(
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user selection box for a session."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.SELECTION_BOX_SERVICE_URL}/{session_id}",
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            return None
