"""Module 2 - Agent Orchestrator (Core).

The orchestrator now logs conversation turns to MemoryService and calls
SemanticService.sync_model to synchronize confirmed models into the
semantic memory graph.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from core.planner import Planner
from core.clarifier import Clarifier
from core.generator import BPMNGenerator
from core.validator import Validator
from services.memory_service import MemoryService
from services.semantic_service import SemanticService


class Orchestrator:
    """Main orchestrator that coordinates all modules."""

    def __init__(self):
        self.planner = Planner()
        self.clarifier = Clarifier()
        self.generator = BPMNGenerator()
        self.validator = Validator()
        self.memory_service = MemoryService()
        self.semantic_service = SemanticService()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def initialize(self):
        """Initialize all services."""
        await self.memory_service.connect()
        await self.semantic_service.connect()
        print("Orchestrator initialized")

    async def shutdown(self):
        """Shutdown all services."""
        await self.memory_service.disconnect()
        await self.semantic_service.disconnect()
        print("Orchestrator shutdown")

    async def create_process(self, process_node_id: str, title: str, description: str) -> Dict[str, Any]:
        """Create a new process model."""
        process_model_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        # Initialize conversation context
        session = {
            "process_model_id": process_model_id,
            "version_id": version_id,
            "process_node_id": process_node_id,
            "title": title,
            "description": description,
            "turns": [],
            "current_json": {},
            "status": "in_progress",
            "created_at": datetime.now(),
        }

        self.active_sessions[process_model_id] = session

        # Step 1: Planning
        plan = await self.planner.plan(description, process_node_id)
        session["plan"] = plan

        # Step 2: Generate initial JSON
        json_output = await self.generator.generate(plan=plan, current_json={}, context={})
        session["current_json"] = json_output

        # Step 3: Validate
        validation_result = await self.validator.validate(json_output)
        if not validation_result["valid"]:
            # Handle validation errors
            session["validation_errors"] = validation_result["errors"]

        # Save to memory (short-term DB)
        await self.memory_service.save_process(
            process_model_id=process_model_id,
            process_node_id=process_node_id,
            title=title,
            description=description,
            status=session["status"],
        )

        # Log initial turn (user description -> assistant initial json)
        await self.memory_service.save_turn(
            process_model_id=process_model_id,
            user_id=None,
            turn_index=0,
            user_message=description,
            assistant_response=str(json_output),
        )

        # Sync confirmed model to semantic memory (background sync is possible)
        try:
            await self.semantic_service.sync_model(process_model_id, json_output, enrichment_text=description)
        except Exception:
            # don't block creation on semantic sync errors
            pass

        # Save initial version
        await self.memory_service.save_version(
            process_model_id=process_model_id,
            version_id=version_id,
            model_json=json_output,
            instruction="initial",
            selection_box=None,
            change_summary="Initial process model created",
        )

        return {
            "process_model_id": process_model_id,
            "version_id": version_id,
            "title": title,
            "description": description,
            "status": session["status"],
            "model_json": json_output,
            "svg": None,
            "change_summary": "Initial process model created",
            "created_at": session["created_at"],
            "updated_at": datetime.now(),
        }

    async def revise_process(
        self, process_model_id: str, instruction: str, selection_box: Optional[Dict[str, Any]], base_version_id: str
    ) -> Dict[str, Any]:
        """Revise an existing process model."""
        # Retrieve current state from memory
        current_json = await self.memory_service.get_process_version(process_model_id, base_version_id)

        version_id = str(uuid.uuid4())

        # Step 1: Plan the revision
        plan = await self.planner.plan(instruction, None, is_revision=True)

        # Step 2: Generate updated JSON
        updated_json = await self.generator.generate(plan=plan, current_json=current_json, selection_box=selection_box, context={})

        # Step 3: Validate
        validation_result = await self.validator.validate(updated_json)

        # Log turn: user instruction -> assistant updated json
        # compute turn index as count of saved turns for this process (best-effort)
        # For simplicity, turn_index is None here
        await self.memory_service.save_turn(
            process_model_id=process_model_id,
            user_id=None,
            turn_index=None,
            user_message=instruction,
            assistant_response=str(updated_json),
        )

        # Sync to semantic memory (attempt)
        try:
            await self.semantic_service.sync_model(process_model_id, updated_json, enrichment_text=instruction)
        except Exception:
            pass

        # Save new version
        await self.memory_service.save_version(
            process_model_id=process_model_id,
            version_id=version_id,
            model_json=updated_json,
            instruction=instruction,
            selection_box=selection_box,
            change_summary=f"Updated: {instruction}",
        )

        return {
            "process_model_id": process_model_id,
            "version_id": version_id,
            "model_json": updated_json,
            "affected_elements": [],
            "change_summary": f"Updated: {instruction}",
            "svg": None,
            "updated_at": datetime.now(),
        }

    async def get_process(self, process_model_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a process model."""
        process_data = await self.memory_service.get_process(process_model_id)

        if not process_data:
            return None

        return {
            "process_model_id": process_model_id,
            "version_id": process_data["latest_version_id"],
            "title": process_data["title"],
            "description": process_data["description"],
            "status": process_data["status"],
            "model_json": process_data["model_json"],
            "svg": None,
            "change_summary": process_data.get("change_summary", ""),
            "created_at": process_data["created_at"],
            "updated_at": process_data["updated_at"],
        }

    async def get_process_history(self, process_model_id: str) -> Optional[Dict[str, Any]]:
        """Get version history of a process model."""
        process_data = await self.memory_service.get_process(process_model_id)

        if not process_data:
            return None

        history = await self.memory_service.get_process_history(process_model_id)

        return {
            "process_model_id": process_model_id,
            "title": process_data["title"],
            "description": process_data["description"],
            "history": history,
        }


# Global orchestrator instance
orchestrator = Orchestrator()
