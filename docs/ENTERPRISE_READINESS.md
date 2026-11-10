# Orqentra enterprise readiness

> Historical checkpoint snapshot. Current user-authorized development scope and sequencing are in [COMMERCIAL_ROADMAP.md](COMMERCIAL_ROADMAP.md); production remains unaccepted.

**Product:** Orqentra. **Positioning:** Your workforce, intelligently orchestrated.

**Decision:** a general platform for specialized AI teammates and governed workflows, with B2B onboarding as the first use case. The tagline describes the intended product; executable teammate orchestration is not present in checkpoint 2C. This naming choice is not trademark clearance or a compliance certification.

Reference supplied by the user: [How I Build AI Teammates With Claude Code — Grok Bot Clone, Code With Antonio](https://www.youtube.com/watch?v=mQBuZ6Dp0u0). Only title/author metadata could be retrieved; no transcript or complete video walkthrough was available. No detailed feature requirement is attributed to the video without that evidence. Repository requirements and explicit user decisions remain authoritative.

## Current release decision

**Not production approved.** Checkpoint 2C live sign-out/invalidated-session recovery remains pending in [the acceptance report](CHECKPOINT_2C.md). Do not start 2D or enable AI execution before that gate passes. Enterprise readiness is a set of verified controls and operational capabilities, not a visual theme or a passing unit-test count.

## Implemented foundation and remaining gates

| Area | Current implementation/evidence | Required before enterprise release |
| --- | --- | --- |
| Identity | Existing Clerk development app, pinned RSA signature/issuer/claims verification, unique local identity, no email linking | Finish live invalidation recovery; establish production identity application, MFA policy and signing-key rotation runbook |
| Tenancy | Active local membership, explicit permissions, restricted runtime role, FORCE RLS, composite tenant foreign keys | Independent adversarial security review; workspace-specific grants when workspace delegation is introduced |
| Organization lifecycle | Atomic owner/default workspace/audit creation, final-owner protection, role restrictions | Invitations and acceptance, ownership transfer UX, offboarding policy and production user-management procedures |
| Browser security | Exact configured Clerk CSP, no token persistence in app storage, failed-session cache cancellation/removal and session-specific denial barrier | Complete live session gate; maintain dependency remediation process and verify production TLS/CSP |
| Request boundaries | 64 KiB default application body cap including chunked bodies; matching nginx cap; early safe 413; ingress body/keepalive timeouts | Distributed request-rate/abuse controls, per-tenant quotas and separately designed upload limits before uploads exist |
| Production configuration | Startup rejects absent auth/runtime DB config, insecure HTTP frontend origins and API-side migration credentials | Secret manager, TLS ingress, network isolation, production Clerk app and independent deploy credentials |
| Service readiness | `/api/v1/health` remains liveness; `/api/v1/ready` returns 200 only with local auth config and reachable restricted DB with forced RLS and known identity function grants | Monitor readiness externally, define rollout thresholds and incident ownership; validate live IdP separately |
| Database operations | Preserved 0001/0002/0003 migrations, private pre-upgrade dump, bounded DB connect/pool/statement/lock waits, pool disposal at shutdown | Encrypted backups/PITR, automated backup retention, a measured restore drill into a separate database, documented RPO/RTO |
| Audit | Append-only events, sanitized metadata, transactionally coupled domain mutations | Tenant-authorized audit export/search, retention policy, access-review process and alerting |
| Build/release | Locked dependencies, CI definitions, contracts, isolated DB tests, browser smoke tests | Staging environment, protected release workflow, image scanning/SBOM and compatible dependency advisory resolution |
| Teammate configuration | Versioned persistence foundation exists | Gated 2D Forge API validation, model/tool allowlists, CAS editing, immutable publication and complete lifecycle authorization |
| Execution | Deliberately absent | Durable jobs/state, cancellation, retry/idempotency rules, tenant budgets, model/provider timeouts, policy enforcement and human approvals |
| Knowledge/connectors | Deliberately absent | Tenant-scoped ingestion/retrieval, source provenance/deletion, scoped connector credentials and SSRF/tool policy |
| Enterprise procurement | No certification/SLA or residency claim | Select deployment region, subprocessors, DPA, retention/deletion commitments, SSO/SCIM requirements and compliance evidence appropriate to target customers |

## Near-term sequence

1. Finish 2C with genuine development-session invalidation, recovery, server outcome evidence and unchanged local identity; mark accepted only with evidence.
2. Build 2D's teammate Forge lifecycle against the existing tenant/version/audit constraints. No live model execution is part of that phase.
3. Finish the operator-facing Command Center/Forge workflows and real API integration, then acceptance tests for lifecycle and tenant permissions.
4. Add one bounded onboarding workflow, usage budgets, human approval and visibly simulated delivery. Do not turn a channel-bot demo into uncontrolled production tool execution.
5. Operate a consented development/staging pilot; measure latency, workload limits, restore time, isolation and incident response before setting service commitments.

## Operational interfaces introduced in this hardening pass

`GET /api/v1/ready` returns only `{"status":"ready"}` or `{"status":"not_ready"}` (503). It checks local configuration and database privilege/schema prerequisites without publishing diagnostics or contacting Clerk. It does not prove external identity-provider availability, successful sign-in, backup recoverability or workload capacity. The process-liveness contract is unchanged. Production load balancers should use readiness, not infer it from liveness.

Production startup requires `ORQENTRA_ENVIRONMENT=production`, a runtime `ORQENTRA_DATABASE_URL`, the Clerk verification settings, and HTTPS allowed frontend origins. `ORQENTRA_MIGRATION_DATABASE_URL` must be absent from the API environment. Runtime DB privilege safety is also enforced on protected identity requests and readiness. The provided Compose stack remains a localhost development deployment, not a production manifest.

API bodies default to 65536 bytes via `ORQENTRA_MAX_REQUEST_BYTES` (configurable within validated bounds). The current nginx cap is 64 KiB; changing the application setting alone cannot raise that ingress cap. Application limit errors have a safe error envelope, correlation ID, no-store and nosniff. Nginx may reject larger bodies first with its own 413 page; clients use status rather than rely on a JSON body. Idle ingress body reads are bounded by nginx's 15-second body timeout; this is not a global per-request execution deadline. No upload endpoint is added.

Readiness, request limits and production guards add no domain table migration and do not rewrite prior revisions or modify tenant records. Existing database tests always use generated disposable databases. Do not delete Docker volumes, rotate local DB credentials or reset development records to fix deployment failures.
