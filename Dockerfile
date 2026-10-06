FROM python@sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr=5.5.0-1+b1 \
        tesseract-ocr-eng=1:4.1.0-2 \
        tesseract-ocr-por=1:4.1.0-2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG INSTALL_DEV=0
COPY pyproject.toml README.md ./
COPY uv.lock ./
RUN pip install --no-cache-dir uv==0.11.7 \
    && uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
COPY assets ./assets
COPY evals ./evals
COPY web ./web
RUN if [ "$INSTALL_DEV" = "1" ]; then uv sync --frozen --all-extras; else uv sync --frozen --no-dev; fi

RUN groupadd --gid 10001 appgroup \
    && useradd --create-home --uid 10001 --gid 10001 appuser \
    && mkdir -p /var/lib/invoiceops/uploads \
    && chown -R appuser:appgroup /app /var/lib/invoiceops
USER 10001:10001

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "invoiceops.api:app", "--host", "0.0.0.0", "--port", "8000"]
