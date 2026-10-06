from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from invoiceops.persistence.models import Document, OutboxEvent

LEASE_TIMEOUT = timedelta(minutes=5)


def publish_outbox_event(
    session_factory: sessionmaker[Session],
    celery_app: Celery,
    event_id: UUID,
) -> bool:
    with session_factory() as session, session.begin():
        event = session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if event is None or event.state != "pending":
            return False
        if event.event_type not in {"process", "delivery"}:
            raise ValueError(f"Unsupported outbox event type: {event.event_type}")
        document = session.get(Document, event.document_id)
        if document is None:
            event.state = "published"
            event.published_at = datetime.now(UTC)
            return False
        if event.event_type == "process":
            task_name = "invoiceops.process_document"
            arguments = [str(document.id), str(event.id)]
        else:
            if event.delivery_id is None:
                raise ValueError("Delivery outbox event has no delivery identifier.")
            task_name = "invoiceops.deliver_approved_record"
            arguments = [str(event.delivery_id), str(event.id)]
        celery_app.send_task(
            task_name,
            args=arguments,
            task_id=str(event.id),
            serializer="json",
        )
        event.state = "published"
        event.published_at = datetime.now(UTC)
        return True


def recover_stale_processing(session_factory: sessionmaker[Session]) -> int:
    cutoff = datetime.now(UTC) - LEASE_TIMEOUT
    recovered = 0
    with session_factory() as session, session.begin():
        stale = list(
            session.scalars(
                select(Document)
                .where(
                    Document.processing_status == "processing",
                    Document.processing_started_at < cutoff,
                )
                .with_for_update(skip_locked=True)
                .limit(20)
            )
        )
        for document in stale:
            document.processing_status = "queued"
            document.processing_started_at = None
            document.claim_token = None
            session.add(
                OutboxEvent(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    event_type="process",
                    state="pending",
                )
            )
            recovered += 1
    return recovered
