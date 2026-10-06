from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from invoiceops.services.sinks import ApprovedRecordSink, SinkResult
from invoiceops.settings import Settings

LOCAL_DEVELOPMENT_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal", "api", "n8n"}
)


class WebhookConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookResult:
    status_code: int
    processed: bool


class ConfiguredWebhookSink(ApprovedRecordSink):
    def __init__(self, settings: Settings) -> None:
        if not settings.webhook_url:
            raise WebhookConfigurationError("WEBHOOK_URL is not configured.")
        if len(settings.webhook_secret) < 32:
            raise WebhookConfigurationError("WEBHOOK_SECRET must contain at least 32 characters.")
        self.url = settings.webhook_url
        self.secret = settings.webhook_secret
        self.app_env = settings.app_env
        self._validate_destination()

    def _validate_destination(self) -> None:
        parsed = urlsplit(self.url)
        host = parsed.hostname
        if (
            host is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.scheme not in {"https", "http"}
        ):
            raise WebhookConfigurationError("Webhook URL must be a credential-free HTTP(S) URL.")
        if self.app_env == "development" and host.casefold() in LOCAL_DEVELOPMENT_HOSTS:
            return
        if parsed.scheme != "https":
            raise WebhookConfigurationError("Non-local webhook destinations require HTTPS.")
        try:
            resolved = socket.getaddrinfo(
                host, parsed.port or 443, type=socket.SOCK_STREAM
            )
            addresses = set()
            for item in resolved:
                address_text = item[4][0]
                if isinstance(address_text, str):
                    addresses.add(ipaddress.ip_address(address_text.split("%", 1)[0]))
        except (OSError, ValueError) as exc:
            raise WebhookConfigurationError(
                "Webhook host did not resolve to a public address."
            ) from exc
        if not addresses or any(not address.is_global for address in addresses):
            raise WebhookConfigurationError(
                "Webhook host resolves to a private or reserved network address."
            )

    def send(self, payload: dict[str, object], idempotency_key: str) -> SinkResult:
        self._validate_destination()
        with httpx.Client(timeout=httpx.Timeout(10.0), follow_redirects=False) as client:
            with client.stream(
                "POST",
                self.url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.secret}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            ) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 8192:
                        break
                response_status = response.status_code
        if len(body) > 8192:
            return WebhookResult(status_code=response_status, processed=False)
        processed = False
        if 200 <= response_status < 300:
            try:
                payload_response = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload_response = {}
            processed = (
                isinstance(payload_response, dict) and payload_response.get("status") == "processed"
            )
        return WebhookResult(status_code=response_status, processed=processed)
