"""Module 1 - API Gateway endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from schemas.process import (
    ProcessCreateRequest,
    ProcessRevisionRequest,
    ProcessModelResponse,
    ProcessRevisionResponse,
    ProcessHistoryResponse
)
from core.orchestrator import orchestrator

router = APIRouter(tags=["process-models"])


@router.post(
    "/process-models",
    response_model=ProcessModelResponse,
    summary="Create a new BPMN process model",
    description="Initiates a new process model creation with initial description"
)
async def create_process_model(request: ProcessCreateRequest):
    """
    Create a new BPMN process model.
    
    Receives:
    - process_node_id: Neo4j level-4 process node anchor
    - title: Process model title
    - description: Natural language description
    
    Returns:
    - process_model_id
    - version_id
    - initial model_json
    - svg representation
    - change_summary
    """
    try:
        result = await orchestrator.create_process(
            process_node_id=request.process_node_id,
            title=request.title,
            description=request.description
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/process-models/{process_model_id}/revisions",
    response_model=ProcessRevisionResponse,
    summary="Create a new revision of a process model",
    description="Edit an existing process model with natural language instruction"
)
async def revise_process_model(
    process_model_id: str,
    request: ProcessRevisionRequest
):
    """
    Revise an existing BPMN process model.
    
    Receives:
    - instruction: Natural language change instruction
    - selection_box: User-selected elements to modify (optional)
    - base_version_id: Version to edit from
    
    Returns:
    - Updated model_json
    - affected_elements list
    - change_summary
    - svg representation
    """
    try:
        result = await orchestrator.revise_process(
            process_model_id=process_model_id,
            instruction=request.instruction,
            selection_box=request.selection_box,
            base_version_id=request.base_version_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/process-models/{process_model_id}",
    response_model=ProcessModelResponse,
    summary="Get current process model state",
    description="Retrieve the latest version of a process model"
)
async def get_process_model(process_model_id: str):
    """
    Get the latest state of a process model.
    
    Returns:
    - Current model metadata
    - Latest confirmed version JSON
    - SVG representation
    """
    try:
        result = await orchestrator.get_process(
            process_model_id=process_model_id
        )
        if not result:
            raise HTTPException(status_code=404, detail="Process model not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/process-models/{process_model_id}/history",
    response_model=ProcessHistoryResponse,
    summary="Get process model version history",
    description="Retrieve full version history with all revisions"
)
async def get_process_history(process_model_id: str):
    """
    Get the full version history of a process model.
    
    Returns:
    - Complete list of confirmed versions
    - Each with: instruction, selection_box, change_summary, timestamps
    """
    try:
        result = await orchestrator.get_process_history(
            process_model_id=process_model_id
        )
        if not result:
            raise HTTPException(status_code=404, detail="Process model not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
