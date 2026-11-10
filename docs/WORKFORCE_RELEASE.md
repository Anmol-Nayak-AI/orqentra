# Workforce development release

## Use the implemented application

Open http://127.0.0.1:8080/app, sign in, and select an organization. Its sidebar now exposes Teammates, Knowledge, Tasks & reviews, Members and Audit trail. Organization settings remain read-only.

1. In Knowledge, select the workspace and save an approved UTF-8 text source. Content is limited to 24,000 characters, with at most 20 active sources per workspace. This is lexical retrieval over bounded source excerpts, not a vector database or PDF ingestion claim.
2. In Teammates, create a specialist in that workspace, save its instructions/model/budget, and publish the saved revision. Publication preserves an immutable snapshot; it does not itself call a model.
3. In Tasks & reviews, select the teammate and a published version, enter a concrete customer request, and queue it. Intake commits before HTTP 202. A key reused with identical input returns the same run; changed input conflicts.
4. The worker selects active workspace sources and requests schema-constrained output from OpenAI. Every checklist item's evidence must identify a supplied document and quote text actually present in that supplied excerpt. This validates references and quotes, not semantic entailment. Missing information stops in NEEDS_CLARIFICATION; additional facts can requeue the same run within its remaining budget/attempt bound.
5. OWNER/ADMIN can approve or reject the exact saved artifact revision before its seven-day expiry. Revoked sources or changed authorization block approval. Approval creates one clearly labeled SIMULATED receipt; no external message is sent.
6. Members supports private invitation links. Invitees sign in first, then open `/app/join#...` and explicitly accept. Links are bearer capabilities, expire after 48 hours, grant only MEMBER/VIEWER, and are stored hashed. Treat them as private. They are not email-bound invitations or automatic email delivery. Their token is removed from the address bar after the component mounts.

## Local operator setup

The ignored `.env.ai` contains `OPENAI_API_KEY` for backend/worker only. Never use `VITE_` for provider keys. The existing `.env.runtime` supplies restricted database credentials. The ignored `.env.worker` contains a comma-separated `ORQENTRA_WORKER_ORGANIZATIONS` allowlist; the local existing acceptance tenants were configured. Add each newly authorized tenant deliberately and recreate the worker. It never discovers tenants through a bypass role.

Start or rebuild the complete local stack:

```sh
make ai-up
```

The Compose `ai` profile runs a separate worker with a read-only filesystem, dropped capabilities, tmpfs heartbeat and the same non-superuser/non-bypass runtime role. It uses transaction-local tenant context and checks membership before work and before accepting output. A claim expires after two minutes; a replacement gets a new fencing token. Old worker results cannot overwrite a cancelled/reclaimed run. A worker outage leaves committed tasks queued.

Retries are bounded by three claims, configured call count and the run's total reservation budget. Retryable provider errors back off by ten seconds times the attempt number. A conservative $1 reservation is retained for every possible model call, including uncertain failures, and the serialized tenant cap is $10 in UTC-day reservations. These are capacity ceilings, not invoice calculations. Default draft capacity is $3; operator pricing review is required before treating this as a financial guarantee.

## Verification commands

```sh
make check
make test-db
E2E_BASE_URL=http://127.0.0.1:8080 E2E_EXPECT_CONFIGURED=1 npm run test:e2e --workspace @orqentra/web -- foundation.spec.ts
make migration-check
```

The real-model test is explicitly opt-in (`ORQENTRA_LIVE_MODEL_TEST=1` and backend-only `OPENAI_API_KEY`), creates its own disposable PostgreSQL database, and must never run automatically as a free fixture or silently spend model credits in CI. The normal database suite skips this one test. No testing helper is registered as an HTTP authentication bypass.

For restore rehearsal, select an existing private dump:

```sh
uv run --locked --package orqentra-api python scripts/verify_local_restore.py .local/backups/SELECTED.dump
```

The script creates and removes only its generated `orqentra_restore_<uuid>` database; it never restores over the application database. Pre-migration rehearsal verified the original 0003 backup, eight forced-RLS tables and preserved counts. This is not a measured managed-PITR RPO/RTO commitment.

## Release decision

**Development workflow implemented; enterprise production release NOT ACCEPTED.** The live adapter and isolated real-model backend journey passed. A signed-in real-browser journey through the new modules has not been observed. The existing 2C provider-invalidation interval remains unverified. Follow BUILD_STATUS.md for other functional/operational gaps, including PDF/vector ingestion, fine-grained workspace grants, load/quality evaluations and external connectors. No production credentials or external deployment were used, and no compliance or availability certification is claimed.

The video reference is [Code With Antonio — How I Build AI Teammates With Claude Code — Grok Bot Clone](https://www.youtube.com/watch?v=mQBuZ6Dp0u0). Its public title/channel metadata was verified; the complete video/transcript was unavailable. Orqentra's implementation follows its own existing B2B onboarding requirements, inspired by configurable AI teammates; exact video feature parity is not asserted.

## Final deployment verification

The configured deployment passed seven browser smoke checks with one unconfigured-only skip; that skip is expected for a configured Clerk deployment. Four synthetic static component layout checks passed separately, including mobile navigation; they are not live identity evidence. Final frontend count is 37 passing tests; CSP count is three. The backend suite has 63 passing unit/API tests; the separate database suite has 73 passes plus its intentionally opt-in live-model skip. The live-model journey was then run explicitly and passed once. The first underspecified live fixture correctly entered NEEDS_CLARIFICATION; the complete-source fixture subsequently passed review and receipt creation without bypassing that state gate.

After final sidebar and worker audit/retry corrections, the web, API, worker and PostgreSQL services are healthy. Readiness returned HTTP 200. The served JavaScript and installed worker source match the locally tested source/build by SHA-256. The development database is at revision 0005 with twelve forced-RLS domain tables; its original one user, two organizations, two memberships and two workspaces remain present. All live model fixtures ran in disposable test databases, so no synthetic tenants/users were added to the application database.


## Vector RAG/chat deployment — 2026-11-06

The earlier text-retrieval limitation is superseded by native pgvector storage, real OpenAI embeddings and workspace-scoped cosine retrieval shared by task generation and private chat. Migration 0006 preserves the existing PostgreSQL volume and prior rows. Both seeded fictional handbook indexes are READY; both demo replies completed through the deployed real-model worker with validated citations. The separate fictional roster grants no permissions. See [RAG_AND_CHAT.md](RAG_AND_CHAT.md) for exact counts, tests, retry history and remaining limits. This development deployment does not pass 2C or authorize production release.
