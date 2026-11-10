# Orqentra build status — 2026-11-10

Public free preview: **https://orqentra-demo.onrender.com** ([scope and live verification](FREE_PREVIEW.md)). Separate static build, fictional data, scripted/local answers, no account or backend/provider connection. It does not replace or accept the full application. This increment passes 105 backend unit tests, 63 frontend tests and two browser checks against the live URL; existing database data/volumes are unchanged.

Latest verified increment: [commercial billing lifecycle, hosted maintenance and tracing](COMMERCIAL_LIFECYCLE_2026_11_10.md). Revision **0011** is deployed locally: test checkout/reconciliation/cancellation/invoice UI and APIs, three new forced-RLS tables, a separate manual hosted-database job and opt-in payload-safe request tracing. **103 backend unit, 98 database, 61 frontend, 4 CSP and 7 anonymous browser checks passed** (expected live-model/configuration skips are documented). Health/readiness return 200; anonymous identity access returns 401; disabled billing callbacks return 503. All existing data is preserved. Commercial acceptance remains **PENDING**. The sections below retain earlier increment evidence; the linked report supersedes their billing/remote-job/request-tracing implementation gaps.

The application now includes a working development AI onboarding workflow, beyond the identity/organization foundation. It is not approved for production release.

| Capability | Implemented behavior |
| --- | --- |
| Identity and organizations | Existing Clerk development authentication, one local identity per subject, organization ownership, RBAC and forced PostgreSQL RLS |
| Organization navigation | Interactive tenant selector, scoped Command Center, Members, Settings and operational sections |
| Members | Role management, last-owner protection, expiring single-use private invitation links for MEMBER/VIEWER, revocation and authenticated acceptance |
| Teammate Forge | Create/edit bounded drafts, optimistic revisions, publish immutable versions, history and archive; OWNER/ADMIN publish; MEMBER can edit; VIEWER reads |
| Knowledge | Approved UTF-8 text, asynchronous chunking/real OpenAI embeddings, native pgvector cosine search, index state/retry and source revocation |
| RAG chat | Persistent private conversations, workspace vector retrieval, quote-checked citations, insufficient-evidence handling and revoked-answer redaction |
| Human support | Explicit private-chat sharing, OWNER/ADMIN inbox/claim, assigned human replies, AI pause/resume and audit events |
| Demo team | Twelve clearly labeled fictional profiles per acceptance organization, with no identity or permission grants |
| Tasks | Durable committed intake, tenant-scoped idempotency, worker claims with fencing/leases, bounded retry/backoff, cancellation, clarification, policy rechecks |
| OpenAI | Backend-only Responses API integration, strict structured output, `store: false`, exact source ID/quote validation, bounded response/call size, sanitized token usage |
| Review | Revision/hash/expiry-bound approval or rejection; recheck creator membership, agent/workspace and active sources |
| Outcome | One immutable SIMULATED receipt per approved run; no email/CRM/social delivery |
| Administration | OWNER/ADMIN rename with conflict checks, current resources/rolling recorded usage and paginated audit JSON export; partial usage is not an invoice |
| Operations | Tenant-allowlisted non-bypass worker with heartbeat, additive migrations 0004–0006, restricted grants, readiness, pre-migration backup and disposable restore rehearsal |

## Actual verification

- 84 backend/unit tests pass; database tests are run separately, not counted as passing when skipped by the plain unit command.
- 81 PostgreSQL regression tests pass in disposable databases, including new lifecycle, invitation, idempotency, cancellation, source-revocation, retry and claim-recovery tests.
- One explicitly opted-in real OpenAI HTTP → durable worker → review → simulated receipt test passes in a disposable database. Authentication in this test uses cryptographically signed test identities and pinned test public keys; it is not a new live Clerk browser test.
- The direct real OpenAI adapter validation produced three checklist items with valid source quotes, using 379 input and 317 output tokens. This is a smoke result, not an accuracy benchmark.
- 53 frontend tests, 4 CSP/build-policy tests, lint/types/build and contract drift checks pass. New editor/review interaction tests use labeled synthetic fixtures.
- Original development rows were preserved during forward migration; credentials and Docker volumes were not reset. The private pre-migration dump restored into a generated disposable database with the expected rows and all eight original tables under forced RLS; that temporary database was removed afterward.

## Remaining enterprise release work

2C genuine-provider session invalidation evidence remains pending. The user explicitly authorized subsequent feature development without falsely accepting 2C. Current knowledge ingestion is small text-only, with pgvector/real embeddings; PDF ingestion remains absent. The onboarding worker now has LangGraph/PostgreSQL checkpoints; arbitrary/custom tool execution remains unavailable. There is no workflow editor, outbound connector, checkout/invoice reconciliation, workspace-specific per-user grants, or multi-provider support. New organizations require explicit addition to the worker allowlist and restart. Recent lists are bounded; this is a small development/pilot implementation.

Per-call reservations are conservative capacity controls ($1 per attempted call, $10 per organization/UTC day), not measured OpenAI invoice amounts. Failed/uncertain attempts keep their reservation; actual input/output token usage is stored where available. A larger evaluation corpus, entailment/quality measurements, load/fault coverage, managed secrets/TLS/production Clerk setup, alerting and a reviewed deployment are still required before claiming enterprise production readiness. See [WORKFORCE_RELEASE.md](WORKFORCE_RELEASE.md).

The configured deployed browser suite passed 7 checks with one unconfigured-only skip. Four static component presentation checks passed separately using explicitly synthetic data. Web/API/worker/PostgreSQL were healthy, readiness returned 200, and the served JavaScript matched the tested build after the final sidebar polish. The installed worker source also matched the tested source. Exact deployment verification is recorded in the release report.

See [Vector RAG and chat](RAG_AND_CHAT.md) for the 2026-11-05 implementation, demo data, current limits and new validation results. The report records current deployment and vector/chat evidence, including the separate opt-in checks and expected skips.

See [Human handoff](HUMAN_HANDOFF.md) for the November 9 implementation, sharing policy, actual test evidence and staffing limits.

Product assistant knowledge and six real retrieval/model smoke checks: [PRODUCT_ASSISTANT.md](PRODUCT_ASSISTANT.md).

Organization-first sidebar flow is documented in [NAVIGATION_FLOW.md](NAVIGATION_FLOW.md).

Commercial development follows [COMMERCIAL_ROADMAP.md](COMMERCIAL_ROADMAP.md); the C1 operations baseline and explicit non-production limitations are in [COMMERCIAL_OPERATIONS.md](COMMERCIAL_OPERATIONS.md). Render templates are unapplied. C2 billing quotas/ledger and a disabled Razorpay test callback adapter are implemented locally; real provider acceptance remains outstanding. The onboarding LangGraph integration and disabled E2B adapter are documented in [ORCHESTRATION_AND_SANDBOX.md](ORCHESTRATION_AND_SANDBOX.md); their production acceptance remains pending.

Latest functional release: [10 November workflows and evidence](FUNCTIONAL_RELEASE_2026_11_10.md). Revision 0010 adds code-specific independent review/dispatch, workspace management and a fix for checkpoint write ordering. Hosted/provider/security acceptance is still pending.

Provider/recruiter publication update: the backend now enforces sandbox concurrency per organization across worker replicas (default one; maximum configurable two). The default mocked/disposable suite passed **103 unit and 99 database checks**, with three real-model database opt-ins skipped. The source is public with `main`/`develop` and owner-only write access; see [repository verification](REPOSITORY_ACCESS.md) and [real-provider acceptance checklist](PROVIDER_ACCEPTANCE.md). No provider resource test or public application deployment was performed.
