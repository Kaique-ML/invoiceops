# Demonstration script

Use only the bundled synthetic files. Start with `./scripts/demo.ps1`, seed the fictional workspace, and sign in with the one-time password printed by the seed command.

1. Upload `assets/demo/synthetic_invoice.pdf`. Show the queued/processing/completed states, page evidence and the prominent `DEMO — EXTRAÇÃO SIMULADA` label.
2. Correct one field with a reason, save a new revision, inspect the audit history, then approve it. Explain that validation is not truth verification and approval is always human.
3. Upload the same bytes again. Show that the existing workspace record is returned and no second processing job is created.
4. Upload the scanned PDF or PNG/JPEG sample. Show the real OCR method in page evidence while keeping the structured demo result clearly identified as simulated.
5. Approve a consistent revision, download CSV and XLSX, then send it to the authenticated local test receiver. Show the stable idempotency key and delivered state.
6. Correct the approved record. Show that approval is revoked, the historical delivery remains, and a new approval/delivery is required.
7. For a recovery case, stop Redis before upload, confirm the durable outbox intent remains in PostgreSQL, restart Redis, and wait for the dispatcher to publish it. Do not delete volumes.

The optional n8n flow is separate. Follow `integrations/n8n/README.md`; do not describe it as verified until the workflow is imported, credentialed, activated and receives a persisted event.
