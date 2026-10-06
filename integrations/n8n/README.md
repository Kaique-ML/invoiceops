# n8n local demonstration

This is a local test destination, not an ERP. The Compose `n8n` profile uses the exact n8n 2.41.3 image digest recorded in this repository, binds its editor to loopback at port 5679, and stores n8n state in the persistent `n8n_data` volume. Port 5678 was already occupied on the observed host and was left untouched. The app and n8n share the internal network so the worker can reach the webhook; PostgreSQL is not published to the host.

## Local setup

1. Start the normal demo first: `.\scripts\demo.ps1`. The script generates and preserves an ignored local `N8N_ENCRYPTION_KEY`; do not publish `.env` or delete the persistent n8n volume.
2. Start n8n: `docker compose --profile n8n up -d n8n`, then open <http://127.0.0.1:5679> and complete the local owner setup.
3. In n8n, create a **Postgres** credential for host `db`, port `5432`, database `invoiceops`, user `invoiceops`, and the local `DB_PASSWORD` from the ignored `.env`. Use SSL disabled for this internal development network. Select this credential on the Postgres node. This demo uses the application's database user for convenience; a production destination must use a separate least-privilege role.
4. Run `docker compose exec -T db psql -U invoiceops -d invoiceops -v ON_ERROR_STOP=1 -f /dev/stdin` and provide `setup.sql` on standard input, or execute the contents of [setup.sql](setup.sql) in the local database. The unique primary key is the atomic idempotency constraint.
5. Import `invoiceops-approved-record.json` from the n8n editor. Create a **Header Auth** credential with header name `Authorization` and value `Bearer <the local WEBHOOK_SECRET from .env>`, then select it on the Webhook node. Credentials are intentionally not embedded in the export.
6. Activate the imported workflow. To deliver an approved InvoiceOps record to it, change only the ignored local `.env` value `WEBHOOK_URL` to `http://n8n:5678/webhook/invoiceops/approved`, then recreate the worker with `docker compose up -d --no-deps --force-recreate worker`.
7. Confirm `invoiceops_n8n_demo_records` contains the event. A same-key/same-JSON replay is an idempotent success. A same-key/different-JSON request returns conflict and is not written. InvoiceOps treats a non-processed response as an unsuccessful delivery; it does not claim that downstream business processing occurred.

Use `docker compose --profile n8n logs --tail 100 n8n` for diagnostics. Do not publish the local owner password, n8n encryption key, DB password, or webhook secret. The local HTTP endpoint and `N8N_SECURE_COOKIE=false` are development-only.

The import, activation, and persistent receipt remain **unverified** until exercised against this exact stack. The application’s separate local test receiver has been exercised; that result is not evidence of an n8n run.
