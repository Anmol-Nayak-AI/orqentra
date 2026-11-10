# Orqentra end-to-end delivery scope

## Objective and current boundary

Build a general AI teammate platform, with customer onboarding as the first complete workflow. The product must support a real authenticated journey from teammate configuration through grounded output, human approval and an auditable result. A screen, fixture or unexecuted design is not a completed capability.

The user explicitly authorized feature development on 2026-11-04 while keeping 2C pending. This supersedes the earlier sequencing block. Current implemented capabilities and limitations are recorded in BUILD_STATUS.md and WORKFORCE_RELEASE.md; the slice table below remains the full delivery target, not a claim that every release criterion has passed. Existing data, credentials, Docker volumes and migrations are preserved.

## Verified starting point

Existing code provides Clerk identity, local users, organization membership/RBAC/RLS, workspaces, versioned agent persistence/repositories, sanitized audits, generated contracts, local deployment and UI. The backend-only development OpenAI key is now configured in ignored .env.ai. The adapter and isolated real-model durable workflow have been exercised without printing credentials. No connected browser is available for the outstanding genuine-session invalidation check.

The existing agent repository already supports create, list, get, compare-and-swap draft updates and immutable publication. At the start, archive, strict model/tool/schema validation and the HTTP lifecycle were missing; they are now implemented and tested as recorded in BUILD_STATUS.md. Reuse this persistence rather than creating a competing agent table or bypassing its constraints.

## Delivery order and concrete acceptance

| Slice | Working user capability | Completion evidence |
| --- | --- | --- |
| 1. Teammate Forge | Select workspace; create/edit a bounded teammate configuration; publish immutable versions; archive and browse history | Restricted-role HTTP tests for every role, invalid tools/models, stale edits, concurrent publish, tenant/workspace denial; generated contracts and functional UI |
| 2. Knowledge | Upload approved text/text-based PDF; view ingestion state; retrieve sources in the selected workspace | Size/parser limits, quarantine, tenant isolation, source revocation, reproducible retrieval cases and evidence links |
| 3. Durable task execution | Submit idempotent intake against a published teammate; persist run and step states; cancel/recover safely | Durable queue/outbox/checkpoint ownership, crash/replay and duplicate-dispatch tests, bounded retries/deadlines, no acknowledged intake lost in tested faults |
| 4. Real model integration | Grounded structured output from an approved provider; record safe usage/cost metadata | Explicit provider configuration, actual successful development call, schema failures/refusal tests, provider timeouts and budget controls; no fixture passed off as inference |
| 5. Human review | Inspect evidence and exact draft; request clarification; approve/reject a specific revision | Revision-bound expiring approval, eligibility checks, source/policy recheck and concurrency/race tests |
| 6. Auditable outcome | Produce a visibly simulated delivery receipt for the approved artifact | One transactional local receipt, idempotent replay, cancellation/permission checks and zero outbound delivery verification |
| 7. Complete UI journey | Configure → upload → run → inspect → approve → receipt → audit/usage | Real API integration with loading/error/waiting/expired states and end-to-end browser evidence; static design previews do not qualify |
| 8. Evaluation and operations | Versioned task corpus, source-support scoring, latency/cost reporting; backup/restore and deployment runbooks | Measured results with sample sizes and model/prompt identifiers, restore rehearsal, load/fault tests, documented unresolved limitations |

Actual external email/CRM/social publication is a separately authorized release scope, consistent with the existing product requirements. Initial approvals create clearly labeled simulation receipts, never silent production sends.

## Implementation contracts to preserve

- Browser-selected IDs never authorize access; all organization/workspace resources use verified identity and active local membership before trusted transaction context.
- Runtime connections remain non-owner, NOSUPERUSER and NOBYPASSRLS. New tables require explicit grants, forced RLS and tenant-consistent foreign keys in new migrations only.
- Draft updates carry expected revision. Publication validates the full configuration and permitted tools, then atomically creates an immutable snapshot and audit event. Published configurations are not overwritten.
- Intake carries a tenant-scoped idempotency key and canonical payload digest. Same key/same payload returns the original result; different payload conflicts.
- Runs reference immutable agent/workflow versions. Workers use durable claim/lease/fencing and retry boundaries; a web request does not synchronously execute a long workflow.
- Models cannot hold DB credentials, approve their own work, execute arbitrary shell/code or select unapproved tools. Evidence/schema checks are enforced outside model instructions.
- Budgets, timeouts, source access and current membership are rechecked before sensitive actions. No retry loop performs unbounded inference or duplicate external actions.
- Do not log tokens, keys, full sensitive prompts or customer documents. Audit/usage metadata remains sanitized and tenant scoped.

## Required external inputs and release evidence

The live 2C test requires a controllable development browser or the authorized human invalidation action. Real inference requires an approved provider and a key configured in ignored backend-only environment/secret management; never send the key in chat or use a VITE variable. Credentials are not fabricated, and their absence is not addressed by a production bypass.

Each slice must update BUILD_STATUS.md with implemented routes/UI, actual test commands/results and blockers. Earlier design documents remain historical and must not be rewritten as proof of execution. Production readiness, compliance, SLAs and model accuracy require measured evidence beyond feature completion.
