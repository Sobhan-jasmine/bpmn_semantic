"""Schemas for process model operations."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProcessCreateRequest(BaseModel):
    """Request schema for creating a new process model."""
    process_node_id: str = Field(..., description="Neo4j level-4 process node ID")
    title: str = Field(..., description="Process model title")
    description: str = Field(..., description="Natural language process description")


class ProcessRevisionRequest(BaseModel):
    """Request schema for revising an existing process model."""
    instruction: str = Field(..., description="Natural language instruction for changes")
    selection_box: Optional[Dict[str, Any]] = Field(None, description="JSON elements user selected")
    base_version_id: str = Field(..., description="Version ID to edit from")


class ProcessModelResponse(BaseModel):
    """Response schema for a process model."""
    process_model_id: str
    version_id: str
    title: str
    description: str
    status: str
    model_json: Dict[str, Any]
    svg: Optional[str] = None
    change_summary: str
    created_at: datetime
    updated_at: datetime


class ProcessRevisionResponse(BaseModel):
    """Response schema for a revision operation."""
    process_model_id: str
    version_id: str
    model_json: Dict[str, Any]
    affected_elements: List[str]
    change_summary: str
    svg: Optional[str] = None
    updated_at: datetime


class ProcessHistoryItem(BaseModel):
    """Single item in process version history."""
    version_id: str
    version_number: int
    instruction: str
    selection_box: Optional[Dict[str, Any]]
    change_summary: str
    created_at: datetime
    created_by: str


class ProcessHistoryResponse(BaseModel):
    """Response schema for process history."""
    process_model_id: str
    title: str
    description: str
    history: List[ProcessHistoryItem]
