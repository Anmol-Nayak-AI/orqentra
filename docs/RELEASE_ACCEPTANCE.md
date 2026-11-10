# Commercial release acceptance — 2026-11-10

Decision: **PENDING — not authorized for public deployment or customer payments.** Local implementation continues; account absence is not reported as a completed integration.

| Gate | Current evidence | Remaining acceptance |
| --- | --- | --- |
| Clerk / session security | Existing real sign-in, identity provisioning, sign-out and automated recovery/RBAC checks | 2C genuine provider-invalidation interval remains unverified; production Clerk and rotation acceptance |
| Tenant data | Forced RLS, restricted role, composite tenant keys, disposable-DB isolation tests; forward migration 0011 | Hosted TLS/role provisioning, adversarial staging review |
| RAG / oversight | Existing cited vector retrieval, explicit human handoff and task approvals | Expanded measured quality/evasion corpus, two-real-user support, operational handoff availability |
| Durable orchestration | LangGraph onboarding checkpoints and synthetic crash/restart recovery; existing task budgets/review gates | Identified pending-write/checkpoint ordering defect fixed by migration 0010; production load/crash/cancellation and retention testing; complete other workflow integrations |
| Isolated execution | Disabled E2B adapter with strict requested/verified policy, approval-hash interface and fixture tests | Persisted independent code approval/queue/results integration is implemented; real account, explicit paid-resource approval, network/timeout/escape and cleanup tests remain |
| Billing | RLS ledger, atomic quotas, durable quote-bound test checkout/cancellation, authoritative reconciliation, append-only invoice/subscription history, signature/replay/order fixtures | Real test-provider checkout/callback/renewal/cancellation/invoice acceptance; approved commercial pricing/quotas and tax/refund requirements; no live charges authorized |
| Deployment | Non-root containers, environment guards, unapplied Render templates, separate manual hosted migration/verification job, local health/readiness | Actual hosted migration/role/secret-manager acceptance, approved staging resources, real Render validation, TLS/domain/ingress/load tests, production rollout approval |
| Observability | Structured safe logs, optional manual payload-safe OTel request spans, existing audit trail | Real collector delivery/privacy/failure evidence, worker/cross-queue tracing, monitored SLOs/alerts, on-call destinations and failure drills |
| Backup / rollback | Private pre-migration dump restored to disposable database, preserved existing counts, documented forward/rollback procedure | Encrypted managed retention/PITR, recovery timing and agreed RPO/RTO, rehearsed production-compatible rollback |
| Dependencies / supply chain | Local pip-audit and npm production-graph audit report no known findings; pinned tools and dependency-security CI job added | Linux CI job has not run remotely; OS image scanning/signing/SBOM, unresolved development-only advisories and independent security assessment |

Account/authorization requirements for the external gates remain: Render staging/production hosting and managed PostgreSQL, Razorpay test application/webhook configuration, reviewed E2B template/account and explicit permission to create sandbox resources, production Clerk, domain/secret/monitoring services. Credentials belong in approved secret storage, never chat. No external accounts, public services or paid resources have been created by this increment.

Do not mark any gate passed from fake billing success, mock sandbox output, simulated action receipts, unit tests alone, or another environment's identity/session. See COMMERCIAL_ROADMAP.md, COMMERCIAL_OPERATIONS.md and ORCHESTRATION_AND_SANDBOX.md for implementation and evidence limits.

Latest user workflows, precise evidence and remaining functionality: [10 November functional release](FUNCTIONAL_RELEASE_2026_11_10.md). Commercial acceptance remains PENDING.

Latest local evidence: [commercial lifecycle report](COMMERCIAL_LIFECYCLE_2026_11_10.md). The 103 unit, 98 disposable-DB, 61 frontend, 4 CSP and 7 anonymous browser checks passed; expected opt-in/configuration skips are recorded separately. These results do not close real-provider or hosted acceptance.
