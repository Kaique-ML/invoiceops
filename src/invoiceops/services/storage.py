from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID


class DocumentStorage(Protocol):
    def store(self, workspace_id: UUID, document_id: UUID, content: bytes) -> str:
        """Store original bytes under a generated, private key."""

    def read(self, key: str) -> bytes:
        """Read an original file from a private generated key."""


class LocalDocumentStorage:
    def __init__(self, root: Path, *, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def store(self, workspace_id: UUID, document_id: UUID, content: bytes) -> str:
        if len(content) > self.max_bytes:
            raise ValueError(f"File exceeds the {self.max_bytes}-byte upload limit.")
        key = f"{workspace_id}/{document_id}"
        destination = (self.root / key).resolve()
        if self.root not in destination.parents:
            raise ValueError("Generated storage key escaped the configured private storage root.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(content)
        return key

    def read(self, key: str) -> bytes:
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents or not candidate.is_file():
            raise FileNotFoundError("Stored document was not found.")
        if candidate.stat().st_size > self.max_bytes:
            raise ValueError("Stored document exceeds the configured upload limit.")
        return candidate.read_bytes()

    def delete(self, key: str) -> None:
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Generated storage key escaped the configured private storage root.")
        candidate.unlink(missing_ok=True)
