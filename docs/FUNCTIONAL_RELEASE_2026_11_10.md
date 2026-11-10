# Functional development release — 10 November 2026

Status: implemented and running on the existing local Docker stack. **Commercial production acceptance remains pending.** No public deployment, customer charge, paid sandbox or production identity was created.

## User workflows now available

1. Open an organization → Settings → Workspaces. OWNER/ADMIN can create a workspace or rename it with an optimistic concurrency check. Its slug stays fixed. Knowledge, Teammates and Chat use the existing shared workspace selector. Organization membership permissions apply to all its workspaces; per-person workspace grants are not implied.
2. In Teammates, create a specialist and choose either Grounded onboarding plan or Python analysis proposal, then publish the saved revision. Published configurations remain immutable. Each existing owned acceptance organization also has two labeled starter teammates, added without overwriting other records or queuing tasks.
3. Add approved text in Knowledge. With an active organization worker, submit a task using a published version. The LangGraph workflow retrieves approved facts, produces a grounded plan and (for analysis) proposed Python, validates citations and pauses for human review. Generation never executes code.
4. Tasks & reviews now renders the summary, checklist, source quotes, missing information and draft reply. An approved artifact can be downloaded as a text file. Task review records no external delivery; the existing delivery receipt remains SIMULATED.
5. After task approval, proposed Python is prefilled in a separate code proposal form. Submitting creates a persisted request. A **different active OWNER/ADMIN** must approve the exact code hash and revision. Approval expires after one hour. A task approval alone does not authorize execution.
6. Run in isolated sandbox is enabled only when a fresh organization worker heartbeat advertises an explicitly authorized/configured E2B worker. The queue endpoint checks availability, entitlement, source/parent validity, current membership and reviewer access, then meters one accepted attempt. Repeated starts do not create a second attempt or consume again.
7. The worker rechecks approval/access/entitlements before remote creation, records audit events and any provider sandbox reference, and dispatches only through E2B. Changed code, revoked access or expired approval cannot execute. A lost or uncertain attempt becomes UNKNOWN and is never automatically replayed. Results are visible to the requester and organization administrators. Other members cannot read another requester's code; cross-tenant access is denied.
8. A stale/offline AI worker is now visible in Tasks and Chat. New AI input is disabled when the server explicitly reports unavailable processing; existing conversations and human support remain available. New organizations are not silently enrolled in paid processing.

Local URL: http://127.0.0.1:8080/app. Existing sign-in and records are preserved. Sandbox controls remain unavailable under the current configuration because no E2B account/resource approval exists. A second real administrator is required for an actual code review; fictional demo profiles cannot approve or log in.

## Checkpoint race fix

The earlier intermittent recovery failure was reproduced with a captured stack in `TenantSaver.put_writes`. The schema required pending writes to reference an already committed checkpoint. LangGraph supports committing pending writes before the checkpoint, as its [PostgreSQL reference implementation](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/base.py) documents. Migration 0010 replaces that ordering dependency with a composite organization/run foreign key. Forced RLS and task binding remain; no existing write/checkpoint rows are discarded. Migrations 0001–0009 were not edited.

A deterministic regression writes pending state before creating its checkpoint and verifies recovery afterward. Five repeated targeted database runs passed (seven checks per run, one live opt-in skipped). The complete database suite also passes. This resolves the identified ordering defect locally; it is not a claim that all production failure modes have been tested.

## Actual evidence

- 92 backend unit tests passed; lint, formatting, strict types and generated contracts passed.
- 93 isolated PostgreSQL tests passed; three live-provider opt-ins skipped in the normal suite. This covers migrations, forced RLS, independent code review, duplicate starts, quotas, tenant/role boundaries, altered-code denial, uncertain execution and workspace concurrency.
- 59 frontend tests passed, including both teammate workflows, proposal submission, independent approval, disabled sandbox execution, generated-code prefill, workspace creation and AI-offline/human-help behavior. Four CSP/build-policy checks, type checks and build passed. The existing >500 KB bundle warning remains.
- One explicitly enabled real OpenAI development analysis check passed in a disposable database. It produced a source-backed Python proposal and stopped at human review; it created no code execution request. This uses isolated test authentication, not a new live Clerk acceptance result.
- A separate scoped real RAG question cited the newly added product guide, passed exact-quote/source checks and did not report insufficient evidence. It wrote no conversation/message records. Two copies of the new guide are indexed READY in the existing owned acceptance workspaces.
- Seven deployed anonymous/browser smoke checks passed; the unconfigured-auth case was correctly skipped for the configured Clerk build. No new signed-in browser or two-real-user acceptance result is claimed.
- Migration 0010 is applied with 25 forced-RLS tables. The private pre-migration revision-0009 dump restored into a separate disposable database with all 23 previous RLS tables and recorded counts intact. All prior table counts were preserved across the forward migration.
- Existing data still includes one real user, two organizations, two real memberships and two workspaces. Additive development setup created four published starter definitions/versions, two new product-guide documents and two worker heartbeat rows. Re-running the starter script added zero duplicates. No development execution results or fake payment successes were seeded.
- All four local containers are healthy; health/readiness return 200 and anonymous identity access returns 401. Worker heartbeats advertise sandbox availability false.

Transport fixtures used for code execution are explicitly synthetic. No real E2B isolation, escape resistance, cleanup or resource-limit result is claimed. Pydantic emitted an existing alias warning during a concurrent test; this is retained as a dependency/compatibility observation.

## Remaining release work

Real Clerk invalidation (2C), two-human support/code acceptance, real E2B enforcement, Razorpay test delivery/reconciliation and complete commercial billing, approved pricing, hosted migrations/secrets/TLS, distributed tracing/alerts, load/quality/security measurements, managed backup/PITR and recovery objectives remain tracked in RELEASE_ACCEPTANCE.md. Outbound business connectors, a general multi-agent workflow editor, PDF ingestion and per-person workspace grants are not implemented by this release. These are not represented as working functionality merely because local tests pass.
