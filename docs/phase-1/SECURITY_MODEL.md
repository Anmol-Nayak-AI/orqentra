# Security model

Status: proposed controls and verification gates. No security tests have run against an application.

## Trust and authentication

Production identity uses OIDC authorization-code flow with PKCE, state and nonce checks; validate issuer, audience, signature, expiry and redirect allowlist. FastAPI is the confidential client and stores an opaque server-side session with a Secure, HttpOnly, SameSite=Lax cookie. Unsafe methods additionally verify a CSRF token and Origin. Rotate sessions after authentication/privilege changes, expire idle sessions at 30 minutes and absolute lifetime at 12 hours (proposed), revoke on account disablement. Never put provider tokens in localStorage. API clients and public webhooks are excluded initially.

Local fixture identity must be opt-in in a development Compose profile, bound to loopback, and rejected at production startup. No “demo” header or query parameter bypasses authentication. Organization provisioning requires authenticated identity and rate limits. Membership invitations use hashed single-use expiring tokens, bind organization/role, and cannot elevate beyond inviter authority.

## Authorization

Effective authorization is the intersection of active identity, active organization membership, active workspace grant, action capability, resource scope and runtime policy. Deny by default. Organization owner/admin may administrate workspaces explicitly; reading customer data still follows the approved role policy. Worker identities are restricted service roles, not tenant administrators. Models cannot grant capabilities.

| Action | Owner | Admin | Operator | Reviewer | Viewer |
|---|---|---|---|---|---|
| Organization policy / ownership transfer | Yes | No | No | No | No |
| Invite members / grant workspace roles | Yes | Yes, cannot grant owner | No | No | No |
| Publish agents/workflows / configure tools | Yes | Yes | No | No | No |
| Upload/revoke workspace knowledge | Yes | Yes | Yes if explicitly granted | No | No |
| Submit intake / respond to task / edit draft | Yes | Yes | Yes | No by default | No |
| View runs and evidence | Yes | Yes | Yes | Yes | Yes |
| Approve communication | Requires explicit reviewer capability, same rule for every role | Requires reviewer capability | No | Yes | No |
| Manage connection secret references | Yes | Yes | No | No | No |
| View workspace audit/cost | Yes | Yes | Limited own runs | Relevant review runs | Summary only |

Rows assume workspace access. Reviewer must differ from run requester by default; changing that policy is an audited organization decision and unresolved pilot requirement. An admin role alone cannot approve. Resource-level service functions recheck authorization even when called from a worker or a route with a decorator.

## Persistence isolation

Organization/workspace IDs in URLs, queue messages, model text, upload metadata and SSE cursors are untrusted. Resolve membership/grant on every request; scope repository queries; enforce composite FKs and RLS. Set transaction-local `app.organization_id`, `app.workspace_id` and identity context using parameterized statements from verified server state; rollback/commit clears context before pool reuse. Missing context yields deny, not global access. Never use session-global SET on a pooled connection.

Runtime DB roles are non-owner, NOSUPERUSER, NOBYPASSRLS, and cannot CREATE/ALTER/TRUNCATE/SET ROLE into privileged roles. Enable and FORCE RLS on tenant tables. Separate migration and backup credentials are unavailable to API/worker. Negative tests run as real restricted roles, including a SQL query missing an application filter, inserts/updates with forged scope, and pool reuse across tenants.

Checkpointer connection pools require the same isolation on every connection and operation. All framework tables including checkpoint blobs/writes need binding-based policies and authorized thread resolution. Globally trusted dispatch discovery can read only minimal work envelopes through a narrow scheduler role; it cannot read document/artifact content. This control cannot protect against fully compromised runtime code capable of forging SQL context; infrastructure segmentation, credentials and a later stronger isolation tier address that residual threat.

## Tools, models, approvals and secrets

- Tool broker intersects immutable AgentToolPermission with current organization/workspace policy, integration resource scope, execution mode and approved action. Model-generated tool names/arguments are validated against allowlists and strict schemas.
- MVP tools are internal retrieval and local delivery simulation. No shell, arbitrary HTTP URL, SQL, browser, user-authored tool code, or direct model-driven external send.
- Secrets reside in an external secret manager; IntegrationConnection stores only an opaque handle/revision. Resolve only in broker at invocation; redact errors/traces; rotate/revoke without republishing agents. Compose uses untracked local secret files. Never commit `.env` contents or expose secrets through UI/API/export/checkpoints.
- Treat intake, documents, tool results and model output as untrusted data. Separate instructions from source content; prompt injection detectors are advisory, while capability checks, no external dispatch path, and human gates enforce boundaries.
- Approval is an authenticated atomic decision bound to exact content/recipient/policy/mode. Recheck membership, scope, hash, expiry and sources before dispatch. An approved row is single-use; direct graph resume cannot authorize an action.
- Simulation safety is server-owned immutable run mode, selected from deployment configuration. Dev/demo contains no live connector credentials/adapter registration and denies network delivery endpoints at egress. UI labels are supplementary, not the safety boundary. Test with an instrumented outbound trap.

## Data protection

Private S3-compatible buckets; keys generated by server under scoped UUID prefixes; no public ACLs. Signed upload URLs expire in 5 minutes and restrict key/size/content type where supported. Completion verifies actual bytes/checksum/limits. Quarantine all uploads; sandbox parsing without network and with CPU/memory/page/time bounds; malware scanning gate before indexing. Download requires current document authorization before issuing a short-lived (60-second) signed URL; already issued URLs cannot be revoked instantly, so highly sensitive content uses an authenticated proxy instead.

Encrypt network traffic and database/object/backups at rest. Keep raw customer content out of logs, metrics and default traces; logs contain event codes and IDs. Minimize prompt data, select providers with agreed retention/training terms and region, and disallow sensitive data categories until contracts/policy approve them. Authorized source references do not prove semantic support; sampled evidence review remains necessary.

Revocation stops retrieval immediately; it invalidates pending dependent approvals and prevents stale source use before dispatch. Cached retrieval keys include organization/workspace, scope hash, content revision, policy revision and embedding profile. No cross-tenant shared cache. SSE connections recheck session/grants at least every 30 seconds; reconnect authorizes cursor/run again.

## Audit, abuse and operations

Domain state change and audit event commit together; API fails the mutation if audit insertion fails. Append-only DB permissions, signed periodic digests/export to immutable storage and restricted audit readers improve tamper evidence; database administrators remain in the threat model. Record actor, tenant/workspace, run/action, event type, policy/bundle hash, timestamp and correlation ID. Never record raw credentials or unnecessary message content in audit.

Rate-limit by identity/organization/IP; quotas on intake, uploads, active runs, token budget and parser resources. Provider credentials cannot elevate organization quotas. Session/CSRF, file parsing, dependency provenance, restore/replay, log redaction and tenant deletion are release gates. Emergency stop disables new dispatch globally or per organization and is itself audited. Incident response rotates secrets, disables affected connections, preserves evidence, scopes tenant exposure, and follows contractual notification requirements established before launch.

## Security verification contract

See AC-01, AC-02, AC-05, AC-09–AC-15 in [acceptance criteria](ACCEPTANCE_CRITERIA.md). Threat scenarios and residual risks are in [threat model](THREAT_MODEL.md). No claim of compliance, penetration-test completion, or production readiness follows from these documents.

Reference: [PostgreSQL row security](https://www.postgresql.org/docs/18/ddl-rowsecurity.html) documents owner/superuser bypass and policy semantics; application controls above must be independently implemented and tested.
