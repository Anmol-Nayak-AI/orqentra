# Implemented database schema — Phase 2B

Status: implemented and verified on PostgreSQL 18.6, 2026-11-02. This describes the eight-table foundation, not the full future workforce/workflow system. Phase 1's broader proposal remains under [phase-1/DATABASE_SCHEMA.md](phase-1/DATABASE_SCHEMA.md).

## Conventions

SQLAlchemy 2.1 typed declarative mappings use UUID primary keys (ORM-generated UUIDv4), PostgreSQL JSONB, timezone-aware `timestamptz`, explicit named CHECK/UNIQUE/FK/PK constraints and indexes. Direct SQL inserts must supply UUIDs; ORM defaults are not server UUID generators. Server timestamps use `now()`; mutable entities' update triggers set `updated_at=clock_timestamp()`. Engine sessions select UTC, bound connection pooling (5 + 5 overflow), connection pre-ping, 15-second statement timeout and 5-second lock timeout. Timestamps represent instants; timezone display is a session concern.

All FKs use RESTRICT deletion. No cascade silently destroys history. Mutable definitions are archived rather than deleted; runtime role has no DELETE privilege. Version/audit tables are append-only through ORM hooks, row UPDATE/DELETE and statement TRUNCATE rejection triggers, plus restricted runtime privileges. Database administrators can deliberately disable controls and remain trusted operators.

## Entities

| Table | Columns / ownership | Lifecycle and key constraints |
|---|---|---|
| organizations | id, name, slug, status, created_at, updated_at | Globally unique normalized slug; nonempty name; ACTIVE/SUSPENDED/ARCHIVED. Root organization scope uses id. |
| users | id, nullable external_auth_id, email, display_name, status, created_at, updated_at | Unique nonnull external_auth_id; multiple null external IDs and repeated emails allowed. ACTIVE/DISABLED. Email is mutable contact data, never authentication identity. |
| organization_memberships | id, organization_id, user_id, role, status, created_at, updated_at | FK organization/user; unique organization/user; OWNER/ADMIN/MEMBER/VIEWER; ACTIVE/INVITED/REVOKED. |
| workspaces | id, organization_id, name, slug, status, created_at, updated_at | Unique organization/slug and organization/id; ACTIVE/ARCHIVED. Slugs are reserved even after archive. |
| agent_definitions | id, organization_id, workspace_id, name, slug, description, lifecycle_status, draft_configuration, revision, created_by, created_at, updated_at, archived_at | Unique organization/workspace/slug; unique organization/id supports child FKs. Workspace and creator must belong to organization. DRAFT/PUBLISHED/ARCHIVED; JSONB object draft; positive revision; archived timestamp iff archived. Ownership immutable on update. Every update advances revision exactly once; archived definitions cannot be updated. |
| agent_versions | id, organization_id, agent_definition_id, version_number, configuration_snapshot, configuration_schema_version, published_by, published_at | Composite FK organization/definition and organization/publisher membership; unique definition/version_number; positive number/schema version; snapshot JSONB object; append-only. |
| agent_tool_permissions | id, organization_id, agent_definition_id, tool_identifier, permission_scope, status, created_at | Composite definition ownership; unique organization/definition/tool_identifier; identifier matches a bounded reference syntax; scope is JSONB object; ACTIVE/REVOKED. One row per logical tool, with resource constraints inside scope; revoke/reactivate that grant rather than duplicate it. No executable tool body. |
| audit_events | id, organization_id, actor_user_id, action, resource_type, resource_id, correlation_id, metadata, created_at | Composite actor membership FK; UUID resource/correlation references; append-only. Metadata object admits only numeric revision/version_number and a bounded reason_code enum. No arbitrary instructions, tokens or request bodies in metadata. ORM attribute is safe_metadata because metadata is reserved by SQLAlchemy. |

JSONB drafts/snapshots are persistence containers, not executable scripts. Repository configuration handling deep-copies JSON, rejects nonfinite numbers and limits input to 64 KiB. Full model/tool/structured-output allowlists are Phase 2D; no inference or execution consumes these records in 2B. Application/provider secrets must live outside domain records; this checkpoint does not implement a secret store or claim semantic secret detection inside arbitrary draft text.

## Published snapshot semantics

Publishing locks the parent definition, checks expected revision, assigns max(existing version)+1 under that lock, and copies `{configuration, tool_permissions}` into a fresh immutable version. Active tool scopes are copied, not live references. The definition advances revision and becomes PUBLISHED. Editing changes only the draft and returns lifecycle to DRAFT; existing published versions remain untouched. The persistence helper emits an audit event in the same caller-owned transaction. No hidden commits exist in repository methods.

Tool-permission mutation endpoints are not implemented. Future tool editors must acquire the same parent lock and increment its draft revision before publishing; direct administrative SQL is not a supported concurrency protocol. Unique version numbers are DB-enforced; consecutive numbering is enforced by the publication helper, not by rejecting every arbitrary administrative INSERT.

## Indexes

Constraint-backed indexes cover organizations.slug; users.external_auth_id; memberships(org,user); workspaces(org,id)/(org,slug); agents(org,id)/(org,workspace,slug); versions(definition,number); tools(org,definition,identifier).

Explicit indexes: membership user lookup; agents(org,lifecycle,created_at,id), (org,workspace), (org,created_by); versions(org,definition), (org,published_by); audit(org,created_at,id), (org,actor), (org,resource_type,resource_id). Composite index prefixes also cover organization FKs and tenant-filtered reads. No unmeasured GIN/vector/trigram index is added to this configuration-only module.

## RLS and runtime grants

Every table has ENABLE and FORCE RLS. Seven tenant tables compare their organization key against transaction-local `app.organization_id`. Missing context denies all rows; USING and WITH CHECK prevent foreign-scope reads, writes and inserts. `users` is a global identity table with SELECT limited to users who have an active membership in the current organization. Runtime has no INSERT/UPDATE policy/grant for users; identity provisioning is a separate future trusted boundary.

`orqentra_runtime` is LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOBYPASSRLS; no ownership/DDL/TRUNCATE/DELETE grants. Normal tenant tables allow SELECT/INSERT/UPDATE, versions/audit SELECT/INSERT, users SELECT only. Alembic tracking and migrations are not runtime capabilities. RLS tests use actual TCP/password restricted logins, not superusers pretending to be tenants.

The organization GUC is trusted application context, not a cryptographic identity. A compromised DB role capable of arbitrary SQL can select a different GUC; shared-application-role RLS does not defend against complete application compromise. 2C must verify Clerk identity, active user/membership/organization, roles and workspace policy before constructing TrustedOrganizationContext. No HTTP route accepts this internal object or unverified identity headers. The repository additionally rejects writes without active OWNER/ADMIN/MEMBER membership; VIEWER is not a writer. Workspace-grant/private-workspace authorization is not implemented or implied by organization RLS.

## Retention and unresolved policy

Referenced memberships/users/definitions cannot be physically deleted casually; revoke/disable/archive instead. Published snapshots and audit history need a separately reviewed retention/purge process with controlled operator privileges. No automatic data retention or erasure job is implemented. Last-owner protection, membership administration, identity bootstrap/issuer binding, complete agent schema validation and stricter per-action capabilities remain before public business endpoints. See [checkpoint risks](CHECKPOINT_2B.md) and [migration operations](MIGRATION_GUIDE.md).

## Checkpoint 2C identity boundary

Revision 0003 retains the eight-table model. Clerk's verified subject uniquely populates users.external_auth_id; email is not an identity linking key. Active local memberships remain authoritative for OWNER/ADMIN/MEMBER/VIEWER access. New identity functions and owner-protection trigger are documented in [authorization](AUTHORIZATION.md). Audit safe_metadata additionally permits constrained old_role/new_role role values for membership changes.

## Workforce additions — migrations 0004 and 0005

The current schema adds `knowledge_documents`, `task_runs`, `action_receipts` and `organization_invitations`, for twelve forced-RLS domain tables. Original migrations 0001–0003 are retained. Agent versions gain a tenant/id unique key so task-version foreign keys enforce tenant consistency in the database.

- Knowledge documents reference a workspace through its tenant-consistent composite key; content is bounded, hashed and soft-revoked.
- Task runs reference an immutable version, workspace and creator membership through tenant-consistent keys. `(organization_id, idempotency_key)` is unique. Status, positive revision and bounded attempt constraints complement the service transition checks. Queue lookup is indexed by tenant/status/creation time.
- Action receipts reference a run and reviewer membership in the same tenant. `run_id` is unique, mode is constrained to SIMULATED, runtime grants are SELECT/INSERT only, and database/ORM guards reject update/delete/truncate.
- Invitations hold only a SHA-256 token hash, bounded role, state and expiration; the raw bearer token is returned once at creation. A sixth narrowly granted SECURITY DEFINER function atomically accepts a still-valid invitation for the verified active subject, with fixed search path and PUBLIC execution revoked. Its non-login owner receives only the extra table privileges required for this function; the runtime remains non-bypass/non-owner.

The readiness check covers all twelve tables and six identity/invitation functions. An additive migration backup and disposable restore rehearsal passed; no application database downgrade or volume reset was performed.
