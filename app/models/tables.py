from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)
    current_stage: Mapped[str] = mapped_column(String(100), default="created")
    priority: Mapped[int] = mapped_column(Integer, default=5)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)

    drive_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_role: Mapped[str] = mapped_column(String(50), default="source")
    drive_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="discovered", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("files.id"), nullable=True, index=True)

    book: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verse_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verse_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    segment_index: Mapped[int] = mapped_column(Integer, default=0)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GlossaryTerm(Base):
    __tablename__ = "glossary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_language: Mapped[str] = mapped_column(String(50), default="en")
    target_language: Mapped[str] = mapped_column(String(50), default="zh-TW")
    translation: Mapped[str] = mapped_column(String(255), nullable=False)

    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("segments.id"), nullable=True, index=True)

    note_type: Mapped[str] = mapped_column(String(100), default="human_note")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), default="translation_rule")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    version: Mapped[int] = mapped_column(Integer, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TranslationVersion(Base):
    __tablename__ = "translation_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("segments.id"), nullable=True, index=True)

    version_no: Mapped[int] = mapped_column(Integer, default=1)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    qa_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("segments.id"), nullable=True, index=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("translation_versions.id"), nullable=True, index=True)

    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_type: Mapped[str] = mapped_column(String(100), default="faithfulness")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    issues_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("segments.id"), nullable=True, index=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("translation_versions.id"), nullable=True, index=True)

    reviewer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    human_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revised_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    source_type: Mapped[str] = mapped_column(String(100), default="human_approved")
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vector_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)

    stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VectorChunk(Base):
    __tablename__ = "vector_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("segments.id"), nullable=True, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
