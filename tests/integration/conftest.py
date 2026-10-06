from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get("INVOICEOPS_RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set INVOICEOPS_RUN_INTEGRATION=1 to run service tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def postgres_session() -> Generator[Session, None, None]:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
