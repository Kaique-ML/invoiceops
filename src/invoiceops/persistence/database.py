from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from invoiceops.settings import Settings


class Base(DeclarativeBase):
    pass


def make_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with factory() as session:
        yield session
