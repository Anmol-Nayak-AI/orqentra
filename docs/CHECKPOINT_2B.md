# Checkpoint 2B — database and persistence foundation

Status: mandatory local 2B checks passed, 2026-11-02. Authentication, frontend features, Forge HTTP endpoints and orchestration were not added. This is not a production-readiness or full Phase 2 completion claim.

## Inspection and plan

Read the completed 2A report, Compose, backend files/configuration/dependencies and Git state before edits. Running API/web/PostgreSQL services were healthy. PostgreSQL was 18.6; the local database was `orqentra`, owned by the local provisioning superuser. A catalog query found **zero user tables and no Alembic revision**. No SQLAlchemy models, database connection setup or migrations existed. SQLAlchemy 2.1.6, Alembic 1.20.1, Psycopg 3.3.6, Pydantic 2.14.1 and Pytest 9.2.0 were already pinned/installed. No dependency changes were needed.

All existing 2A files were uncommitted/untracked; no commit/reset/recreation was performed. The implementation plan was models/constraints → reviewed table and security revisions → scoped sessions/repositories → disposable tests → backed-up forward local migration → restricted role/container verification → documentation. Existing Docker volumes, unrelated databases and other projects were preserved.

## Files created

- `apps/api/src/orqentra/persistence/{__init__,models,errors,session,repositories,roles}.py`
- `apps/api/alembic.ini`, `apps/api/alembic/env.py`, `script.py.mako`, `versions/0001_tenant_foundation_tables.py`, `versions/0002_database_guards.py`
- `apps/api/tests/test_persistence_unit.py`, `tests/database/conftest.py`, `tests/database/test_persistence.py`
- `scripts/{database_support,migrate_database,provision_runtime,test_database}.py`
- This report, [schema](DATABASE_SCHEMA.md), [relationships/ER](DATABASE_RELATIONSHIPS.md), [migration guide](MIGRATION_GUIDE.md).

Private generated local artifacts, excluded from Git: `.env.runtime` and `.local/backups/*.dump`. They are not source files or committed secrets.

## Files modified

- `apps/api/src/orqentra/core/config.py`: optional redacted runtime/migration URLs, no default DB/auth bypass.
- `apps/api/Dockerfile`: include Alembic configuration/revisions in the API image.
- `infrastructure/compose.yaml`: optional restricted-runtime env file; existing DB volume/config retained.
- `Makefile`: migration/current/check/runtime/test-db tasks.
- `.github/workflows/ci.yml`: disposable database tests and migration verification in integration job.
- `.gitignore`, `.dockerignore`, `apps/api/.env.example`, `README.md`, `scripts/seed_demo.py`: setup/backup boundaries and current checkpoint documentation.

## Tables and constraints implemented

Eight tables: organizations, users, organization_memberships, workspaces, agent_definitions, agent_versions, agent_tool_permissions, audit_events. UUIDs, JSONB, timezone-aware timestamps, explicit lifecycle CHECKs, normalized/scoped slugs, named uniqueness/FK constraints and indexed tenant/FK query paths are implemented. Composite keys reject foreign tenant workspaces/definitions/authors/publishers/tool references. Email is not an auth identity.

Published versions and audit records are protected at ORM and database levels, including raw UPDATE/DELETE/TRUNCATE tests as the owner. Runtime privileges additionally prohibit their mutation. Agent updates use revision CAS; publication serializes on the parent row and freezes draft/tool configuration. Audit metadata is allowlisted by both repository construction and DB CHECKs; business write and audit share a transaction.

ENABLE/FORCE RLS covers all eight tables, with organization-scoped policies and membership-filtered global user reads. A real NOBYPASSRLS/NOSUPERUSER login is used in tests. Runtime has no schema DDL, table DELETE/TRUNCATE or identity provisioning privilege. See the limitations below before interpreting this as user-level authorization.

## Executed verification

| Check | Result |
|---|---|
| `make check-api` | Ruff lint and format passed across backend/scripts; strict mypy passed on 15 source files. **15 tests passed** (6 existing API + 9 persistence unit). 36 DB cases explicitly skipped in this invocation without test admin URL, then run separately below. |
| `make test-db` | **36 PostgreSQL integration cases passed**, no skips; disposable databases and restricted roles only. |
| Migration tests | Fresh schema, metadata drift, retained sentinel across 0001→0002, disposable head→base→head, uniqueness/FKs/JSONB/timestamps/rollback, concurrent CAS/publication, RLS matrix across all tables, missing/foreign scope, privileges, audit sanitization/atomicity and immutable version/audit controls passed. |
| `make migrate` | Applied forward 0001 then 0002 after private pg_dump. Initial preexisting public-table map was empty; no existing records to overwrite. |
| Repeated `make migrate` | Idempotent at head; all eight existing domain table counts (zero) preserved after another backup. No development downgrade. |
| `make runtime-setup` twice | Restricted role created, private credentials generated once and retained on repeat. |
| `make db-current`, `make migration-check` | `0002 (head)`; no new upgrade operations detected. |
| `make up` | Images built; existing PostgreSQL volume retained; API recreated with restricted runtime configuration; API/web/PostgreSQL all healthy. |
| Connection inside API container | current_user=orqentra_runtime, superuser/bypass=false, SELECT organizations without scope returns zero rows. |
| `make contracts-check` | Existing OpenAPI/TypeScript contracts unchanged and matching. No new HTTP endpoint. |
| `E2E_BASE_URL=http://127.0.0.1:8080 make e2e` | **1 Chromium browser test passed**: actual API connectivity, theme and route navigation through existing built UI. |

Backend total: **51 executed cases across unit/API and isolated DB invocations**; browser smoke adds one separate E2E case. These counts do not include unexecuted future authentication/workflow tests. Hosted GitHub Actions have been configured, not executed in this session. Mermaid source exists; visual rendering was not verified.

## Preservation evidence

Original `postgres_data` volume was reused; no Compose down-volume/reset/prune was run. Both before/after migration row-count checks passed. A reviewed additive forward path and disposable sentinel-upgrade test provide preservation evidence for this baseline, not a guarantee about arbitrary production data. Private custom-format dumps were created before both upgrades. Their archive structure was checked; a full restore drill is not claimed.

The temporary review database created by this checkpoint was removed only after verifying it contained solely an empty Alembic tracking table. All randomly generated test databases/roles are cleaned by their fixtures. No test fixtures or demo organizations were inserted into development. Existing frontend remains at http://127.0.0.1:8080.

## Security findings, limitations and 2C readiness

- RLS protects row scope against omitted predicates and foreign-scope operations under the runtime role, **not arbitrary SQL/application compromise**: that role can set a different organization GUC. Trusted context must come from verified server-side authorization in 2C, never request headers/body identity. No such authentication route exists yet.
- User bootstrap/global identity mutation is deliberately unavailable to runtime. 2C needs a reviewed constrained provisioning boundary after Clerk JWT verification, issuer/subject binding, organization membership resolution and role checks. Do not give the API migration-owner credentials to bypass this restriction.
- Same-organization private workspace grants, last-owner membership protection, invitations, disabled-account enforcement, role administration and full Forge capability policies remain before public endpoints. The repository's active writer-membership check is a persistence guard, not complete product authorization.
- DB triggers/privileges do not constrain a privileged DBA disabling controls. Retention/purge, disaster-recovery restores, load/pool sizing, lock/deadlock recovery and migration deployment discipline need later operational verification. Repositories do not automatically retry transactions with unknown outcomes.
- Draft JSON persistence validation is not the full future agent/model/tool schema, secret detection or execution sandbox. Tool configuration is never executed here. Future tool mutation must follow the parent revision/lock protocol.
- The existing development-only npm advisory remains in [dependency review](DEPENDENCY_ADVISORIES.md); this checkpoint does not change or waive it.

2C may now build on the schema and tested persistence boundary. **Stop here; no Clerk integration, new frontend functionality, LangGraph runtime or orchestration was started.** Recommended Git checkpoint after review: `feat: add phase 2B tenant persistence and migrations`. No commit/push was performed.
