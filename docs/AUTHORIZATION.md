# Organization authorization

Clerk establishes identity; active local membership establishes organization access. Every organization API lookup checks the active local user, membership and organization before setting transaction-local tenant scope. Request headers, browser state and Clerk organization/role claims cannot set trusted scope. Organization creation atomically creates its OWNER membership, default workspace and sanitized audit event.

| Capability | OWNER | ADMIN | MEMBER | VIEWER |
| --- | --- | --- | --- | --- |
| Organization, membership, workspace and agent read | yes | yes | yes | yes |
| Agent create/update | yes | yes | yes | no |
| Agent publish/archive; audit read | yes | yes | no | no |
| Organization update; workspace create/update/delete | yes | yes | no | no |
| Membership invite/update/remove | yes | limited | no | no |
| Organization delete | yes | no | no | no |

This is the centralized permission matrix, not a claim that all capabilities have HTTP endpoints. This checkpoint exposes identity, organization list/create/read, membership list/self/read/update/remove, and workspace list. Invitation endpoints, agent execution and organization deletion are absent. ADMIN may manage MEMBER/VIEWER memberships only; only OWNER may manage or assign administrative roles. Removing a membership marks it REVOKED. Role/removal writes serialize on the organization, reread actor access, protect the final active OWNER, and write an audit event in the same transaction. A database trigger also protects the final owner.

## Database boundary

The API uses a NOSUPERUSER, NOBYPASSRLS login role. Tenant tables retain enabled and forced RLS, transaction-local organization scope, explicit grants and no runtime DELETE privilege. Scope is cleared on commit/rollback before pooled connection reuse. Existing repository operations still require trusted service context.

Five narrowly defined SECURITY DEFINER functions resolve identity, provision an identity, list memberships' organizations, verify one organization's membership and create an owned organization. Their owner is a dedicated NOLOGIN, NOSUPERUSER role with BYPASSRLS and only SELECT/INSERT privileges on the five necessary identity/organization/audit tables. This role is never the API login and is not granted to it. Functions pin search_path to pg_catalog, public, revoke PUBLIC execution and accept bound/validated inputs. Runtime provisioning grants execution only on these known functions. The database administrator remains privileged and must be isolated operationally.

RLS is defense in depth against missing tenant filters. Its transaction variables are trusted application inputs: a fully compromised API process or stolen runtime SQL credentials could set them directly and call granted functions. This design does not claim to contain that compromise. Migration/owner credentials must never reach the API container.

Security tests exercise cross-tenant access, forged role claims, concurrent provisioning, owner protection, revoked membership, disabled users, atomic auditing and connection reuse against real restricted PostgreSQL connections.

## Inspected foundation

Before 2C implementation, the local development database was at 0002 with eight domain tables. All eight had enabled and forced RLS; tenant scope used transaction-local app.organization_id. The API role was NOSUPERUSER/NOBYPASSRLS and did not own those tables; the local migration owner was separate. Existing SQLAlchemy transaction helpers reset scope through transaction completion, and their restricted-role tests passed. The frontend previously offered public foundation routes without identity. Checkpoint 2C adds verified identity dependencies before tenant context construction rather than trusting browser-selected organization IDs. The local migration-owner superuser remains an operator credential only.

## Workforce routes

All organization-scoped agent, knowledge, run and audit routes use the same verified bearer identity and active local membership dependency. OWNER/ADMIN publish/archive teammates, manage knowledge/invitations and review artifacts. MEMBER may create/edit drafts, submit/cancel tasks and supply clarification. VIEWER reads authorized organization data. Audit and invitation listings require administrator permissions. UI visibility is supplementary; HTTP permission tests enforce these boundaries.

Invitation acceptance is the one identity-scoped cross-organization bootstrap: possession of an unexpired single-use private link is required, the verified subject is resolved server-side, an active inviter is rechecked, and the database inserts only the link's MEMBER/VIEWER role. It cannot promote an existing membership or grant OWNER/ADMIN. It is not an email-bound invitation, and existing/revoked memberships are not silently reactivated.

The worker has an explicit tenant allowlist, never bypasses RLS, and reads the submitted run's stored creator membership rather than trusting model output for identity. It rechecks membership/workspace/agent eligibility before inference and before saving output. Approval rechecks policy and locks active evidence documents, binds to the stored output hash/revision and requires the unexpired review state. All delivery receipts remain simulated.
