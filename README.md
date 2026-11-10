# Orqentra

**Your workforce, intelligently orchestrated.**

Orqentra is a multi-tenant AI workforce application built with React, FastAPI, PostgreSQL/pgvector and LangGraph. It combines source-grounded AI assistance, human support handoff, reviewed task artifacts and independently approved isolated code execution.

**Status: active development, not production-accepted.** The application runs locally; Render templates are unapplied, billing supports test mode only, and E2B execution remains disabled until separately authorized. A configured key does not authorize provider resource usage.

## For reviewers and recruiters

- **Identity and tenancy:** Clerk JWT verification, exactly-once local provisioning, organization RBAC, restricted database roles and forced PostgreSQL RLS.
- **Vector RAG:** approved workspace knowledge, asynchronous OpenAI embeddings, pgvector retrieval, persistent conversations and validated source quotations.
- **Human oversight:** explicit conversation sharing, support assignment/replies, AI pause/resume and revision/hash/expiry-bound task approvals.
- **Durable execution:** tenant-scoped LangGraph checkpoints, bounded retries, lease fencing, cancellation and conservative handling of uncertain outcomes.
- **Isolated code boundary:** independent code review, durable queue, E2B adapter, timeout/network/output restrictions and database-enforced per-organization concurrency. Customer code never runs in API or worker containers.
- **Commercial foundation:** atomic quotas and usage events, test subscription lifecycle/reconciliation, signed idempotent webhooks, append-only invoice history and audit export.
- **Operations:** non-root read-only containers, development/staging/production guards, private pre-migration backups, separate hosted maintenance job, opt-in payload-safe tracing and CI.

Start with [build status](docs/BUILD_STATUS.md), [commercial implementation evidence](docs/COMMERCIAL_LIFECYCLE_2026_11_10.md), [provider acceptance checklist](docs/PROVIDER_ACCEPTANCE.md), and [release acceptance](docs/RELEASE_ACCEPTANCE.md). Reports distinguish real provider observations, synthetic tests and unverified gates. Historical checkpoint reports describe their original increments.

## Architecture

```text
Browser → React / nginx → FastAPI → PostgreSQL + pgvector
                            │           │
                            │     durable jobs/checkpoints
                            │           │
                     Clerk verification └→ bounded LangGraph worker → OpenAI
                                                    │
                                       independent approval → E2B (disabled)

Razorpay TEST webhook → signature / replay checks → subscription + immutable ledgers
```

`apps/api` contains the modular backend and migrations; `apps/web` the React application; `packages/contracts` generated OpenAPI/TypeScript contracts; `infrastructure` Compose, nginx and unapplied Render templates; `scripts` provisioning, verification and maintenance tools.

## Local setup

Requirements: Python 3.12.15 / uv 0.12.23, Node 22.22.2, npm, Docker with Compose, Git and Make. Exact dependency locks and image digests are included.

```sh
make setup
make install
make db-up
make migrate
make runtime-setup
make up
```

Open http://127.0.0.1:8080. `make setup` creates ignored local PostgreSQL credentials and preserves existing files. Migrations use a separate local owner; API/worker containers receive the restricted runtime credentials. There are no automatic startup migrations or destructive resets. `make down` preserves the named database volume.

For authentication, configure `VITE_CLERK_PUBLISHABLE_KEY` in ignored `.env` and the Clerk issuer, allowed origins and **public** signing key in ignored `.env.auth`, following `.env.auth.example`. Rebuild the web image after changing its publishable key. Never put backend secrets in `VITE_*` variables.

AI setup uses backend-only `.env.ai` and an explicit organization allowlist in `.env.worker`; consult the corresponding examples and [workflow runbook](docs/ORCHESTRATION_AND_SANDBOX.md), then use `make ai-up`. An OpenAI call may consume paid API credit; it is not required for the default automated tests. Demo profiles are labeled fictional and do not grant login access.

Billing, sandbox and tracing templates are `.env.billing.example`, `.env.sandbox.example` and `.env.telemetry.example`. Keep configured copies ignored and mode 0600. Leave provider actions disabled until separately authorized. No real credentials are included in this repository.

## Validation

```sh
make check                 # lint, types, unit/UI/CSP checks, build and contracts
make test-db               # real PostgreSQL isolation/lifecycle tests in disposable databases
npm exec --workspace @orqentra/web -- playwright install chromium
make e2e                   # anonymous browser regression checks
```

The default suites use synthetic identities and mocked AI/payment/sandbox transports. Real-model tests require explicit opt-in and are reported separately; they are not silently included as free checks. To test running local containers:

```sh
E2E_BASE_URL=http://127.0.0.1:8080 E2E_EXPECT_CONFIGURED=1 make e2e
```

`GET /api/v1/health` checks process liveness. `GET /api/v1/ready` checks local database/auth configuration, not external provider availability. See [migration operations](docs/MIGRATION_GUIDE.md) before changing schema or roles.

## Repository access

`main` is the reviewed baseline; `develop` is the integration branch. Public readers receive no write permission. Changes to the upstream repository require the owner's authorization; anyone can still clone/fork public code and modify their own copy. See [publication and access controls](docs/REPOSITORY_ACCESS.md) and [security policy](SECURITY.md). No reusable open-source license has been selected.

## Release boundaries

Real Razorpay test callbacks, reviewed E2B resource/network acceptance, hosted deployment/restore, production identity setup, genuine-session acceptance, broader reliability/load/security assessment and remaining business connectors are still release gates. Public source availability is not authorization to deploy, charge customers or claim commercial production readiness.
