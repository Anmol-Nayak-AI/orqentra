# Checkpoint 2A — monorepo and local infrastructure

Status: 2A foundation implemented and locally verified, including containers on 2026-10-31. A build-tool dependency advisory remains unresolved; see below. Initial record date: 2026-10-28. This checkpoint does not implement 2B. Full Phase 2 acceptance remains unmet.

## Implementation

- Established `apps/web`, `apps/api`, `packages/contracts`, `infrastructure`, `docs` and `scripts` inside the existing nested Git root.
- Added an installable Python 3.12 FastAPI package, validated environment configuration, health controller/Pydantic contracts, structured errors, bounded correlation IDs and allowlisted JSON request logs. Only public process liveness is available; no business data, identity headers or authentication bypass is implemented.
- Added a React/TypeScript/Vite foundation with Tailwind, a source-managed shadcn-pattern Button, React Router, TanStack Query and Zod. It fetches real liveness, supports retry/error/not-found states and dark/light themes. It has no hardcoded business data or execution behavior.
- Added generated OpenAPI/TypeScript contracts with drift checking independent of Git index state; exact direct dependencies and resolved transitive lockfiles.
- Added digest-pinned API/web Dockerfiles, non-root/read-only application containers, same-origin nginx proxy, and local PostgreSQL Compose with health checks, loopback port bindings and persistent volume. PostgreSQL is intentionally not connected to the API before schema/runtime-role work in 2B.
- Added generated ignored local env configuration, examples, task commands, deferred migration/demo-seed entrypoints, foundation tests and pinned-action GitHub Actions. No application seed data exists yet.
- Preserved original Phase 1 docs and copied identical references into the Git repository; recorded Clerk/role/path/checkpoint-order changes in [Phase 2 plan](PHASE_2_PLAN.md).

## Verification evidence

Executed from the Git root using uv 0.12.23, Python 3.12.15, installed host Node 22.14.0 and npm 10.9.2. Recommended CI/container Node target is 22.22.2; local compatibility does not establish image runtime correctness.

| Check | Result |
|---|---|
| `uv sync --locked --all-packages --all-groups`, `uv lock --check` | Passed; resolved Python dependency set installed with hashes in uv.lock. |
| `make check-api` | Passed: Ruff lint/format, strict mypy, six Pytest/HTTPX foundation tests. |
| `uv build --package orqentra-api` | Passed: source distribution and wheel built. |
| Real subprocess `uvicorn orqentra.main:app` + HTTP GET | Passed: liveness body and correlation header verified; test process stopped afterward. |
| `make setup` twice, file-mode/Git-ignore checks | Passed: generated local env mode 0600, second setup preserves existing file, env excluded from Git candidates. |
| `make compose-check` | Passed using Compose 5.5.1; configuration validation only. |
| `make migrate`, `make seed-demo` | Expected failures: explicit deferred-checkpoint messages, no database changes. |
| Phase 1 copy comparison | Passed: all nine copies byte-identical to parent originals. |
| Source candidate secret-pattern scan | No private-key or Clerk-secret patterns found; generated .env excluded. This is a limited scan, not a comprehensive secret/security audit. |
| `npm ci`, `make check` | Passed: clean locked Node install; Python checks above; Biome lint/format (13 files), TypeScript (web/contracts), five Vitest tests, Vite production build, and non-mutating OpenAPI/TS contract drift check. |
| `make e2e` | Passed: one Chromium test against real FastAPI/Vite processes, liveness, theme switch, unknown route and return home (3.4 seconds total). No health API mock. This is not the future authenticated Forge lifecycle test. |
| Docker image build/start/PostgreSQL smoke | Passed on 2026-10-31: both images built with locked dependencies; API/web/PostgreSQL healthy; authenticated PostgreSQL SELECT 1; built assets/API proxy/security headers verified. Earlier blocked attempts remain recorded below. |
| GitHub Actions hosted runs | Not executed; workflow configured only. |

## Changed files

- Root tooling: `.gitignore`, `.dockerignore`, `.editorconfig`, `.npmrc`, `.nvmrc`, `.python-version`, `.env.example`, `pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`, `biome.json`, `Makefile`, `README.md`.
- API: `apps/api/pyproject.toml`, Dockerfile/env example, `src/orqentra/main.py`, `api/{health,schemas}.py`, `core/{config,errors,logging}.py`, package initializers and `tests/test_foundation.py`.
- Web: package/TypeScript/Vite/Playwright/shadcn configuration, Dockerfile/env example, index HTML, app/bootstrap/styles, UI Button/license, API client/utilities, test setup/component/client tests and foundation E2E.
- Contracts: package/TypeScript configuration, README, exported OpenAPI, generated type declarations and named aliases.
- Infrastructure/scripts: Compose/nginx configuration; local setup, contract export/drift and deferred demo-seed scripts.
- CI/docs: `.github/workflows/ci.yml`, this report, `docs/PHASE_2_PLAN.md`, and nine `docs/phase-1/*.md` references.

Initial npm installation encountered ENOSPC on the nearly full host disk. Task-created abandoned-toolchain/resolved metadata and downloaded archive caches were removed without deleting preexisting cache or project files; a subsequent `npm ci` succeeded from the generated lockfile. Npm reported zero known vulnerabilities in that install audit; this is not a comprehensive security assessment. A disk-full contract export failure also led to atomic OpenAPI replacement and a read-only drift-check workflow; the contract was regenerated and the final check passed. Maintain free space before retrying image/browser setup.

## Remaining gaps and acceptance boundaries

1. Docker runtime verification now passes locally (2026-10-31). Hosted GitHub Actions have not run. A current npm audit reports three moderate findings through one development-only minimatch advisory; remediation is unverified and tracked in [dependency advisory review](DEPENDENCY_ADVISORIES.md). No clean-audit or production security claim is made. PostgreSQL startup does not establish migration correctness.
2. Database entities, Alembic configuration/revisions, tenant constraints/RLS and runtime/migration credentials start in 2B. Installed SQLAlchemy/Alembic/Psycopg do not imply an implemented persistence layer.
3. Clerk configuration/sign-in/JWKS/JWT verification and local organization membership authorization start in 2C. No live identity provider was provisioned or tested in 2A.
4. Forge lifecycle/services/audit, optimistic concurrency, immutable publication, role/tenant tests, business UI and authenticated lifecycle E2E follow 2D–2F. None of the full Phase 2 business/security acceptance criteria are claimed as passed.
5. This is a local foundation, not a production deployment or production-readiness claim. No LLM, agent execution, checkpoint/worker, or external messaging has been added.

## Verification retry — 2026-10-29

The user requested continuation of the remaining 2A runtime checks. Host free space is now approximately 1.0 GiB. `make compose-check` passes again, and `.env` remains excluded from Git. No application or schema changes were made during this retry.

Docker verification is still blocked by Desktop/engine state:

- `docker info --format '{{.ServerVersion}}'` exits 1: cannot connect to the daemon at the configured desktop-linux socket.
- `docker desktop start --timeout 45` reports that Docker Desktop is already running.
- A direct three-second socket probe to `~/.docker/run/docker.sock` gets `ConnectionRefusedError` (errno 61). Desktop backend processes exist, but this does not establish engine health.
- Desktop status and restart commands did not complete; the unresponsive task CLI processes were stopped. The restart command's timeout option did not provide a usable restart result.

No images, containers, database volume, or Docker configuration were deleted/reset. Image builds, container-network checks and PostgreSQL `SELECT 1` remain unverified. Restore a working engine through Docker Desktop on the host, then retry `make up` and the CI smoke commands. More free space may be needed for image/build storage; the current 1 GiB does not establish sufficient image-build capacity. Hosted CI has not run.

This retry stops before 2B. Previous host test/build results above are retained as historical evidence; they were not rerun because no application code changed.

## Container verification completed — 2026-10-31

Disk space was available after the separate laptop cleanup. Docker Desktop still had stalled background processes. The documented CLI `docker desktop stop --force --timeout 15` succeeded; reopening Docker started engine 29.8.2. No reset, image/volume prune, or data deletion was performed. Existing other-project containers remain present.

Executed verification:

| Command/check | Observed result |
|---|---|
| `make compose-check` | Passed. |
| `make up` | Passed; digest-pinned PostgreSQL pulled, Python API and static-web images built, all three services healthy. API image used Python 3.12.15; frontend build used Node 22.22.2. |
| PostgreSQL TCP/password connection + `SELECT 1`, `SHOW server_version` | Passed; returned 1 and 18.6 (Debian 18.6-1.pgdg12+2). No domain tables/migrations created. |
| HTTP requests to `http://127.0.0.1:8080/` and `/api/v1/health` | Passed; expected health JSON and UUID correlation header, no-store API header, static JS/CSS served, frontend CSP/nosniff headers present. |
| Container user / read-only root checks | API UID 10001, web UID 101; both read-only root filesystems and healthy. |
| `E2E_BASE_URL=http://127.0.0.1:8080 make e2e` | One Chromium test passed in 2.6 seconds against built containers: actual API connection, theme switch, unknown route and return home. |
| `npm run lint`, `npm run typecheck`, CI YAML parse | Passed after test configuration changes. |
| `make contracts-check` | Passed; generated contracts match current API. |
| Fresh npm audit | Three moderate findings in a development-only dependency chain; see the linked review above. Not silently fixed or waived. |

Host port 8000 is already used by another project. Added optional `E2E_BASE_URL` to Playwright configuration to test an existing deployment without starting host development servers. Default host mode remains available. README documents container mode; GitHub Actions now runs the same browser smoke against built containers after its HTTP/database checks. Changes for this retry: `apps/web/playwright.config.ts`, `.github/workflows/ci.yml`, `README.md`, this report, and `docs/DEPENDENCY_ADVISORIES.md`.

Orqentra is left running at **http://127.0.0.1:8080**. `make down` stops only this Compose project while retaining its database volume. No schema/auth/Forge implementation or Phase 3 execution was added. Stop before 2B as specified in the Phase 2 brief.

## Recommended Git checkpoint

After reviewing files and outstanding verification limits:

```sh
git add .
git commit -m "chore: establish phase 2A monorepo and local infrastructure"
```

No commit or push has been performed. Stop here before 2B. The next checkpoint is database schema and migrations, beginning with workspace ownership, explicit role/lifecycle policies, tenant constraints and immutable version strategy.
