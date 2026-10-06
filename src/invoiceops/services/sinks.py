from __future__ import annotations

from typing import Protocol


class SinkResult(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def processed(self) -> bool: ...


class ApprovedRecordSink(Protocol):
    def send(self, payload: dict[str, object], idempotency_key: str) -> SinkResult:
        """Deliver one approved snapshot to a configured destination."""
