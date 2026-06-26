"""Module 8 - Short-Term Memory (MariaDB).

Stores conversation history and versioned BPMN artifacts.

Added a ConversationTurn model and save_turn method for short-term logging of
user-assistant turns associated with a process_model_id.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

Base = declarative_base()


class ProcessModel(Base):
    """ProcessModel table - one row per process."""
    __tablename__ = "process_models"

    process_model_id = Column(String(36), primary_key=True)
    process_node_id = Column(String(100))
    title = Column(String(255))
    description = Column(String(2000))
    status = Column(String(50))
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ProcessModelVersion(Base):
    """ProcessModelVersion table - one row per confirmed version."""
    __tablename__ = "process_model_versions"

    version_id = Column(String(36), primary_key=True)
    process_model_id = Column(String(36))
    version_number = Column(Integer)
    model_json = Column(JSON)
    svg_content = Column(String(10000), nullable=True)
    instruction = Column(String(2000), nullable=True)
    selection_box = Column(JSON, nullable=True)
    change_summary = Column(String(1000))
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)


class ConversationTurn(Base):
    """Conversation turn logging for short-term memory."""
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_model_id = Column(String(36), nullable=True)
    user_id = Column(String(100), nullable=True)
    turn_index = Column(Integer, nullable=True)
    user_message = Column(Text)
    assistant_response = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class MemoryService:
    """Service for managing short-term memory in MariaDB."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    async def connect(self):
        """Connect to MariaDB."""
        db_url = settings.get_database_url()
        self.engine = create_engine(db_url, echo=settings.DEBUG)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        print("Connected to MariaDB")

    async def disconnect(self):
        """Disconnect from MariaDB."""
        if self.engine:
            self.engine.dispose()
            print("Disconnected from MariaDB")

    async def save_process(
        self,
        process_model_id: str,
        process_node_id: str,
        title: str,
        description: str,
        status: str,
        created_by: str = "system",
    ):
        """Save a new process model."""
        session = self.SessionLocal()
        try:
            process = ProcessModel(
                process_model_id=process_model_id,
                process_node_id=process_node_id,
                title=title,
                description=description,
                status=status,
                created_by=created_by,
            )
            session.add(process)
            session.commit()
        finally:
            session.close()

    async def save_version(
        self,
        process_model_id: str,
        version_id: str,
        model_json: Dict[str, Any],
        instruction: str,
        selection_box: Optional[Dict[str, Any]],
        change_summary: str,
        created_by: str = "system",
    ):
        """Save a new version of a process model."""
        session = self.SessionLocal()
        try:
            # Get current version number
            latest = (
                session.query(ProcessModelVersion)
                .filter_by(process_model_id=process_model_id)
                .order_by(ProcessModelVersion.version_number.desc())
                .first()
            )

            version_number = (latest.version_number + 1) if latest else 1

            version = ProcessModelVersion(
                version_id=version_id,
                process_model_id=process_model_id,
                version_number=version_number,
                model_json=model_json,
                instruction=instruction,
                selection_box=selection_box,
                change_summary=change_summary,
                created_by=created_by,
            )
            session.add(version)
            session.commit()
        finally:
            session.close()

    async def save_turn(
        self,
        process_model_id: Optional[str],
        user_id: Optional[str],
        turn_index: Optional[int],
        user_message: str,
        assistant_response: str,
    ):
        """Save a conversation turn for a process model."""
        session = self.SessionLocal()
        try:
            turn = ConversationTurn(
                process_model_id=process_model_id,
                user_id=user_id,
                turn_index=turn_index,
                user_message=user_message,
                assistant_response=assistant_response,
            )
            session.add(turn)
            session.commit()
        finally:
            session.close()

    async def get_process(self, process_model_id: str) -> Optional[Dict[str, Any]]:
        """Get process and latest version."""
        session = self.SessionLocal()
        try:
            process = (
                session.query(ProcessModel).filter_by(process_model_id=process_model_id).first()
            )

            if not process:
                return None

            version = (
                session.query(ProcessModelVersion)
                .filter_by(process_model_id=process_model_id)
                .order_by(ProcessModelVersion.version_number.desc())
                .first()
            )

            return {
                "process_model_id": process.process_model_id,
                "title": process.title,
                "description": process.description,
                "status": process.status,
                "latest_version_id": version.version_id if version else None,
                "model_json": version.model_json if version else {},
                "change_summary": version.change_summary if version else "",
                "created_at": process.created_at,
                "updated_at": process.updated_at,
            }
        finally:
            session.close()

    async def get_process_version(self, process_model_id: str, version_id: str) -> Dict[str, Any]:
        """Get a specific version of a process."""
        session = self.SessionLocal()
        try:
            version = (
                session.query(ProcessModelVersion)
                .filter_by(process_model_id=process_model_id, version_id=version_id)
                .first()
            )

            return version.model_json if version else {}
        finally:
            session.close()

    async def get_process_history(self, process_model_id: str) -> List[Dict[str, Any]]:
        """Get version history of a process."""
        session = self.SessionLocal()
        try:
            versions = (
                session.query(ProcessModelVersion)
                .filter_by(process_model_id=process_model_id)
                .order_by(ProcessModelVersion.version_number)
                .all()

            return [
                {
                    "version_id": v.version_id,
                    "version_number": v.version_number,
                    "instruction": v.instruction or "",
                    "selection_box": v.selection_box,
                    "change_summary": v.change_summary,
                    "created_at": v.created_at,
                    "created_by": v.created_by,
                }
                for v in versions
            ]
        finally:
            session.close()
