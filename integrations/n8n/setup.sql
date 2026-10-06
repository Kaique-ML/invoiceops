CREATE TABLE IF NOT EXISTS invoiceops_n8n_demo_records (
    idempotency_key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
