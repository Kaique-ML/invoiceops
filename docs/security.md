# Security notes

InvoiceOps is a local portfolio demonstration, not a security certification or a claim of LGPD compliance.

Implemented controls include authenticated sessions, backend role checks, workspace-scoped queries, Argon2 password hashes, CSRF protection for cookie-authenticated writes, upload byte/page/pixel limits, signature-based file detection, generated storage names, a non-root worker, JSON-only task serialization, private service networks, escaped templates, restrictive browser headers, webhook destination configuration outside document data, stable idempotency keys, and formula-safe exports.

Do not expose PostgreSQL or Redis to the host network. Compose binds the web port to loopback. Do not use demonstration mode for arbitrary invoices and do not send sensitive documents to an LLM. The application does not provide payments, tax interpretation, immutable audit logs, a complete SSRF boundary, or a retention/deletion policy suitable for production. Webhook delivery must be treated as at-least-once unless the receiver implements idempotency.

Current implementation and verification status is listed in [acceptance.md](acceptance.md).

Before publication, tracked-file scanning searches for common credential patterns and verifies `.env`, local uploads, caches and virtual environments are ignored. This lightweight scan is not a substitute for a hosted secret scanner or a full production review.
