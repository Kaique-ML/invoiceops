from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str
    mode: str
    database_url: str
    redis_url: str
    session_secret: str
    upload_dir: Path
    max_upload_bytes: int
    max_pages: int
    max_image_pixels: int
    ollama_host: str
    ollama_model: str
    webhook_url: str
    webhook_secret: str

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            mode=os.getenv("INVOICEOPS_MODE", "demo"),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://invoiceops:invoiceops@localhost:5432/invoiceops",
            ),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            session_secret=os.getenv("SESSION_SECRET", ""),
            upload_dir=Path(os.getenv("UPLOAD_DIR", "data/uploads")),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "10485760")),
            max_pages=int(os.getenv("MAX_PAGES", "50")),
            max_image_pixels=int(os.getenv("MAX_IMAGE_PIXELS", "20000000")),
            ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", ""),
            webhook_url=os.getenv("WEBHOOK_URL", ""),
            webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
        )

    def validate(self) -> None:
        if self.mode not in {"demo", "real"}:
            raise ValueError("INVOICEOPS_MODE must be 'demo' or 'real'.")
        if len(self.session_secret) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters.")
        if min(self.max_upload_bytes, self.max_pages, self.max_image_pixels) <= 0:
            raise ValueError("Upload, page, and image-pixel limits must be positive.")
