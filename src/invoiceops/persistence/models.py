from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invoiceops.persistence.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    users: Mapped[list[User]] = relationship(back_populates="workspace")
    documents: Mapped[list[Document]] = relationship(back_populates="workspace")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("workspace_id", "username", name="uq_user_workspace_username"),
        CheckConstraint("role in ('admin', 'reviewer', 'reader')", name="ck_user_role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="reader")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    workspace: Mapped[Workspace] = relationship(back_populates="users")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_document_workspace_sha256"),
        CheckConstraint(
            "processing_status in ('queued', 'processing', 'completed', 'failed')",
            name="ck_document_processing_status",
        ),
        CheckConstraint(
            "review_status in ('pending', 'needs_review', 'approved', 'rejected')",
            name="ck_document_review_status",
        ),
        CheckConstraint(
            "delivery_status in ('not_requested', 'pending', 'delivered', 'failed', 'unknown')",
            name="ck_document_delivery_status",
        ),
        Index("ix_document_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    processing_status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    delivery_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_requested"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[str | None] = mapped_column(String(36))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    revisions: Mapped[list[Revision]] = relationship(
        back_populates="document", order_by="Revision.number"
    )
    audits: Mapped[list[AuditEvent]] = relationship(back_populates="document")
    attempts: Mapped[list[ProcessingAttempt]] = relationship(back_populates="document")


class ProcessingAttempt(Base):
    __tablename__ = "processing_attempts"
    __table_args__ = (
        UniqueConstraint("document_id", "number", name="uq_attempt_document_number"),
        CheckConstraint(
            "state in ('processing', 'completed', 'failed')",
            name="ck_attempt_state",
        ),
        Index("ix_attempt_document_started", "document_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    document: Mapped[Document] = relationship(back_populates="attempts")


class Revision(Base):
    __tablename__ = "revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "number", name="uq_revision_document_number"),
        CheckConstraint(
            "kind in ('extraction', 'review')",
            name="ck_revision_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_pages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    issues: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(160))
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount_discounts: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount_taxes: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount_shipping: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    document: Mapped[Document] = relationship(back_populates="revisions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_document_created", "document_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("revisions.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(80))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    document: Mapped[Document] = relationship(back_populates="audits")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_state_created", "state", "created_at"),
        CheckConstraint("state in ('pending', 'published')", name="ck_outbox_state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    delivery_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("deliveries.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("revision_id", "destination_key", name="uq_delivery_revision_destination"),
        CheckConstraint(
            "state in ('pending', 'sending', 'delivered', 'failed', 'unknown')",
            name="ck_delivery_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("revisions.id", ondelete="CASCADE"))
    destination_key: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    payload_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class IntegrationReceipt(Base):
    __tablename__ = "integration_receipts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_receipt_idempotency_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
