# Decisions and unresolved questions

Status: Phase 1 design record, 2026-10-28. “Selected” means the proposed design baseline follows the user brief; it is not evidence of implementation or organizational sign-off. Role owners below must be assigned before their gates. Unresolved choices do not prevent design completion.

## Selected architectural baseline

| ID | Decision | Rationale and consequence |
|---|---|---|
| ADR-01 | Modular monolith, Python FastAPI API and worker process roles, PostgreSQL source of truth | Shared domain policy and transactional consistency first; no Node/Express/Next backend. Scale process roles before splitting services. |
| ADR-02 | React/TypeScript/Vite, Tailwind and shadcn/ui; read-only React Flow graph | Meets required frontend stack while keeping arbitrary visual workflow execution outside MVP. |
| ADR-03 | Fixed bounded LangGraph workflow and explicit schema-versioned state; official Postgres checkpoints with scoped adapter | Recovery/interrupts are required; framework persistence alone does not establish tenant isolation or business-effect idempotency. |
| ADR-04 | Application scope checks plus composite foreign keys plus PostgreSQL FORCE RLS | Defense against route/query mistakes; shared runtime compromise remains residual risk. |
| ADR-05 | Immutable agent/workflow/artifact revisions and exact bundle-bound approval | Reproducibility and review integrity; edits trigger new approval. Runtime revocation overrides old permissions. |
| ADR-06 | Transactional outbox, Redis Streams as at-least-once hints, DB recovery scanner | Redis outages cannot erase accepted work; duplicate queue messages are expected. |
| ADR-07 | Durable node-operation ledger distinct from checkpoint and BusinessAction ledger | Domain/checkpoint commits are not assumed atomic; replay reuses recorded results; arbitrary remote exactly-once effects are not promised. |
| ADR-08 | Development/demo includes only simulated delivery; model/provider inference is separately controlled | No real external messages. A future live connector requires provider-specific idempotency/reconciliation and separate gates. |
| ADR-09 | pgvector in same DB, exact tenant-filtered search first | Small pilot corpus does not justify another database or unmeasured approximate retrieval. Embedding profile/dimensions are versioned. |
| ADR-10 | External secret manager handles only in domain records; no provider credentials in prompts/checkpoints/logs | Reduces secret propagation; broker controls retrieval at runtime. |
| ADR-11 | OIDC with server-side opaque sessions and CSRF; explicit workspace grants | Consistent browser authorization/revocation without browser storage of provider tokens. |
| ADR-12 | Integer-cost reservations across organization/workspace/run, bounded persisted attempts/deadlines | Controls concurrent spend and runaway retries; invoice-level limits depend on provider enforcement. |

## Unresolved decisions and gates

| ID | Decision to resolve / options | Provisional assumption | Accountable role | Must resolve by / evidence |
|---|---|---|---|---|
| D-01 | Identity provider, invitation lifecycle and initial organization bootstrap | OIDC; fixture provider only locally; authenticated transactional bootstrap | Identity/backend lead | 2A: provider discovery/claims/session/logout tests; no production dev-auth bypass |
| D-02 | Official saver schema isolation, serializer, connection scoping and stale-worker checkpoint fencing | Restricted schema, binding-based RLS, scoped wrapper and dedicated thread lock; do not assume framework support | Orchestration + security leads | 2A blocker: AC-02/03 spike with exact package; choose reviewed adapter or stronger role/schema isolation if needed |
| D-03 | LLM/embedding provider/model, region, retention/training terms, context dimensions and pricing | Deterministic fixtures first; no sensitive customer data sent to unapproved provider | AI/product/security leads | Before real inference: approved data terms, model schema capability, price snapshot, evidence benchmark and budget tests |
| D-04 | Reviewer separation and admin access to workspace customer content | Requester cannot self-approve; admin alone cannot approve; explicit grants for data access | Product + security leads | 2A/2B policy tests; document any organization-specific exception and accountability |
| D-05 | Supported interpreter/build runtime, dependency compatibility, exact image/extension/CLI pins and licenses | Registry versions in implementation plan are observations only; PostgreSQL 18 candidate; Node build-only | Platform lead | 2A: compatibility/install tests, vendor support/advisory/license review, lockfiles/hashes/digests and SBOM |
| D-06 | Pilot corpus, mandatory intake fields, evidence rubric, data classification and acceptable quality | Synthetic corpus; customer reference, contact, product context, desired outcome required; missing facts block delivery | Product/implementation lead | Stage 3: labeled cases, customer vocabulary and reviewer agreement; scope-sensitive fields approved |
| D-07 | Production communication provider, channel, credentials, safe recipient policy and replay support | No live connector; simulated receipt only | Integrations + security leads | Stage 5 only: AC-16 plus explicit production configuration/enablement; provider idempotency/receipt lookup required |
| D-08 | Contractual retention, deletion/hold policy and idempotency tombstone horizon | Proposed 90-day operational/365-day audit; 35-day backup expiry; expired request keys return 410 while tombstone retained | Product/data/legal + platform leads | Before customer data/pilot contract: precise replay horizon and tombstone duration; demonstrate purge/restore; never imply infinite duplicate detection after tombstone deletion |
| D-09 | Hosting region, S3-compatible service, secrets/KMS, Redis distribution, backup and immutable audit export | Local Compose only initially; managed/private infrastructure later | Platform/security leads | Before hosted pilot: resource sizing, licenses, data residency, recovery and access plan |
| D-10 | Pilot quotas, pricing/cost policy, commercial packaging, business metric baseline | USD 1/run and USD 25/org/day provisional; 10 org/50 user/20 active run sizing | Product/finance + AI leads | Before paid pilot: validated model prices, cap behavior, measured workload, manual baseline; billing excluded from MVP |
| D-11 | Pilot reliability targets and operational ownership/on-call | 99.5% monthly objective; RPO 15 min, RTO 4 h; recovery 120 s | Platform + product leads | Stage 4: load/restore drills and SLO definitions; no contractual SLA before review |
| D-12 | Commercial brand/domain/trademark availability | Orqentra and CrewForge remain internal labels | Product/business owner | Before external commercial branding; qualified clearance process outside engineering scope |
| D-13 | Evidence revocation, reviewer correction workflow and sensitive signed downloads | Immediate source revoke; new artifact revision/new approval; short URL TTL or authenticated proxy for high sensitivity | Product/security/knowledge leads | Stage 3: AC-06/14 and clear unavailable-source UI; define correction/consent expectations |
| D-14 | Long-lived graph version support and checkpoint migration lifecycle | Keep old executors until runs terminal/expired; no silent state upgrade | Orchestration/platform leads | Before first incompatible release: old-version resume and migration/rollback drill |
| D-15 | Evaluation scorer/tooling and target thresholds for semantic evidence and unsupported claims | Human-labeled corpus and deterministic safety gates; no LLM-only self-grading | AI/product leads | Stage 3: versioned rubric, measured agreement, sample sizes and failure analysis; set pilot go/no-go threshold |

## Prioritized architecture review

1. **Checkpoint isolation and fencing are the main feasibility gate.** Scope must cover framework blobs/writes/list/delete and stale-worker writes. If the selected package cannot preserve this through a reviewed adapter, change the persistence integration before building around it.
2. **Do not conflate one ledger record with exactly-once external delivery.** The first slice can guarantee one local simulation receipt transactionally. A future remote send needs stable provider keys, receipt lookup and an unknown-outcome state.
3. **Approval must survive content and policy races.** Bundle hashes, source checks, expiring eligible reviewers, locking and CAS are required at dispatch, not just at the API/UI decision.
4. **Model quality and privacy remain independent gates.** Valid JSON/citation IDs do not establish factual support. Provider terms, labeled evaluation and human evidence review are required before customer use.
5. **Operational targets need measurement.** Load, restore, migration, telemetry and retention drills turn a plausible architecture into release evidence; the documents alone do not do so.

## Next implementation vertical slice

Seed one secure workspace, a published teammate/workflow and one synthetic knowledge document. Accept authenticated idempotent intake, run a bounded fixture-backed graph with Postgres checkpoints, persist a sourced plan/draft, pause for a distinct eligible reviewer, and record one simulated delivery with audit and usage. Include crash/replay, tenant attacks, stale approvals and no-outbound verification in the same slice. Build no live delivery path until D-07 and AC-16 are satisfied.

## Change policy

Record a new ADR when changing isolation, approval semantics, delivery guarantees, budget behavior, graph-state compatibility or data retention. Include rationale, rejected alternatives that affect tradeoffs, affected threats/criteria, migration and rollback evidence. Close unresolved decisions with actual selection, owner, date and evidence; do not overwrite the historical rationale or label an unexecuted test passed.
