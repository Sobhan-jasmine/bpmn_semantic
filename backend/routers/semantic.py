"""Router for semantic memory operations.

Exposes two endpoints for agent usage:
- POST /semantic-memory/update
- POST /semantic-memory/query

These endpoints are intentionally small and call the service skeleton in
backend/services/semantic_memory.py. Extend them to add authentication,
validation, background LLM extraction calls, and richer merge workflows.
"""
from fastapi import APIRouter, HTTPException

from schemas.semantic import (
    UpdateRequest,
    UpdateResponse,
    QueryRequest,
    QueryResponse,
)
from services.semantic_memory import semantic_memory

router = APIRouter(tags=["semantic-memory"])


@router.post("/semantic-memory/update", response_model=UpdateResponse, summary="Update semantic memory with final BPMN and enrichment")
async def update_semantic_memory(request: UpdateRequest):
    try:
        result = await semantic_memory.upsert_from_final_bpmn(
            process_id=request.process_id,
            final_bpmn=request.final_bpmn,
            enrichment_text=request.enrichment_text,
            user_id=request.user_id,
            source=request.source,
        )
        return UpdateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/semantic-memory/query", response_model=QueryResponse, summary="Query semantic memory from agent natural-language query")
async def query_semantic_memory(request: QueryRequest):
    try:
        result = await semantic_memory.query_by_nl(
            nl_query=request.nl_query,
            schema_hint=request.schema_hint or [],
            top_k=request.top_k,
        )
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
