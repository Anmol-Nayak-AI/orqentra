# Threat model

Status: initial design review. Risk ratings are qualitative estimates before validation. Owners are roles to assign, not named people. Review whenever tools, tenants, models, identity or data flows change.

## Assets, adversaries and boundaries

Assets: customer intake/contact data; proprietary onboarding documents and embeddings; artifact drafts/evidence; identity/session tokens; provider credentials; approval integrity; delivery receipts; usage budgets; workflow/checkpoint integrity; audit history; availability and tenant reputation.

Adversaries: unauthenticated internet clients, malicious or compromised tenant users, malicious source authors, compromised provider/tool responses, compromised workers/dependencies, insiders with operational access. Accidental bugs, retries, outages and operator restore mistakes also threaten integrity.

Boundaries: browser→ingress/API; identity provider→session; API/worker→database and pool; worker→checkpoint schema; relay→Redis→worker; upload→parser→knowledge; tool broker→provider; domain→telemetry; operator→backup/restore; one organization/workspace→another. [Architecture](ARCHITECTURE.md) diagrams the data paths.

## Threat register

Likelihood/impact: L low, M medium, H high. “Residual” assumes controls are actually implemented; presently all controls are unverified.

| ID / category | Attack or failure | Initial L/I | Controls and test | Residual / owner |
|---|---|---|---|---|
| T-01 / disclosure, elevation | Swap organization/workspace/resource IDs in routes, exports, evidence, SSE or upload completion | H/H | Server scope resolution, composite FKs, RLS, authorization on each resource; AC-01/02/10 | M/H; backend/security |
| T-02 / disclosure | Missing SQL predicate, pool tenant-context leakage or cache namespace collision | M/H | Transaction-local scope, FORCE RLS, restricted role, scope-aware keys, direct SQL and pool tests; AC-02 | L/H; database owner |
| T-03 / tampering | Client supplies another thread ID, resumes another tenant's checkpoint, or reads checkpoint blobs | M/H | No raw saver API; binding ownership; all checkpoint tables RLS; read/write/list/delete negative tests; AC-02/03 | M/H pending spike; orchestration owner |
| T-04 / spoofing | Stolen session, login CSRF, forged token or replayed invite | M/H | OIDC validations, PKCE, state/nonce, secure cookies, CSRF, single-use invites, revoke/expire tests; AC-10 | M/H; identity owner |
| T-05 / tampering | Prompt injection in source tells model to exfiltrate data or self-approve | H/H | Treat sources as data; schema/tool allowlist; no arbitrary network; human action gate; adversarial evaluation AC-11 | M/M; AI/security owner |
| T-06 / elevation | Worker/model bypasses reviewer, approves own request or reuses approval after edit | M/H | Server policy, separation of duties, CAS, content/recipient/mode hash, dispatch recheck; AC-05/09 | L/H; actions owner |
| T-07 / integrity | Duplicate intake, queue replay or concurrent resume creates duplicate action | H/H | Unique key+hash, action slot/approval constraints, local atomic simulation; AC-04 | L/H; actions owner |
| T-08 / integrity | Provider accepts action, worker crashes before receipt; naive retry sends twice | M/H | Unknown state, stable provider key/lookup, freeze/manual reconcile; live connector gate AC-16 | M/H until provider chosen; integrations owner |
| T-09 / availability, spend | Run loops, malicious long request, repeated retries, concurrent budget overrun | H/H | Persisted counters/deadlines, schema bounds, per-tenant quotas, atomic reservations; AC-07/12 | M/M; orchestration/operations |
| T-10 / disclosure | Secrets in domain JSON, logs, checkpoint, exception or frontend bundle | M/H | Secret handles/broker, no raw credentials, redaction/content scanning, restricted traces; AC-11 | L/H; security/operations |
| T-11 / availability, execution | Malicious PDF, decompression bomb, parser exploit or upload path traversal | M/H | Type/size/page limits, generated keys, quarantine/scanning, isolated no-network parser, time/memory limits; AC-12 | M/H; knowledge owner |
| T-12 / integrity | Stale source, fabricated citation or misleading but valid chunk ID | H/H | Scoped immutable citations, source recheck, evidence coverage validation, semantic review/evaluation; AC-06 | M/H; AI/product |
| T-13 / repudiation | Important action lacks audit; operator edits audit to hide abuse | M/H | Atomic audit insertion, append-only permissions, external digest/export, alert on gap; AC-08 | M/H against privileged DBA; security/operations |
| T-14 / availability | Redis loss, DB outage, worker crash or checkpoint incompatibility | H/H | DB outbox/scanner, leases/locks/fences, retries, pinned executors, restore drills; AC-03/13 | M/H; operations |
| T-15 / disclosure | Deleted source survives checkpoint, cache, evaluation data, tracing or restored backup | M/H | Immediate revoke, retention jobs, deletion inventory/tombstones, restore suppression; AC-14 | M/H; data/operations |
| T-16 / supply chain | Malicious dependency, unpinned image, compromised CI or deserialization payload | M/H | Hash lockfiles, digest images, least-privilege CI, provenance/SBOM, serializer allowlist, scans; AC-15 | M/H; platform/security |
| T-17 / disclosure | Provider stores/trains on customer data or wrong-region processing | M/H | Approved provider/region, contractual terms, minimization, explicit sensitive-data restrictions; launch decision D-03 | M/H; product/security |
| T-18 / integrity | Stale leased worker writes checkpoint after takeover or cancellation | M/H | Exclusive thread lock, fencing adapter, write CAS, abort on lost DB session; fault-injection AC-03 | M/H pending spike; orchestration |
| T-19 / integrity | Demo deployment accidentally registers live delivery adapter or credentials | M/H | Immutable server mode, absent live adapter/secrets, egress deny, instrumented outbound trap; AC-09 | L/H; platform |
| T-20 / elevation | Forged queue message or scheduler discovery role reads all tenant content | M/H | Messages carry ID only, resolve DB ownership; narrow metadata-only role; adversarial queue tests AC-02 | L/H; platform/backend |

## Priorities and risk treatment

Release blockers for the first slice: T-01/02/03 tenant and checkpoint isolation; T-06/07 approval and duplicate-action controls; T-18 stale-worker fencing; T-19 simulation containment. Do not substitute a UI warning for these controls. Document parser security is a blocker before accepting uploaded files. Provider contracts, restore drills, production observability and T-08 reconciliation block commercial/live deployment, even after a demo works.

Residual risk acceptance requires an accountable owner, compensating controls, expiry/review date, and a linked test/result in the release record. No risk has been accepted merely by writing this table. Assumptions to validate: identity provider availability, nonprivileged app role enforcement, no unrestricted worker egress, and trusted operators with separately managed credentials.

## Abuse and incident scenarios

For suspected cross-tenant leakage: disable affected endpoints/dispatch, revoke sessions and credentials, preserve scoped immutable evidence without copying unrelated customer data, identify reads and exports via audit/trace correlation, restore boundary controls, verify negative tests, and notify according to an established contractual/legal process. For unknown delivery: freeze the action and connector, obtain provider evidence, record reconciliation actor/outcome, then permit an explicit authorized next step. For poisoned knowledge: revoke source, invalidate pending bundles, enumerate dependent artifacts and request reviews; never silently rewrite prior evidence.

## Review checklist

Before each release, attach actual AC results, inventory new data sinks/tools, verify secrets/egress/role privileges, review unknown actions and outstanding reservations, and confirm retention/restore procedures. Security targets are test scope statements, not a proof of absence of vulnerabilities.
