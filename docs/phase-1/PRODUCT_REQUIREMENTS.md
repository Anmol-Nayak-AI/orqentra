# Product requirements

Status: Phase 1 proposal, 2026-10-28. Nothing in this package is implemented or performance-verified. Orqentra and CrewForge are internal labels; commercial naming requires a separate clearance decision.

## Problem and customer

B2B SaaS onboarding teams translate inconsistent intake requests and scattered documentation into implementation plans and customer replies. The first buyer is a head of customer success or implementation; primary users are onboarding operators and designated human reviewers. The product provides configurable AI teammates within a secure organization/workspace, with evidence, controlled tool access, durable workflows, and visible costs.

## Primary customer journey

1. An organization owner signs in through an identity provider, creates an organization and its first workspace, and invites operators and reviewers.
2. An administrator uploads approved onboarding documentation, waits for ingestion, and publishes a teammate version with allowed knowledge, model, tools, and budget.
3. An operator submits a customer request with customer reference, contact, desired outcome, product context, and a client-generated idempotency key.
4. The workflow validates intake, extracts requirements, retrieves workspace documentation, and produces a checklist, missing-information questions, evidence, and a draft reply.
5. The operator inspects intermediate outputs, sources, run status, usage, and any failures. Missing critical facts or sources produce a clarification task, not an invented plan.
6. A reviewer sees the exact recipient, message, evidence, risk flags, and cost. Approval is bound to that exact artifact revision. Editing invalidates pending approval.
7. In development/demo, approval produces one visibly simulated delivery record; no external messages leave the system. A later production connector requires separate enablement and acceptance gates.
8. The team reviews the immutable action receipt, audit trail, and outcome metrics. Failed work can resume within its bounds without creating duplicate actions.

## MVP scope

- OIDC identity; organization membership; workspace grants; owner, administrator, operator, reviewer, and viewer roles. One organization can have multiple workspaces.
- Versioned teammate configuration: name, role instructions, selected model, knowledge scope, tool allowlist, and cost limits. Begin with one onboarding specialist; multiple teammates can be configured but autonomous delegation is excluded.
- One versioned, fixed LangGraph onboarding workflow; teammates fill structured inference steps. React Flow presents a read-only graph, not executable user-authored code.
- Authenticated manual intake; document upload (UTF-8 text and text-based PDF only), ingestion and tenant-scoped retrieval using pgvector; evidence-linked output.
- Run detail, step timeline, clarification tasks, approval inbox, simulated communication, audit view, and basic cost/quality reporting.
- Durable run state, bounded retries, failure recovery, cancellation, per-run budgets, tenant-level daily spend caps, and deterministic fixture mode.
- Thin API integrations boundary with secret references, even though initial delivery uses only a local simulation adapter.

## Exclusions

No live CRM/mail delivery in the first slice; no public intake endpoint, billing, arbitrary tool execution, shell/browser agents, marketplace, autonomous teammate delegation, drag-and-drop workflow execution, OCR, shared cross-tenant knowledge, customer-authored Python, custom training, regulated-data certification, or claim of production readiness. Commercial readiness follows explicit operational/security gates.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | Every operation resolves authenticated user, organization membership, and workspace grant server-side. |
| FR-02 | Published agent/workflow versions are immutable; runs reference exact versions and policy snapshots. |
| FR-03 | Intake keys are required; same key and canonical payload returns the original run; different payload returns conflict. |
| FR-04 | Model output must validate against a strict schema. Each actionable checklist item references allowed document chunks or is explicitly marked unsupported and blocks delivery. |
| FR-05 | Critical missing information creates a human task and persistent wait state; added facts create an audited input revision. |
| FR-06 | Approvals are explicit, expiring, single-use, and scoped to action hash and recipient. |
| FR-07 | Runs expose safe intermediate outputs, recoverable/terminal errors, retry history, evidence, usage, and simulated receipts. |
| FR-08 | Member revocation, source revocation, budget exhaustion, and cancellation stop new sensitive actions. |
| FR-09 | Sensitive state transitions and decisions produce durable audit events. |
| FR-10 | Documents, model configuration, permissions, and retention are workspace/organization controlled. |

## Reliability and limits (proposed targets)

Targets become release criteria only after measurement. Pilot sizing assumption: 10 organizations, 50 concurrent signed-in users, 20 concurrent active runs; queued/waiting runs do not consume a worker slot. Maximum request 64 KiB, document 10 MiB/200 pages, 20 documents per workspace for initial pilot; limits are configurable downward. Reject excess before processing.

- Intake API p95 under 500 ms excluding upload, at pilot load; async work returns 202 after durable commit.
- Supported automated run p95 under 120 seconds excluding queue, human waits, and provider outages; active execution deadline 5 minutes.
- Reclaim a crashed run within 120 seconds when dependencies are healthy; no acknowledged intake lost on worker/Redis failure.
- Proposed service availability objective 99.5% monthly; define dependency exclusions explicitly before offering any SLA.
- Database point-in-time recovery objective: RPO ≤15 minutes, RTO ≤4 hours, verified by restore drills. This differs from the zero acknowledged-intake-loss target for worker failure against a healthy database.
- Approval/clarification expires after 7 days. Model calls ≤3 extraction/draft calls plus 1 schema-repair call; total graph node visits ≤20, each external read attempt ≤30 seconds, maximum 3 attempts for transient errors. All attempts count toward time/cost limits.

## Business and quality metrics

Measure per organization/workspace over weekly cohorts: median operator minutes per completed onboarding, time from intake to approved draft (human wait separately), reviewer acceptance without edits, clarification rate, evidence coverage, unsupported-claim rate from sampled review, completion/failure rate, recovery rate, model/embedding cost per completed onboarding, and cost per accepted plan. Never interpret reviewer approval alone as factual accuracy.

Initial hypotheses to validate in a consented pilot: ≥30% reduction in operator handling time against a measured manual baseline; ≥80% first-review draft acceptance; 100% actionable items with resolvable evidence or delivery blocked; zero unauthorized actions in the release security suite. Report sample size, denominator, time window, and provider pricing assumptions; no achieved results exist yet.

## Open product questions

See [Decisions](DECISIONS.md) for owners, defaults, and decision gates: pilot identity provider, source corpus, sensitive data policy, reviewer separation, retention contract, model/data residency, budget policy, production delivery provider, deployment region, and commercial branding.
