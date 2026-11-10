# Commercial SaaS implementation roadmap — 2026-11-09

Latest implementation: [10 November commercial lifecycle report](COMMERCIAL_LIFECYCLE_2026_11_10.md). It supersedes historical descriptions below that say checkout, reconciliation, invoice history, a separate hosted maintenance job or API request tracing are absent. These now have local implementations and tests; real-provider/hosted acceptance, full queue tracing and business integrations remain pending.

Status: **implementation in progress; NOT production accepted**. This is the current roadmap, superseding sequencing descriptions in historical checkpoint/enterprise documents where they conflict with the user's November 4 and November 9 instructions. 2C remains pending; development is authorized without accepting it. No public deployment, live payments, paid resources or local untrusted execution is authorized.

## Repository audit

Reviewed the monorepo layout, dependency manifests/locks, API modules and persistence/session boundaries, web routing/components/query boundaries, migrations 0001–0007, CI/container/network configuration, database scripts, phase-1 architecture/security requirements, 2A/2B/2C checkpoint records, BUILD_STATUS, WORKFORCE_RELEASE, RAG/product-knowledge and human-handoff evidence. This is a component-level implementation audit, not an independent security assessment. The repository is initially untracked/uncommitted; no history was reset and no commit was made.

| Area | Existing implementation | Gaps / evidence boundary |
| --- | --- | --- |
| Identity | Clerk development auth, claim verification, unique provisioning, RBAC, session cache barriers | Production instance, signing-key rotation and genuine provider invalidation acceptance pending |
| Data | PostgreSQL/pgvector, 21 forced-RLS domain tables after additive migration 0008, tenant foreign keys, restricted runtime, additive migrations/backups | Managed encrypted backup/PITR, restore objectives, future tables require equivalent RLS |
| AI | OpenAI adapter, bounded durable worker, task leases/fences/retries, source-checked RAG, approval-bound simulated receipts | No LangGraph dependency/checkpoints yet; no actual business connector actions |
| Human oversight | Explicit conversation sharing, exclusive support claim/replies, AI pause/resume | Two-real-user acceptance and availability/notification operations pending |
| Commercial foundation | Admin rename/usage/audit export and production guards under test in the current working tree | Recorded usage is partial, not an invoice; C2 quota/subscription/immutable meter implemented locally; complete invoice reconciliation absent |
| Sandbox | No execution service or sandbox adapter | No E2B SDK/account; no shell execution fallback is allowed |
| Operations | Non-root images, loopback Compose, liveness/readiness, structured request logs, locked dependencies and CI | Unapplied Render manifests and trace correlation added; hosted validation, full traces, protected deploy workflow and release measurements pending |

Current local baseline results: 84 backend unit tests, 81 disposable-database checks (2 live-model opt-ins skipped), 53 frontend and 4 CSP/build-policy checks for the admin/deployment increment. These are not proof of production readiness. Results will be updated for each completed slice.

## Dependency-aware delivery

| Phase | Depends on | Independently testable deliverables | Gate |
| --- | --- | --- | --- |
| C0 inventory and decisions | Existing repository | This audit; provider choices and feature boundaries | Preserve existing behavior and records |
| C1 deployment/security baseline | C0 | Development/staging/production config, Render/container manifests, production guards, explicit unavailable integration states, preflight, structured timing/trace correlation, operator rollback runbook | Local tests and configuration validation; no account/resource creation |
| C2 commercial data plane | C1 | Additive RLS migrations for plans/subscriptions, append-only usage events, idempotent entitlement/quota reservations, organization billing status | Concurrency, tenant isolation, double-consumption and rollback tests |
| C3 Razorpay test adapter | C2 | Provider-independent billing interface; bounded test-mode API adapter; raw-body signature verification, event dedupe, replay/order handling and reconciliation | Disabled without test credentials; real test checkout/webhook verification required before acceptance; never enable live charges |
| C4 isolated tool execution | C1 + C2 | E2B adapter, tenant/run/approval binding, tool allowlists, bounded input/output/runtime, deny-by-default network, no host credentials or Docker socket | Execution unavailable by default; real isolated test plus escape/network/timeout tests required; no local code fallback |
| C5 persistent orchestration | C2 + C4 | LangGraph PostgreSQL checkpoints with tenant namespaces/RLS, explicit approvals, bounded retries/steps, idempotent side effects and recovery integrated with the existing worker | Preserve existing job/approval fences; crash/replay/cancellation/cross-tenant tests; no vendor setup that bypasses RLS |
| C6 business integrations | C3 + C5 | Approved connector scopes and outbound action idempotency, revocation, human approval; enable chosen workflows behind flags | Real development integrations and authorization evidence; no silent sends |
| C7 reliability and release | C1–C6 | Measured evaluation corpus, load/fault tests, traces, dependency/image checks, backup restore/recovery, staging security review, two-human support and live auth acceptance | All mandatory evidence recorded; explicit authorization still required for public deployment, paid resources and real payments |

RAG/human support, onboarding/review and general teammate workflows remain in scope. They reuse identity, tenancy, billing entitlements and orchestration rather than becoming separate apps. Subscription prices, customer SLAs and compliance claims are deliberately unset until agreed and supported by evidence.

## Fixed provider boundaries

- Render first; portable Docker images and environment contracts, with no Render calls/resources created by local development.
- Razorpay first, Stripe later via a provider interface. All money-moving paths disabled; only test mode can be implemented/enabled under the current authorization.
- E2B for untrusted execution. Never run customer code in FastAPI, the worker, a subprocess on the laptop or a host-mounted Docker socket. Fail unavailable when credentials or policy enforcement are missing.
- LangGraph orchestrates bounded workflows; it does not replace Clerk, application membership authorization or PostgreSQL RLS. Checkpoint ownership is server-derived, not accepted from a client thread ID.

## Provider documentation

Implementation uses official [Render Blueprint](https://render.com/docs/blueprint-spec), [Razorpay webhook validation](https://razorpay.com/docs/webhooks/validate-test/), [E2B documentation](https://e2b.dev/docs), and [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence). Video-inspired feature direction is not proof that a tutorial architecture or third-party transcript is production safe. Instructions in external material to discard data or bypass migrations do not apply here.


## C0/C1 local verification update

C0 audit/roadmap and the initial C1 baseline are implemented. Both Render manifests pass offline YAML/policy validation, the shell entrypoint passes syntax/invalid-input checks and the local development stack is healthy after sequential rebuild. Readiness returns 200 with a bounded trace header; served JavaScript matches the tested build. Existing counts remain one real user, two organizations, two real memberships and two workspaces; revision 0007 and existing migrations/volumes are unchanged. The two added administration guides indexed READY. No commercial provider account was contacted or configured.

The administration console is available to OWNER/ADMIN in Organization Settings: conflict-checked rename, scoped current resources/rolling usage, bounded JSON audit export and explicit unavailable payment/sandbox status. It does not expose private chat text in usage summaries and does not calculate invoices. These behaviors are verified by isolated authenticated tests; a new real signed-in browser administration journey has not been observed.

C2 is now implemented locally. C3 has a disabled-by-default test adapter and signed callback processing; it is not provider-accepted. C4 E2B and C5 LangGraph are not implemented. Missing accounts do not prevent their local implementation, but real-provider acceptance cannot be fabricated. All ten requested areas remain tracked across C1–C7; this increment does not complete the commercial product.


## C2/C3 implementation and evidence

Migration 0008 adds four forced-RLS tables without modifying old migrations or records. A private pre-migration backup was restored into a disposable database at revision 0007 with all 17 original RLS tables and recorded counts intact; the existing database advanced forward only. The baseline retained one real user, two organizations/memberships/workspaces, 24 demo profiles, 24 knowledge documents/chunks, three conversations and four exchanges. The four commercial tables initially contain zero rows; no fake active subscription or payment success was seeded.

The isolated suite verifies atomic last-allowance competition (one accepted, one quota rejection), retry deduplication, tenant scope, cancelled/expired denial and append-only usage protection. Synthetic signed callback checks cover disabled operation, invalid signatures, replay/body deduplication, conflicting reuse, wrong tenant/plan, malformed/stale input and conservative event ordering/terminal states. A mocked read-only provider lookup confirms that only an authorized owner can link and that remote ACTIVE does not grant access from linking: local state begins PENDING. These fixtures do not prove a real payment or hosted delivery. An initial test expected 404 for an unknown tenant; observed 403 at the earlier tenant boundary was correct, and the assertion was corrected.

C3 limitations: no real Razorpay account/event delivery, checkout or subscription creation, reconciliation job, invoice/tax lifecycle or billing-provider acceptance. Paid production entitlements stay disabled. See the operations runbook for callback freshness and conservative denial rules.

Final local verification for this increment: **86 backend unit tests, 86 disposable-PostgreSQL tests, 53 frontend tests, four CSP/build-policy tests and seven anonymous browser checks passed**. Two real-OpenAI database opt-ins were skipped to avoid repeating completed paid-provider verification; the browser's one unconfigured-auth case was correctly skipped because this build has Clerk configured. It does not block the anonymous browser suite or resolve the separate 2C real-session gate. Contracts, lint/type checks, offline deployment-manifest checks and migration drift checks passed. All four local containers are healthy; health/readiness return 200, anonymous `/me` returns 401 and disabled webhook POST returns 503. Read-only inspection confirms revision 0008, 21 forced-RLS tables, preserved identity/organization counts and zero subscription/usage/webhook rows in development. The later membership recheck passed its targeted database regression. No live billing API or sandbox call was made.

Known warnings/limitations remain: a Pydantic alias warning appeared in an earlier concurrent identity run, the frontend build reports a >500 kB bundle, and production dependency/image/security acceptance is not established. Backup restore evidence is local, not managed PITR or measured recovery objectives. Full tracing, secret rotation enforcement, remote deployment/migration validation, E2B isolation and persistent LangGraph recovery are release blockers. **Final commercial acceptance: PENDING; not production-ready.**


## C4/C5 continuation — 2026-11-09

The onboarding worker now uses a bounded persistent LangGraph with tenant-scoped PostgreSQL checkpoints (additive migration 0009), claim/lease fences, synchronous writes and existing human-review authorization. An E2B adapter and disabled default provider are implemented but not exposed as a code tool. Code-specific approval integration and real E2B enforcement acceptance remain open; onboarding approval cannot authorize arbitrary code. See [ORCHESTRATION_AND_SANDBOX.md](ORCHESTRATION_AND_SANDBOX.md) for exact boundaries, fault-injection evidence and the provider-call-before-checkpoint crash window.

This supersedes the earlier “not implemented” descriptions for these two components only. It does not accept 2C, C4/C5 production behavior, external delivery, full billing, observability or the commercial release. No cloud resources or live payments were activated.

C4/C5 local validation update: 92 backend unit tests and 87 disposable-database checks passed; two live-model opt-ins skipped. Revision 0009 is applied locally after a private backup and a verified disposable restore of revision 0008. Existing row counts and volumes are preserved, runtime RLS covers 23 tables, and the four local services are healthy with readiness 200. One earlier intermittent expired-claim test failure remains an unresolved production regression item despite passing focused/final reruns. Six sandbox fixture checks passed without creating any resource. Local runtime dependency audits reported no known findings; the added Linux CI dependency-audit job has not run remotely. Frontend/CSP checks were not needlessly repeated because those sources did not change. See [RELEASE_ACCEPTANCE.md](RELEASE_ACCEPTANCE.md) for every remaining external/security/reliability gate. **Commercial acceptance remains PENDING.**

Post-rebuild smoke: seven anonymous/browser checks passed, with the unconfigured-auth case correctly skipped for the configured Clerk build. Health/readiness returned 200 and anonymous identity access returned 401. These checks do not establish a genuine signed-in provider-invalidation test. No frontend component sources changed in this increment.


## Functional continuation — 2026-11-10

[Functional release report](FUNCTIONAL_RELEASE_2026_11_10.md): Python analysis proposals, readable/downloadable approved artifacts, independently reviewed code execution with a durable queue/unknown-outcome handling, worker availability, workspace administration and starter specialists are implemented locally. Migration 0010 also resolves the reproduced pending-write/checkpoint ordering defect while preserving tenant/run binding. These supersede earlier descriptions of the E2B adapter as unexposed and that defect as unexplained. E2B resource creation remains disabled and real provider/deployment acceptance remains open. All existing migrations and data were preserved; no public deployment or customer payment occurred.
