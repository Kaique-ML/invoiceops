from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=80)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=500)


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    line_total: str | None = None


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: Literal["invoice", "receipt", "purchase_order", "unknown"] = "unknown"
    supplier: str | None = None
    tax_identifier: str | None = None
    document_number: str | None = None
    issue_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    discounts: str | None = None
    taxes: str | None = None
    shipping: str | None = None
    total: str | None = None
    tax_included_in_total: bool | None = None
    items: list[ExtractedItem] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)


class PageText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    text: str
    method: Literal["pdf-text", "tesseract"]


class ProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: InvoiceExtraction
    pages: list[PageText]
    mode: Literal["demo", "ollama"]
    model: str | None = None
    prompt_version: str
    issues: list[dict[str, str]] = Field(default_factory=list)


class ApprovedItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    line_total: str | None = None


class ApprovedInvoiceFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_type: Literal["invoice", "receipt", "purchase_order", "unknown"]
    supplier: str | None = None
    tax_identifier: str | None = None
    document_number: str | None = None
    issue_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    discounts: str | None = None
    taxes: str | None = None
    shipping: str | None = None
    total: str | None = None
    tax_included_in_total: bool | None = None
    items: list[ApprovedItemPayload]


class ApprovedRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["invoiceops.approved.v1"]
    event_id: str = Field(min_length=1, max_length=64)
    document_id: str = Field(min_length=1, max_length=64)
    revision_id: str = Field(min_length=1, max_length=64)
    approved_at: str = Field(min_length=1, max_length=64)
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fields: ApprovedInvoiceFields
