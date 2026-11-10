# Commercial lifecycle implementation — 10 November 2026

**Release decision: PENDING. This is a tested local implementation, not a completed commercial launch.** No public deployment, live payment, customer charge or sandbox resource was authorized or performed.

## What changed

Organization Settings now contains a provider-backed **test billing console** for OWNER/ADMIN. It loads configured plan prices from Razorpay rather than inventing a price, binds checkout to a verified quote, prepares a hosted test authorization link, reconciles provider subscription state, requests period-end cancellation, resolves uncertain operations using verified provider references, and displays sanitized invoice and subscription history. The console clearly reports an unavailable provider when credentials are absent. Existing free local development use is preserved; unknown states on linked provider subscriptions fail closed.

Additive migration **0011** creates three forced-RLS tables: `billing_operations`, `billing_snapshots`, `invoice_snapshots`. The latter two are append-only histories protected against update/delete/truncate. No previous migration was rewritten. Current subscriptions, immutable webhook/usage ledgers and atomic quotas remain in place.

Provider writes first commit a durable intent. A timeout or ambiguous response becomes UNKNOWN and is never automatically reissued. A verified hosted URL means authorization is prepared; it does **not** mean payment succeeded. Activation requires a verified signed event or authoritative reconciliation. Reconciliation uses a version fence so an older provider read cannot overwrite a newer event. Cancellation is requested at period end, not falsely reported complete on click. Invoice ingestion verifies subscription binding, retains historical snapshots and excludes customer/contact/card details. Unknown draft amounts remain unknown. Provider POSTs disable customer notifications.

Checkout and cancellation are separately disabled by `ORQENTRA_BILLING_TEST_ACTIONS_ENABLED=false`. The only supported integration mode is test, with `rzp_test_` keys; production activation remains prohibited. Previous webhook signing secrets require a timezone-aware expiry no more than two days away and stop verifying once expired. No fake active subscription, invoice or payment was seeded.

## Hosted maintenance job

`scripts/hosted_database.py` is a separate operator entry point, never called by API/worker startup. Its `validate` action is offline. `check` connects read-only at the application level to verify schema head/drift and restricted runtime grants. `upgrade` performs forward migrations and reapplies reviewed grants. It requires an explicit target host/database, separate migration/runtime credentials, verified TLS, an operator backup reference, and a PostgreSQL advisory lock. It refuses unversioned domain tables and never resets data or rotates runtime passwords.

Operators must provision the `orqentra_runtime` login and the narrowly scoped identity definer owner privileges before using a managed database; managed provider permission compatibility has **not** been observed. The job validates the runtime connection, role inheritance, ownership, read access and forced RLS. API/worker environments must never receive migration credentials.

Example from a reviewed checkout, with both DSNs supplied through an approved secret manager:

```sh
uv run --locked --package orqentra-api python scripts/hosted_database.py validate \
  --environment staging --host YOUR_DATABASE_HOST --database YOUR_DATABASE_NAME
uv run --locked --package orqentra-api python scripts/hosted_database.py check \
  --environment staging --host YOUR_DATABASE_HOST --database YOUR_DATABASE_NAME
```

Only after resource approval, a provider backup and restore rehearsal, run `upgrade` with `--backup-reference PROVIDER_BACKUP_ID`. A supplied reference is an operator assertion, not evidence that the backup restores. The manual-only `database-maintenance.yml` workflow has no push trigger, cloud provisioning or deployment step. Configure its GitHub Environment with required reviewers, target variables and job-only secrets before use. It has not been triggered. Existing Render templates remain unapplied.

## Payload-safe tracing

Optional manual OpenTelemetry API request spans now use bounded batching, a 10% sample rate, an explicit service resource, fixed route templates, method and response status. There is no automatic HTTP/SQL/model instrumentation. No request body, URL query, authorization header, user identity, document, prompt, code, exception text, baggage or tracestate is exported. Incoming valid trace parents correlate to fresh server spans; logs and responses share those identifiers. Export transport rejects redirects and does not import proxy/netrc credentials. Shutdown drains the bounded provider lifecycle.

Tracing exports are **off by default**. To opt in, configure `ORQENTRA_TRACING_ENDPOINT=https://YOUR-APPROVED-COLLECTOR/v1/traces` in the ignored backend `.env.telemetry` or hosted API secret configuration; use an approved HTTPS collector with network access controls. URLs containing credentials, query strings or fragments are rejected. No collector account was created or contacted. Worker spans, cross-queue trace continuity, exporter delivery/failure drills, metrics, alerts and monitored SLOs remain open; request tracing alone does not satisfy full observability acceptance.

The initial OTel 1.44.0 audit found CVE-2026-114603; the lock now pins the API/SDK/exporter to **1.45.1**, and the subsequent locked runtime dependency audit reports no known vulnerabilities. This is not an independent security or container-image assessment.

## Actual validation

- **103 backend unit tests passed**; lint, formatting and strict type checking passed. The plain backend command separately skips database cases; those are not counted as passes.
- **98 PostgreSQL integration tests passed**, with three explicit real-model opt-ins skipped. Tests use disposable databases and signed synthetic development identities, not a real Razorpay merchant or Clerk browser session.
- **61 frontend tests and 4 CSP/build-policy tests passed**, plus lint, type checking, production build and OpenAPI contract drift checks.
- Billing fixtures cover concurrent checkout deduplication, stale quote rejection, uncertain POST recovery without resending, exact provider-operation binding, pending access denial, authoritative activation/expiry, cancellation deduplication, invoice sanitization/deduplication, role/tenant denial, and reconcile/webhook races.
- An in-memory exporter test observes a failing API request with private path/query/body/authorization/baggage inputs and verifies that the exported span contains only the fixed route, method and status, with no exception events or private text. This is not real collector delivery evidence.
- Hosted-job tests verify exact TLS/host/database validation and prove `validate` opens no connection or prints credentials. Offline staging/production manifest policy checks passed; no hosted database was contacted.
- Migration 0011 applied locally after private backup `.local/backups/20261110T072002265322Z.dump`. All 25 preexisting table counts were unchanged. The backup restored successfully into a generated disposable database at revision 0010 with all 25 original domain tables under forced RLS; the temporary database was removed afterward.

Post-rebuild verification: all four local containers healthy; `/api/v1/health` and `/api/v1/ready` return **200**, anonymous `/api/v1/me` returns **401**, and disabled billing callback POST returns **503**. **Seven anonymous browser checks passed**, with the unconfigured-auth-only case correctly skipped for the configured Clerk build. It does not verify a real signed-in session or clear the separate 2C gate. Deployed billing/telemetry source hashes match the tested checkout.

Read-only inspection confirms revision **0011**, **28 forced-RLS tables**, one real user with zero duplicate subjects, two organizations/memberships/workspaces, 24 fictional profiles, 26 knowledge documents, three chats/four exchanges and four teammates. Subscriptions, provider operations, invoice/subscription snapshots, usage events and code executions are all still zero. The restricted runtime verifier passed locally; this is not hosted-provider evidence. Completed real OpenAI checks from the earlier functional release were not needlessly repeated.

Known limits: the frontend build still reports a large bundle warning; one existing Pydantic alias warning remains in the database suite. Neither is represented as a security acceptance result.

## Remaining commercial gates

1. Real Razorpay test checkout/authorization, event delivery, rotation, renewal, cancellation and invoice acceptance; approved prices/quotas and tax/refund/accounting requirements. No live payment mode is implemented or authorized.
2. Approved Render/managed database accounts and resources, production Clerk, managed secrets, domain/TLS/ingress validation, hosted role/migration/restore and rollback rehearsal. Applying templates would create resources and still requires explicit approval.
3. Reviewed E2B account/template and explicit resource authorization; real deny-network, resource/timeout, cleanup and escape tests. Execution remains disabled, with no host-code fallback.
4. Remaining 2C genuine invalidation interval, two-real-human support journey, expanded measured RAG/agent reliability, queue/load/crash tests, monitored SLOs/alerts, backup RPO/RTO and security review.
5. Customer-selected outbound connectors, workflow composition, workspace-specific per-user grants, broader ingestion, and Stripe support remain beyond the current implemented release. Generic arbitrary tools and a fully configurable multi-agent workflow editor have not been represented as complete.

All development data and Docker volumes are preserved. The full commercial platform is **not yet accepted**, and these remaining gates must not be replaced with simulated success.
