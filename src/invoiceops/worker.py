from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import cast
from uuid import UUID, uuid4

import httpx
from celery import Celery
from celery.utils.log import get_task_logger
from kombu.exceptions import OperationalError as BrokerOperationalError
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from invoiceops.domain.validation import is_possible_business_duplicate
from invoiceops.extraction.documents import DocumentLimitError, UnsupportedDocumentError
from invoiceops.persistence.database import make_session_factory
from invoiceops.persistence.models import (
    Delivery,
    Document,
    OutboxEvent,
    ProcessingAttempt,
    Revision,
)
from invoiceops.providers.ollama_provider import StructuredOutputError
from invoiceops.services.processing import (
    InvalidDemoDocumentError,
    RetryableExtractionError,
    normalize_extraction,
    process_bytes,
)
from invoiceops.services.storage import LocalDocumentStorage
from invoiceops.services.webhook import (
    ConfiguredWebhookSink,
    WebhookConfigurationError,
)
from invoiceops.settings import Settings

settings = Settings.from_environment()
celery_app = Celery("invoiceops", broker=settings.redis_url)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
)
logger = get_task_logger(__name__)
session_factory = make_session_factory(settings)
storage = LocalDocumentStorage(settings.upload_dir, max_bytes=settings.max_upload_bytes)


@celery_app.task(
    name="invoiceops.process_document",
    acks_late=True,
    reject_on_worker_lost=True,
)  # type: ignore[untyped-decorator]
def process_document(document_id: str, outbox_id: str) -> dict[str, str]:
    document_uuid = UUID(document_id)
    outbox_uuid = UUID(outbox_id)
    claim_token = str(uuid4())
    started_clock = perf_counter()
    with session_factory() as session, session.begin():
        document = session.scalar(
            select(Document).where(Document.id == document_uuid).with_for_update()
        )
        if document is None:
            return {"state": "missing"}
        if document.processing_status != "queued":
            return {"state": "duplicate"}
        document.processing_status = "processing"
        document.processing_attempts += 1
        attempt = ProcessingAttempt(
            document_id=document_uuid,
            number=document.processing_attempts,
            state="processing",
        )
        session.add(attempt)
        session.flush()
        attempt_uuid = attempt.id
        document.processing_started_at = datetime.now(UTC)
        document.claim_token = claim_token
        document.last_error = None
        event = session.get(OutboxEvent, outbox_uuid)
        if event is not None:
            event.attempts += 1

    try:
        content = storage.read(document.storage_key)
        result = process_bytes(content, document.original_name, settings)
        normalized, normalization_issues = normalize_extraction(result.extraction)
        issues = result.issues + normalization_issues
    except RetryableExtractionError:
        if document.processing_attempts < 3:
            _schedule_retry(
                document_uuid,
                claim_token,
                attempt_uuid,
                "Local extraction provider did not respond; a bounded retry was scheduled.",
                delay_seconds=5 * (2 ** (document.processing_attempts - 1)),
            )
            return {"state": "retry_scheduled"}
        _record_failure(
            document_uuid,
            claim_token,
            attempt_uuid,
            "Local extraction provider did not respond after bounded retries.",
            int((perf_counter() - started_clock) * 1000),
        )
        return {"state": "failed"}
    except (OSError, ValueError, RuntimeError) as exc:
        safe_message = _safe_failure_message(exc)
        _record_failure(
            document_uuid,
            claim_token,
            attempt_uuid,
            safe_message,
            int((perf_counter() - started_clock) * 1000),
        )
        logger.warning(
            "document processing failed",
            extra={"document_id": document_id, "error_type": type(exc).__name__},
        )
        raise

    with session_factory() as session, session.begin():
        document = session.scalar(
            select(Document).where(Document.id == document_uuid).with_for_update()
        )
        if document is None or document.claim_token != claim_token:
            return {"state": "stale_result_discarded"}
        previous = session.scalar(
            select(Revision)
            .where(Revision.document_id == document_uuid)
            .order_by(Revision.number.desc())
            .limit(1)
        )
        duplicate_id = _find_possible_business_duplicate(session, document, normalized)
        if duplicate_id is not None:
            issues.append(
                {
                    "code": "possible_duplicate",
                    "field": "document",
                    "message": (
                        "Possible business duplicate in this workspace: "
                        f"document {duplicate_id}. Review both records before approval."
                    ),
                }
            )
        revision = Revision(
            document_id=document_uuid,
            number=(previous.number + 1) if previous else 1,
            kind="extraction",
            source_pages=[page.model_dump(mode="json") for page in result.pages],
            extracted=result.extraction.model_dump(mode="json"),
            normalized=normalized,
            issues=issues,
            mode=result.mode,
            model_name=result.model,
            prompt_version=result.prompt_version,
            amount_subtotal=_as_decimal(normalized.get("subtotal")),
            amount_discounts=_as_decimal(normalized.get("discounts")),
            amount_taxes=_as_decimal(normalized.get("taxes")),
            amount_shipping=_as_decimal(normalized.get("shipping")),
            amount_total=_as_decimal(normalized.get("total")),
            latency_ms=int((perf_counter() - started_clock) * 1000),
        )
        session.add(revision)
        attempt_record = session.get(ProcessingAttempt, attempt_uuid)
        if attempt_record is not None:
            attempt_record.state = "completed"
            attempt_record.finished_at = datetime.now(UTC)
            attempt_record.duration_ms = int((perf_counter() - started_clock) * 1000)
        document.processing_status = "completed"
        document.review_status = "needs_review" if issues else "pending"
        document.processing_started_at = None
        document.claim_token = None
        document.last_error = None
        document.version += 1
    logger.info("document processing completed", extra={"document_id": document_id})
    return {"state": "completed"}


@celery_app.task(
    name="invoiceops.deliver_approved_record",
    acks_late=True,
    reject_on_worker_lost=True,
)  # type: ignore[untyped-decorator]
def deliver_approved_record(delivery_id: str, outbox_id: str) -> dict[str, str]:
    delivery_uuid = UUID(delivery_id)
    event_uuid = UUID(outbox_id)
    with session_factory() as session, session.begin():
        delivery = session.scalar(
            select(Delivery).where(Delivery.id == delivery_uuid).with_for_update()
        )
        if delivery is None:
            return {"state": "missing"}
        if delivery.state not in {"pending", "unknown"}:
            return {"state": "duplicate"}
        delivery.state = "sending"
        delivery.attempts += 1
        payload = dict(delivery.payload)
        key = delivery.idempotency_key
        event = session.get(OutboxEvent, event_uuid)
        if event is not None:
            event.attempts += 1

    try:
        result = ConfiguredWebhookSink(settings).send(payload, key)
    except WebhookConfigurationError as exc:
        _finish_delivery(delivery_uuid, "failed", None, str(exc))
        return {"state": "failed"}
    except httpx.TimeoutException:
        _finish_delivery(
            delivery_uuid,
            "unknown",
            None,
            "Destination timed out; it may have processed the event.",
        )
        _schedule_delivery_retry(delivery_uuid)
        return {"state": "unknown"}
    except httpx.RequestError:
        _finish_delivery(
            delivery_uuid,
            "unknown",
            None,
            "Destination connection ended without a verifiable response.",
        )
        _schedule_delivery_retry(delivery_uuid)
        return {"state": "unknown"}

    if 200 <= result.status_code < 300 and result.processed:
        _finish_delivery(delivery_uuid, "delivered", result.status_code, None)
        return {"state": "delivered"}
    if result.status_code == 429 or result.status_code >= 500:
        retry_state = "pending"
        message = f"Destination returned retryable HTTP {result.status_code}."
        _finish_delivery(delivery_uuid, retry_state, result.status_code, message)
        _schedule_delivery_retry(delivery_uuid)
        return {"state": retry_state}
    if 200 <= result.status_code < 300:
        _finish_delivery(
            delivery_uuid,
            "unknown",
            result.status_code,
            "Destination returned success without a processed acknowledgement.",
        )
        _schedule_delivery_retry(delivery_uuid)
        return {"state": "unknown"}
    _finish_delivery(
        delivery_uuid,
        "failed",
        result.status_code,
        f"Destination rejected the event with HTTP {result.status_code}.",
    )
    return {"state": "failed"}


def _schedule_retry(
    document_id: UUID,
    claim_token: str,
    attempt_id: UUID,
    error: str,
    *,
    delay_seconds: int,
) -> None:
    with session_factory() as session, session.begin():
        document = session.scalar(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        if document is None or document.claim_token != claim_token:
            return
        document.processing_status = "queued"
        document.processing_started_at = None
        document.claim_token = None
        document.last_error = error[:500]
        attempt = session.get(ProcessingAttempt, attempt_id)
        if attempt is not None:
            attempt.state = "failed"
            attempt.finished_at = datetime.now(UTC)
            attempt.error = "Transient local provider failure; bounded retry scheduled."
        session.add(
            OutboxEvent(
                workspace_id=document.workspace_id,
                document_id=document.id,
                event_type="process",
                state="pending",
                available_at=datetime.now(UTC) + timedelta(seconds=delay_seconds),
            )
        )


def _record_failure(
    document_id: UUID,
    claim_token: str,
    attempt_id: UUID,
    error: str,
    duration_ms: int,
) -> None:
    with session_factory.begin() as session:
        session.execute(
            update(Document)
            .where(Document.id == document_id, Document.claim_token == claim_token)
            .values(
                processing_status="failed",
                processing_started_at=None,
                claim_token=None,
                last_error=error[:500],
                review_status="needs_review",
                version=Document.version + 1,
            )
        )
        attempt = session.get(ProcessingAttempt, attempt_id)
        if attempt is not None:
            attempt.state = "failed"
            attempt.finished_at = datetime.now(UTC)
            attempt.duration_ms = duration_ms
            attempt.error = error


def _finish_delivery(
    delivery_id: UUID,
    state: str,
    response_status: int | None,
    error: str | None,
) -> None:
    with session_factory() as session, session.begin():
        delivery = session.scalar(
            select(Delivery).where(Delivery.id == delivery_id).with_for_update()
        )
        if delivery is None:
            return
        delivery.state = state
        delivery.response_status = response_status
        delivery.last_error = error
        document = session.get(Document, delivery.document_id)
        if document is not None:
            document.delivery_status = state


def _schedule_delivery_retry(delivery_id: UUID) -> None:
    with session_factory() as session, session.begin():
        delivery = session.scalar(
            select(Delivery).where(Delivery.id == delivery_id).with_for_update()
        )
        if delivery is None or delivery.attempts >= 3:
            return
        session.add(
            OutboxEvent(
                workspace_id=delivery.workspace_id,
                document_id=delivery.document_id,
                delivery_id=delivery.id,
                event_type="delivery",
                state="pending",
                available_at=datetime.now(UTC)
                + timedelta(seconds=5 * (2 ** (delivery.attempts - 1))),
            )
        )


def dispatch_pending_once() -> int:
    from invoiceops.services.queue import publish_outbox_event

    published = 0
    with session_factory() as session:
        ids = list(
            session.scalars(
                select(OutboxEvent.id)
                .where(
                    OutboxEvent.state == "pending",
                    OutboxEvent.available_at <= datetime.now(UTC),
                )
                .order_by(OutboxEvent.created_at)
                .limit(20)
            )
        )
    for event_id in ids:
        try:
            publish_outbox_event(session_factory, celery_app, event_id)
            published += 1
        except OperationalError:
            logger.warning("database unavailable while dispatching durable outbox event")
        except (ConnectionError, TimeoutError, BrokerOperationalError):
            logger.warning("queue unavailable; durable outbox event remains pending")
    return published


def recover_stale_deliveries(session_factory: sessionmaker[Session]) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    recovered = 0
    with session_factory() as session, session.begin():
        stale = list(
            session.scalars(
                select(Delivery)
                .where(Delivery.state == "sending", Delivery.updated_at < cutoff)
                .with_for_update(skip_locked=True)
                .limit(20)
            )
        )
        for delivery in stale:
            delivery.state = "unknown"
            delivery.last_error = (
                "Worker lease expired after send began; external receipt is uncertain."
            )
            document = session.get(Document, delivery.document_id)
            if document is not None:
                document.delivery_status = "unknown"
            if delivery.attempts < 3:
                session.add(
                    OutboxEvent(
                        workspace_id=delivery.workspace_id,
                        document_id=delivery.document_id,
                        delivery_id=delivery.id,
                        event_type="delivery",
                        state="pending",
                        available_at=datetime.now(UTC)
                        + timedelta(seconds=5 * (2 ** (delivery.attempts - 1))),
                    )
                )
            recovered += 1
    return recovered


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Normalized money values must be decimal strings.")
    return Decimal(value)


def _find_possible_business_duplicate(
    session: Session,
    document: Document,
    normalized: dict[str, object],
) -> UUID | None:
    rows = session.execute(
        select(Document.id, Revision.normalized)
        .join(Revision, Revision.document_id == Document.id)
        .where(
            Document.workspace_id == document.workspace_id,
            Document.id != document.id,
            Document.sha256 != document.sha256,
            Document.processing_status == "completed",
        )
        .order_by(Document.id, Revision.number.desc())
    )
    seen: set[UUID] = set()
    for raw_candidate_id, raw_candidate_values in rows:
        candidate_id = cast(UUID, raw_candidate_id)
        candidate_values = cast(dict[str, object], raw_candidate_values)
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        if is_possible_business_duplicate(normalized, candidate_values):
            return candidate_id
    return None


def _safe_failure_message(error: Exception) -> str:
    if isinstance(
        error,
        (
            DocumentLimitError,
            UnsupportedDocumentError,
            InvalidDemoDocumentError,
            StructuredOutputError,
        ),
    ):
        return str(error)[:500]
    if isinstance(error, FileNotFoundError):
        return "The stored source file is unavailable."
    return "Document parsing or extraction failed. Correct the source/configuration and retry."
