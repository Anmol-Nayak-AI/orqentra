# Commercial operations baseline — 2026-11-09

This runbook describes the C1 baseline and C2/C3 local billing increment. It is not authorization to deploy or evidence that a production deployment exists. Use COMMERCIAL_ROADMAP.md for unfinished provider acceptance, sandbox and LangGraph work. No Render service, payment account or sandbox was created.

## Environments and containers

Development stays on the existing loopback-only Docker Compose stack and existing volumes. `staging` is now a distinct backend environment: explicit trusted hosts, HTTPS frontend origins, certificate-verified PostgreSQL TLS, bounded token lifetime, no runtime migration credentials and no public interactive API docs. Staging can use a separate Clerk development instance. Production adds rejection of development Clerk domains; production web builds require a `pk_live_` publishable key. Staging/production web builds refuse missing auth configuration.

The API/worker continue running as non-root without host code-execution or Docker-socket mounts. Local Compose remains read-only with tmpfs, dropped capabilities and no-new-privileges. Render templates use the same images, a private API, a worker and a public frontend definition; templates have automatic deployment disabled. **Do not apply them:** Render resource creation and public hosting require the user's separate explicit approval. Template compute sizes/region are examples, not measured capacity or a data-residency commitment.

The web entrypoint resolves the API using the platform DNS resolver. `ORQENTRA_API_UPSTREAM` defaults to `api:8000` locally; Render supplies the private service's `hostport`. Only hostname/port input is accepted, not URLs or shell syntax. It writes the rendered nginx configuration to `/tmp` and validates it before startup. TLS still terminates at the approved ingress; nginx's internal service connection is not a substitute for managed database TLS.

## Secrets and roles

Keep development/staging/production identities, databases and provider keys separate. Use a secret manager / provider environment configuration. Never commit `.env` files, put backend keys in Vite variables, or copy development records into a customer database. `infrastructure/production.env.example` is a template, not valid credentials.

Configure allowed hosts to include the frontend's exact hostname forwarded by the proxy and any exact internal health/operator hostname required by the deployment. The API Docker health probe uses the first allowed host. Configure the restricted runtime DSN with `sslmode=verify-full` and a trusted CA location appropriate to the provider. On Render, provision the CA through an approved secret file (for example `/etc/secrets/database-ca.pem`) if needed. Managed-owner connection strings must not be forwarded to API/worker.

Migration/provisioning remains a separate operator job with its own credentials and network access. The existing migration helper is explicitly local; it must not be pointed at a hosted database or described as a hosted migration job. A reviewed remote migration job is still required before Render acceptance. Runtime privileges and RLS must be checked against the real hosted database before traffic is admitted.

## Offline checks (no cloud calls)

```sh
uv run --locked --package orqentra-api python scripts/check_deployment_manifests.py
uv run --locked --package orqentra-api python scripts/production_preflight.py \
  --env-file PATH_TO_BACKEND_ENV --frontend-env-file PATH_TO_FRONTEND_ENV
```

Manifest checks validate YAML and local safety constraints only. Render CLI/provider validation has not run. The production preflight checks configuration without printing values; it always reports release approval false, and does not establish runtime permissions, a successful sign-in, TLS reachability or backup readiness. The current development configuration correctly fails that production preflight. CI runs tests and offline manifest/entrypoint validation; there is no automatic commercial deployment job.

## Observability

Structured API completion logs now include bounded W3C trace ID, a newly generated server span ID and request duration in milliseconds, alongside safe route/method/status/request IDs. Invalid trace headers are replaced. Headers, bodies, tokens, query strings and exception text are not added to logs. Incoming trace identifiers are correlation data, not identity or authorization evidence.

This is correlation/timing instrumentation, **not a complete distributed tracing installation**. No OTLP collector, vendor exporter, production alert destination or session replay is enabled. Worker/provider span propagation, tracing storage access controls, redaction tests and measured latency/error dashboards belong to the later observability gate. Liveness is `/api/v1/health`; readiness is `/api/v1/ready` and includes restricted DB/RLS checks but not live Clerk availability.

## Backups and rollback

1. Before a hosted change, identify the previous immutable image digest, schema compatibility, migration revision and rollback owner. Git history is not established in the current uncommitted workspace; do not invent a release SHA.
2. Create and verify an encrypted managed snapshot/PITR restore point with retention, access controls and residency appropriate to the customer. Local `.local/backups` dumps are private development evidence, not a managed production backup service.
3. Restore into a separate disposable database and verify schema, counts, tenant/RLS behavior and application reads. Record measured recovery time and data loss; RPO/RTO are currently unmeasured and uncommitted.
4. Apply only reviewed forward migrations through the separate migration role. Use expand/contract changes so the old application can still read during a rollout. Never give API/worker owner credentials or disable RLS for a deployment.
5. Roll back application images to the previously verified digest if compatibility allows; pause affected workers first to avoid competing side effects. Do not run `docker compose down -v`, `alembic downgrade`, or restore over the existing database as an automatic rollback.
6. For incompatible data repair, stop new writes, preserve the failed state, rehearse recovery into a separate database and obtain an explicit operator recovery decision. Reconcile external payment/tool side effects before resuming. No payment or sandbox side effects are currently enabled.

## Unfinished commercial acceptance

2C genuine provider-invalidation evidence, real two-person support, managed deployment/secret/CA verification, remote migrations/role provisioning, real billing-provider delivery/reconciliation, E2B enforcement, LangGraph recovery, connector approvals, quality/load/fault measurements and restore objectives remain open. The development build must not be sold as a production-certified service based solely on these tests or manifests.

## C2/C3 billing data and Razorpay test boundary

Migration 0008 adds organization subscriptions, daily quota buckets, immutable usage events and immutable webhook receipts. Every table uses forced tenant RLS. Existing records are retained. Quota reservation and accepted chat/task insertion commit together under an organization lock. Idempotent intake retries consume once. The first bucket includes existing same-day intake counts, without rewriting historical events. Known provider token usage is recorded per attempt, including known late results; embeddings and calls without reported usage remain excluded. This ledger is not invoice reconciliation.

Organization Settings shows server-owned policy allowances and availability. `development` and `pilot` are draft internal policy keys, not sold plans or pricing. Unsubscribed development/test environments retain bounded development allowances; hosted environments fail closed without an eligible subscription. Production paid entitlements are disabled regardless of subscription rows.

The default provider is `disabled`. `.env.billing.example` documents optional backend-only TEST configuration; no real file/account/key was created. The worker does not receive payment keys. Live key prefixes and production activation are rejected. The provider protocol supports verification and a bounded read-only subscription fetch; no subscription purchase, checkout, capture, refund or customer charge endpoint exists. Stripe is a future adapter, not an enabled integration.

An OWNER/ADMIN may link an **already existing test subscription** using `POST /api/v1/organizations/{id}/billing/test-subscription` only when test mode is configured. It verifies the remote plan against the server-owned plan mapping and the remote `notes.orqentra_organization_id` against the authenticated organization. Linking creates PENDING, never payment success or an ACTIVE entitlement. It does not create a provider subscription. Do not create provider resources as part of local verification without the separately required approval.

`POST /api/v1/billing/webhooks/razorpay` remains 503 while disabled. It verifies HMAC-SHA256 over raw bounded request bytes before parsing, binds callbacks to an existing local test subscription/organization/plan, and persists deduplication receipts in the same transaction as state changes. Duplicate event IDs and signed body hashes do not reapply, altered reuse is rejected, and callbacks outside the two-day past/five-minute future window are denied. Out-of-order events cannot undo newer state; equal timestamps cannot upgrade access. Terminal cancellation/expiry cannot reactivate automatically. This intentionally conservative policy requires an operator reconciliation workflow before a commercial release; missing/delayed callbacks can deny legitimate test access. Webhook headers are not independently trusted as tenant identity.

If test credentials are added later, use an explicitly approved development account and Razorpay test events, verify the actual endpoint delivery, and record provider evidence. Fixtures are not payment evidence. During secret rotation retain the previous webhook secret only for a bounded retry window, then remove it. There is no automatic rotation-expiry enforcement yet. No full subscription reconciliation, invoice accounting, tax handling, payment UI or commercial acceptance exists.

## 10 November lifecycle and hosted-job update

See [commercial lifecycle operations and evidence](COMMERCIAL_LIFECYCLE_2026_11_10.md) for the new test checkout/reconcile/cancel/invoice console, unresolved-operation recovery, expiring webhook rotation key, manual-only hosted migration job and opt-in payload-safe tracing. This supersedes earlier statements that these components have no local implementation. Default provider actions and telemetry export remain disabled. No production payment, managed resource, hosted migration or public release has been performed.
