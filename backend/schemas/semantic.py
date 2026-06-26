from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class NodeDescriptor(BaseModel):
    type: str
    key: Dict[str, Any]
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)


class RelationshipDescriptor(BaseModel):
    from_node: Dict[str, Any]
    to_node: Dict[str, Any]
    type: str


class UpdateRequest(BaseModel):
    process_id: Optional[str] = None
    final_bpmn: Dict[str, Any]
    enrichment_text: Optional[str] = None
    user_id: Optional[str] = None
    source: Optional[str] = None


class UpdateResponse(BaseModel):
    status: str
    merged_nodes: Dict[str, int] = Field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    process_node_id: Optional[str] = None


class QueryRequest(BaseModel):
    process_id: Optional[str] = None
    nl_query: str
    schema_hint: Optional[List[str]] = None
    top_k: int = 5


class NodeResult(BaseModel):
    label: str
    id: str
    name: Optional[str] = None
    definition: Optional[str] = None


class RelationResult(BaseModel):
    type: str
    target: NodeResult


class QueryResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)
