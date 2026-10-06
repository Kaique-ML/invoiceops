from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from invoiceops.api import (
    _approve,
    _approved_rows,
    _get_document,
    _metrics_text,
    _request_delivery,
    _save_review,
    require_reviewer,
)
from invoiceops.persistence.models import (
    AuditEvent,
    Delivery,
    Document,
    OutboxEvent,
    Revision,
    User,
    Workspace,
)
from invoiceops.services.queue import publish_outbox_event

pytestmark = pytest.mark.integration


def _document_graph(session: Session) -> tuple[User, Document, Revision]:
    workspace = Workspace(name=f"Integration {uuid4()}")
    session.add(workspace)
    session.flush()
    user = User(
        workspace_id=workspace.id,
        username=f"reviewer-{uuid4()}",
        password_hash="not-used-by-this-test",
        role="admin",
    )
    session.add(user)
    session.flush()
    document = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        original_name="synthetic.pdf",
        content_type="application/pdf",
        sha256=uuid4().hex + uuid4().hex,
        size_bytes=128,
        storage_key=f"integration/{uuid4()}",
        processing_status="completed",
        review_status="pending",
    )
    session.add(document)
    session.flush()
    extracted = {
        "document_type": "invoice",
        "supplier": "Synthetic Supplier",
        "currency": "BRL",
        "total": "10.00",
        "items": [],
        "evidence": [
            {"field": "document_type", "page": 1, "quote": "Document Type: Invoice"},
            {"field": "supplier", "page": 1, "quote": "Supplier: Synthetic Supplier"},
            {"field": "currency", "page": 1, "quote": "Currency: BRL"},
            {"field": "total", "page": 1, "quote": "Total: 10.00"},
        ],
    }
    revision = Revision(
        document_id=document.id,
        number=1,
        kind="extraction",
        source_pages=[
            {
                "page": 1,
                "text": (
                    "Document Type: Invoice\nSupplier: Synthetic Supplier\n"
                    "Currency: BRL\nTotal: 10.00"
                ),
                "method": "pdf-text",
            }
        ],
        extracted=extracted,
        normalized={
            "document_type": "invoice",
            "supplier": "Synthetic Supplier",
            "currency": "BRL",
            "total": "10.00",
            "items": [],
            "field_provenance": {},
        },
        issues=[],
        mode="demo",
        prompt_version="invoice-extract-v1",
        amount_total="10.00",
    )
    session.add(revision)
    session.commit()
    return user, document, revision


def test_approved_correction_revokes_current_approval_but_preserves_delivery(
    postgres_session: Session,
) -> None:
    user, document, original_revision = _document_graph(postgres_session)
    _approve(postgres_session, user, document.id, expected_version=1)
    delivery, duplicate = _request_delivery(postgres_session, user, document.id)
    assert duplicate is False

    _save_review(
        postgres_session,
        user,
        document.id,
        expected_version=2,
        changes={"supplier": "Corrected Supplier"},
        reason="Verified against the synthetic source.",
    )

    postgres_session.refresh(document)
    postgres_session.refresh(original_revision)
    revisions = list(
        postgres_session.scalars(
            select(Revision).where(Revision.document_id == document.id).order_by(Revision.number)
        )
    )
    assert original_revision.approved_at is None
    assert original_revision.approved_by is None
    assert revisions[-1].normalized["supplier"] == "Corrected Supplier"
    assert revisions[-1].approved_at is None
    assert document.review_status == "pending"
    assert document.delivery_status == "not_requested"
    assert postgres_session.get(Delivery, delivery.id) is not None
    assert _approved_rows(postgres_session, user) == []
    actions = set(
        postgres_session.scalars(
            select(AuditEvent.action).where(AuditEvent.document_id == document.id)
        )
    )
    assert {"approved", "delivery_requested", "field_corrected", "approval_revoked"} <= actions


def test_outbox_remains_pending_when_broker_publish_fails(
    postgres_session: Session,
) -> None:
    user, document, _ = _document_graph(postgres_session)
    event = OutboxEvent(
        workspace_id=user.workspace_id,
        document_id=document.id,
        event_type="process",
        state="pending",
    )
    postgres_session.add(event)
    postgres_session.commit()
    event_id = event.id
    factory = sessionmaker(
        bind=postgres_session.get_bind(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    celery_app = Celery("outbox-failure-test")

    def fail_publish(*args: object, **kwargs: object) -> None:
        raise ConnectionError("synthetic broker outage")

    celery_app.send_task = fail_publish  # type: ignore[method-assign]
    with pytest.raises(ConnectionError, match="synthetic broker outage"):
        publish_outbox_event(factory, celery_app, event_id)
    postgres_session.expire_all()
    persisted = postgres_session.get(OutboxEvent, event_id)
    assert persisted is not None
    assert persisted.state == "pending"


def test_workspace_scope_roles_and_exact_duplicate_constraint(postgres_session: Session) -> None:
    owner, document, _ = _document_graph(postgres_session)
    other_workspace = Workspace(name=f"Other {uuid4()}")
    postgres_session.add(other_workspace)
    postgres_session.flush()
    reader = User(
        workspace_id=other_workspace.id,
        username=f"reader-{uuid4()}",
        password_hash="not-used-by-this-test",
        role="reader",
    )
    postgres_session.add(reader)
    postgres_session.commit()

    with pytest.raises(HTTPException) as hidden:
        _get_document(postgres_session, reader, document.id)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as forbidden:
        require_reviewer(reader)
    assert forbidden.value.status_code == 403

    duplicate = Document(
        workspace_id=owner.workspace_id,
        uploaded_by=owner.id,
        original_name="same-content.pdf",
        content_type="application/pdf",
        sha256=document.sha256,
        size_bytes=128,
        storage_key=f"integration/{uuid4()}",
    )
    with pytest.raises(IntegrityError), postgres_session.begin_nested():
        postgres_session.add(duplicate)
        postgres_session.flush()


def test_metrics_are_aggregate_and_do_not_expose_document_ids(postgres_session: Session) -> None:
    _, document, _ = _document_graph(postgres_session)
    payload = _metrics_text(postgres_session)
    assert 'invoiceops_documents_total{processing_status="completed"}' in payload
    assert "invoiceops_processing_duration_milliseconds_sum" in payload
    assert str(document.id) not in payload


def test_real_redis_celery_worker_consumes_json_task() -> None:
    redis_url = os.environ["REDIS_URL"]
    app = Celery(
        f"invoiceops-integration-{uuid4()}",
        broker=redis_url,
        backend=redis_url,
    )
    queue_name = f"invoiceops-integration-{uuid4().hex}"
    app.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        task_default_queue=queue_name,
        result_expires=60,
    )

    @app.task(name=f"invoiceops.integration.echo.{uuid4().hex}")
    def echo(value: str) -> dict[str, str]:
        return {"value": value, "processed_at": datetime.now(UTC).isoformat()}

    with start_worker(app, pool="solo", concurrency=1, perform_ping_check=False):
        result = echo.delay("real-redis")
        payload = result.get(timeout=15)
    assert payload["value"] == "real-redis"
    assert payload["processed_at"].endswith("+00:00")
