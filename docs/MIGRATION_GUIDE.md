# Migration and persistence operations

Run from the nested Git root, `orqentra/`. Commands below target its existing local Compose database. They do not reset volumes. The application never auto-migrates on startup.

## Local setup and forward upgrade

```sh
make db-up
make test-db
make migrate
make runtime-setup
make db-current
make migration-check
make up
```

`make migrate` explicitly selects local Compose credentials from the ignored root `.env` using `scripts/database_support.py`. Credentials are constructed as a SQLAlchemy URL, not interpolated into shell commands. Before upgrading, it inventories public tables, rejects unversioned collisions with domain table names, records preexisting row counts, and creates a PostgreSQL custom-format dump under `.local/backups/` (directory mode 0700, file 0600). It then runs only `upgrade head`, commits and checks row counts. Run against a quiet database; a row-count comparison is not a concurrent-write-safe data checksum or a restore drill.

The first inspected development database had no user tables or migration revision. `0001` adds eight tables and constraints; `0002` installs triggers, timestamp handling and RLS. Both are transactional PostgreSQL DDL. Reviewed scripts contain no table rewrite or data deletion on the forward path. Upgrade is idempotent at head. Existing unrelated tables are not removed; metadata drift checks may flag them for manual review instead of silently dropping them.

`make runtime-setup` provisions the restricted local role and creates ignored `.env.runtime` with random credentials only when absent. Existing credentials are preserved, not silently rotated. It refuses to adopt a privileged existing role or rotate an existing role with a missing credential file. It is a local administrator/provisioning command, not an HTTP endpoint. Keep runtime secrets private and outside source control; `.env.runtime`, `.env` and `.local/` are ignored. Compose uses the runtime file optionally so the original health-only setup still starts before provisioning. Rerun `make up` after first runtime setup to load the restricted URL into the API container.

The API's health endpoint remains process liveness; it is deliberately not evidence of tenant authentication or database readiness. The configured runtime connection was separately tested using the API container's Settings/engine helper.

## Explicit non-Compose Alembic use

With a separately provisioned migration-owner credential in `ORQENTRA_MIGRATION_DATABASE_URL`:

```sh
uv run --locked --package orqentra-api alembic -c apps/api/alembic.ini current
uv run --locked --package orqentra-api alembic -c apps/api/alembic.ini upgrade head
uv run --locked --package orqentra-api alembic -c apps/api/alembic.ini check
```

Supply secrets through your shell/secret manager, not tracked files or pasted command output. Use an independently established backup/restore procedure when not using the local helper. Alembic has no fallback URL and uses a nonpooled migration connection. Offline rendering of secret URLs is disabled. Runtime roles cannot migrate. Cloud deployments need a schema-owning migration role and an operator with permission to provision runtime roles; the local Compose owner is a superuser and must never become the production API credential.

## Sessions and repositories

`database_engine(explicit_url)` accepts only `postgresql+psycopg`. Trusted services construct `TrustedOrganizationContext(organization_id, actor_user_id, correlation_id)` after authorization. `transaction(engine, context)` opens a fresh SQLAlchemy session, sets transaction-local organization scope, commits once on success and rolls back on exceptions. Repositories flush but never commit. Database exceptions are mapped to safe duplicate/integrity/forbidden/general persistence errors without SQL parameters. Calls must not catch a failed SQL statement and continue using the aborted transaction; let the context exit, then start a new one.

Draft updates require an expected revision and use a conditional UPDATE. A stale revision raises StaleRevision. Publication locks the parent row and checks the revision, then stores a detached JSONB snapshot, increments revision and emits an audit event atomically. Concurrent operations cannot successfully publish/update the same expected revision twice. Future tool editors must use this parent-lock/revision protocol as well.

## Disposable database tests and rollback

`make test-db` connects to the local cluster's maintenance database only to create a uniquely named `orqentra_test_<uuid>` database and matching restricted login role. The fixture owns those generated identifiers, applies reviewed migrations and removes only its own database/role in cleanup. A second generated database verifies `0001 → 0002` preserves a sentinel row, then verifies `head → base → head` on disposable data only. No test TRUNCATE, DELETE, downgrade or database drop targets the development database.

For an explicitly provisioned test cluster, tests may instead use `ORQENTRA_TEST_ADMIN_URL` with Pytest directly. The URL must be a PostgreSQL Psycopg URL to a cluster where the test operator may create/drop databases and roles. It does not select an existing database to erase; fixtures always generate new database names. If database tests are run through plain `make check-api` without this setting, they are explicitly skipped. **Run `make test-db` as well; skips are not database verification.** CI includes this mandatory command.

Never run `alembic downgrade` against the user's development database. For a bad deployed migration: stop writers, inspect the backup and failed revision, write a reviewed forward repair or restore into a separate database, verify it, and perform an explicit cutover. No automatic rollback/reset is implemented. DDL reversal drops data and is tested solely to validate disposable recovery mechanics. Backups have been created and listed; a full disaster-recovery restore rehearsal remains future operational work.

## Adding revisions

Inspect live schema/data and migration history first. Use a disposable database, autogenerate a candidate from Base.metadata, review SQL/constraints/indexes, and test fresh and previous-revision upgrades with retained records. Review RLS/triggers/grants explicitly: autogenerate does not prove their correctness or fully compare CHECK constraints. Update role grants for new tables and run restricted-role tests; grants are deliberate rather than broad default privileges for unknown future tables. Commit revision files together with models, tests and documentation. No create_all is used as a migration substitute.

## Checkpoint 2C revision 0003

Revision 0003 extends audit metadata with constrained old_role/new_role fields, adds five pinned-search-path identity functions and self-user RLS, and protects the final owner. Run `make runtime-setup` after migration to transfer the five functions to the dedicated NOLOGIN identity owner and grant the runtime role explicit execution. This operator-only step requires role provisioning privileges; the runtime login remains NOBYPASSRLS. Repeating setup preserves existing runtime credentials.

The 0003 downgrade intentionally refuses to discard role-change audit metadata that the old schema cannot represent. Never downgrade development data to work around that safeguard. Use forward repair and retain audit history. Fresh and reverse migrations are tested only on generated disposable databases.
