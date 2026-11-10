# Provider preparation and acceptance checklist

As of 10 November 2026, account configuration is in progress. **No real-provider resource acceptance is authorized by configuring credentials.** Existing Render manifests are unapplied; Razorpay is TEST-only; E2B resource execution is off by default. Production release remains pending.

## Environment boundaries

| File / environment | Consumer | Contents and default |
| --- | --- | --- |
| `.env` | Local Compose / web build | PostgreSQL setup and public Clerk publishable key only |
| `.env.runtime` | API / worker | Restricted PostgreSQL login; no migration owner |
| `.env.auth` | API | Clerk issuer, RSA public signing key, exact frontend origins |
| `.env.ai` | API / worker | Backend OpenAI key |
| `.env.billing` | API only | Razorpay TEST key, webhook secret, server plan bindings; provider/actions disabled by default |
| `.env.sandbox` | Worker only | E2B key, reviewed template, explicit execution flag; disabled by default |
| `.env.telemetry` | API only | Optional approved collector endpoint; no exports by default |
| Hosted secret manager | Future reviewed services/job | Separate environment-specific runtime and migration credentials |

Configured copies are ignored; examples contain placeholders. Set local configured files to mode 0600. Do not copy secrets into GitHub source, frontend variables, workflow inputs, public issues, logs or chat. Do not share provider secret files between API and worker indiscriminately.

## Implemented and locally verified

- Razorpay provider interface, test-key validation, HTTPS requests, bounded responses, no redirects or automatic provider POST retries.
- Server-quoted subscription authorization, provider-state reconciliation and period-end cancellation. Browser return/hosted link never proves payment success.
- Raw-body HMAC webhook verification, constant-time comparison, bounded signing-key rotation, tenant/plan binding, event/body idempotency, freshness/order checks and immutable histories.
- Invoice snapshots exclude customer/contact/card details; ambiguous operations stay UNKNOWN until an authoritative provider reference resolves them.
- E2B separate code approval, exact hash/revision/expiry binding, immutable approval intent, 60-second sandbox lifetime, 20-second Python runtime, bounded output, deny IPv4/IPv6 egress/public traffic, no host credentials/mounts, CPU/memory attestation, cleanup auditing and no local fallback.
- Database admission enforces **one RUNNING execution per organization by default**, configurable only from 1 to 2. A serialized tenant lock prevents worker replicas from claiming additional queued jobs beyond the limit. Expired attempts become UNKNOWN rather than being resubmitted. This is a tenant limit, not proof of an account-wide global resource ceiling.
- Unapplied staging/production Render templates, non-root containers, explicit production settings, separate manual-only database job and offline configuration checks. No deploy-on-start migration.

## Which checks can run without customer charges?

| Check | Charge/resource boundary | Current status / authorization |
| --- | --- | --- |
| Unit, UI, CSP, local browser and disposable PostgreSQL regressions | No real payment/sandbox call; uses local compute and synthetic transports | Authorized; latest 103 unit / 99 DB / 61 UI / 4 CSP / 7 anonymous browser checks passed |
| Invalid-signature, replay, tenant and concurrency fixtures | No provider connection or resource | Authorized and passed; not real-provider proof |
| Offline Render/YAML and hosted-target validation | No cloud connection or resource | Authorized and passed |
| Local secret scan and repository publication | Source publishing, not service hosting or payment processing | Authorized; publication evidence in REPOSITORY_ACCESS.md |
| Razorpay TEST metadata and dummy subscription/authorization/callback/cancellation/invoice journey | Test Mode cannot accept real payments; still creates test records and may need an inbound callback endpoint | **Pending explicit authorization**; test keys only, dummy payment instruments only, no customer notifications. No public tunnel without separate approval |
| Read-only Render account/configuration inspection | Does not deploy a service, but requires an account connection | Pending account configuration and explicit provider-test authorization |
| E2B template inspection and one isolated sandbox smoke | Creating/running a sandbox consumes metered compute/credits even on Hobby | **Pending explicit resource authorization**; never assume Hobby means unlimited/free execution |
| Render deploy, managed DB, TLS ingress and rollback drill | Creates/runs hosted resources, possibly paid | Not authorized; a free account does not authorize deployment |
| OpenAI live evaluation | Consumes API credit | Opt-in only; not repeated by the default test suites |
| Any LIVE payment, settlement or customer charge | Real money movement | Prohibited under current authorization |

Razorpay describes Test Mode as unable to accept real payments in its [official mode documentation](https://razorpay.com/docs/payments/dashboard/test-live-modes). E2B describes usage-based compute and Hobby credits in its [billing documentation](https://docs.e2b.dev/billing); available credit and overage settings must be checked before an authorized run. Neither provider's documentation is evidence that this repository passed live acceptance.

## Pending real-provider evidence

- [ ] Razorpay TEST account/plan bindings privately configured and independently confirmed to use test keys.
- [ ] One explicitly authorized test subscription creation and dummy authorization; correct subscription/organization binding and PENDING-to-verified-state transition.
- [ ] Real signed callback delivery, retry/replay deduplication, changed-body conflict rejection and delayed/out-of-order lifecycle handling.
- [ ] Test renewal/period expiry/cancellation, invoice retrieval, uncertain request reconciliation and bounded signing-key rotation.
- [ ] Reviewed E2B template policy and account spend limits; one authorized isolated run with measured duration/resources and confirmed teardown.
- [ ] Real E2B IPv4/IPv6/private-network/public-ingress restrictions, timeout, output cap, cleanup failure/recovery and concurrency across workers/organizations.
- [ ] Account-wide E2B concurrency/cost enforcement and failover behavior measured before any multi-replica commercial enablement.
- [ ] Approved Render resources and production identity/secrets configuration, platform manifest validation, hosted migration/role/RLS, ingress health and restricted-origin acceptance.
- [ ] Hosted backup/restore timing and rollback rehearsal; no development-volume reset.
- [ ] Remaining genuine-session, two-human handoff, reliability/load/security and operational release gates in RELEASE_ACCEPTANCE.md.

Before an authorized provider run, record: provider/environment, exact action, maximum resource count/duration/credit budget, approved test identities/data, callback exposure scope, cleanup plan and stop conditions. Record redacted observations afterward. Never turn a mock response, prepared checkout link or configured credential into a production-ready claim.
