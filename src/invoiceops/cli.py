from __future__ import annotations

import secrets
import sys
from uuid import uuid4

from sqlalchemy import select

from invoiceops.api import password_hasher, session_factory
from invoiceops.persistence.models import User, Workspace

DEMO_WORKSPACE_NAME = "Cafe Aurora (fictional demonstration)"
DEMO_USERNAME = "demo-admin"


def seed_demo() -> None:
    password: str | None = None
    with session_factory() as session, session.begin():
        workspace = session.scalar(select(Workspace).where(Workspace.name == DEMO_WORKSPACE_NAME))
        if workspace is None:
            workspace = Workspace(id=uuid4(), name=DEMO_WORKSPACE_NAME)
            session.add(workspace)
            session.flush()
        user = session.scalar(
            select(User).where(
                User.workspace_id == workspace.id,
                User.username == DEMO_USERNAME,
            )
        )
        if user is None:
            password = secrets.token_urlsafe(24)
            session.add(
                User(
                    workspace_id=workspace.id,
                    username=DEMO_USERNAME,
                    password_hash=password_hasher.hash(password),
                    role="admin",
                    active=True,
                )
            )
    if password is None:
        print("The demo administrator already exists; no account or password was changed.")
        return
    print("Demo account created. Save this password now; it is not stored in plaintext.")
    print(f"Username: {DEMO_USERNAME}")
    print(f"Password: {password}")
    print("Workspace: Cafe Aurora (fictional demonstration)")


def main() -> None:
    if sys.argv[1:] != ["seed-demo"]:
        raise SystemExit("Usage: python -m invoiceops.cli seed-demo")
    seed_demo()


if __name__ == "__main__":
    main()
