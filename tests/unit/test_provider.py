from pathlib import Path
from types import SimpleNamespace

from invoiceops.domain.schemas import PageText
from invoiceops.providers.ollama_provider import OllamaStructuredProvider
from invoiceops.settings import Settings


class FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.contents = iter(contents)
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content=next(self.contents)),
            model="fixture-model",
        )


def settings() -> Settings:
    return Settings(
        app_env="test",
        mode="real",
        database_url="postgresql+psycopg://unused",
        redis_url="redis://localhost",
        session_secret="x" * 32,
        upload_dir=Path("uploads"),
        max_upload_bytes=1024,
        max_pages=2,
        max_image_pixels=1000,
        ollama_host="http://127.0.0.1:11434",
        ollama_model="verified-local-tag",
        webhook_url="",
        webhook_secret="",
    )


def test_schema_invalid_response_gets_only_one_repair_attempt(monkeypatch) -> None:
    client = FakeClient(["not-json", "still-not-json"])
    monkeypatch.setattr(
        "invoiceops.providers.ollama_provider.Client",
        lambda **kwargs: client,
    )
    provider = OllamaStructuredProvider(settings())
    try:
        provider.extract([PageText(page=1, text="Invoice", method="pdf-text")])
    except ValueError as exc:
        assert "schema-invalid" in str(exc)
    else:
        raise AssertionError("Invalid structured output must not be accepted.")
    assert len(client.calls) == 2


def test_missing_field_evidence_gets_one_repair_and_is_reported(monkeypatch) -> None:
    response = '{"supplier":"Invented Ltd.","total":"8.00"}'
    client = FakeClient([response, response])
    monkeypatch.setattr(
        "invoiceops.providers.ollama_provider.Client",
        lambda **kwargs: client,
    )
    provider = OllamaStructuredProvider(settings())
    extraction, model, issues = provider.extract(
        [PageText(page=1, text="A different invoice", method="pdf-text")]
    )
    assert extraction.supplier == "Invented Ltd."
    assert model == "verified-local-tag"
    assert len(client.calls) == 2
    assert {issue["code"] for issue in issues} == {"missing_evidence"}
