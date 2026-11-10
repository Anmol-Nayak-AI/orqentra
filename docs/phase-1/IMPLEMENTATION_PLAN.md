# Implementation plan

Phase 1 delivered design only; this file describes future work. Stop before application scaffolding, dependencies, migrations or deployment in this phase.

## Repository inspection

On 2026-10-28 the workspace `/Users/adityaansuman/Desktop/Orqentra` was empty, including hidden entries other than directory metadata. It had no application, dependency manifests, tests, Git metadata or applicable AGENTS.md. No existing implementation or conventions can be assumed. The attached product brief is the requirements source. Phase 1 creates nine Markdown documents only.

## Proposed monorepo (not created)

```text
apps/
  web/                         # React, TypeScript, Vite, Tailwind, shadcn/ui
    src/{app,features,components,lib}/
    src/components/ui/         # reviewed shadcn source
    tests/
services/
  backend/
    pyproject.toml
    uv.lock
    src/workforce/
      api/                     # FastAPI routers, sessions, dependencies
      modules/
        identity/ tenancy/ agents/ workflows/ onboarding/
        knowledge/ approvals/ integrations/ budgets/ evaluations/ audit/
      orchestration/           # graph registry, state, checkpoint adapter
      workers/                 # worker, outbox, scheduler entrypoints
      infrastructure/          # SQLAlchemy, storage, Redis, telemetry
    alembic/
    tests/{unit,integration,security,faults}/
packages/
  api-client/                  # generated TS client from versioned OpenAPI
infra/
  compose/                     # local profiles, healthchecks, resource limits
  otel/                        # collector redaction and export policy
scripts/                       # reproducible dev/check/restore commands
tests/                         # cross-application end-to-end verification
  e2e/                         # Playwright full browser journeys
  fixtures/                    # synthetic corpus, model responses, adversarial cases
.github/workflows/             # CI, no production secrets on PR jobs
docs/                          # this package plus subsequent ADRs/runbooks
```

Domain modules own repository interfaces and policies. Shared infrastructure contains mechanics, not business rules. One Python lockfile covers API/worker; one frontend/package-manager lockfile covers web and generated client. Avoid a second backend or premature service split.

## Delivery stages and exit gates

| Stage | Deliverable | Exit evidence / dependencies |
|---|---|---|
| 1 — completed design | Nine linked documents; unresolved decisions recorded | Structural/link review only; no app tests |
| 2A — foundations and risk spikes | Lock dependencies, Compose, CI, OIDC fixture, tenant schema/RLS, official Postgres checkpoint adapter | Actual DB role isolation, pool reuse, checkpoint read/write/list/delete tests; stale-worker fence crash spike; resolve D-01/02/04/05 |
| 2B — first vertical slice | Fixture knowledge and model, fixed graph, intake→evidence draft→human approval→simulated receipt, minimal React UI | AC-01–09 and relevant AC-10/11 passing with persisted Postgres, duplicate/concurrency and worker-kill tests; outbound trap shows zero delivery |
| 3 — usable pilot workflow | Agent configuration/version publication, text/PDF ingestion, clarification loops, real approved model, usage UI and evaluations | AC-06/07/10–12/14/15; parser quarantine, source revocation, corpus evaluation, D-03/06 resolved |
| 4 — operational hardening | Restore and migration drills, runbooks, load tests, accessible UI, cost/recovery dashboards | AC-13/15 and declared pilot targets measured; security review with scoped unresolved risks |
| 5 — production connector (separate authorization/scope) | Live provider adapter behind explicit production configuration | D-07 resolved; AC-16, provider idempotency/unknown-outcome recovery; no automatic promotion of demo approvals |

No schedule promise until team, hosting, credentials and spike results are known. Keep each stage reviewable; do not build all stages in one run.

## First vertical slice task order

1. Create minimal pinned Python/React toolchains, local PostgreSQL+pgvector/Redis, API and worker entrypoints and CI. Use synthetic data only. Prepare a fixture identity provider with actual sessions; production must reject fixture auth.
2. Add organization/workspace/membership/grant and scoped run/artifact/action/approval/outbox/audit/budget schema with Alembic. Add restricted-role RLS and direct DB tests before inference.
3. Prove Postgres saver isolation, serialized thread execution, durable replay and fencing against the selected exact package. Implement controlled kill/takeover tests. Stop if framework integration cannot preserve invariants.
4. Implement idempotent intake and durable outbox/scanner; bounded fixed graph using deterministic structured model fixture and pre-ingested document/chunks. Fixture vector dimensions must match the test profile.
5. Persist evidence-linked checklist/draft, approval interrupt and authenticated review endpoint; consume exact approval into unique local simulation receipt. Audit and budget records accompany transitions.
6. Add minimal intake, run detail/evidence, and approval UI. Generate typed client from OpenAPI. Label fixture inference and simulated delivery clearly.
7. Execute happy path, role/scope attacks, 20 concurrent duplicate submissions, crash points, approval edit/revocation, budget exhaustion and no-outbound checks. Record commands/results and limitations; a running UI alone is not an exit gate.

## Verification and CI plan

- Pytest: deterministic domain transition/budget/hash tests; integration tests against real PostgreSQL+pgvector and Redis; actual restricted DB role security tests; subprocess fault injection. SQLite/in-memory saver is insufficient for release recovery/isolation tests.
- Vitest and React Testing Library: validation, status/error rendering, approval bundle changes, simulation labels, accessible controls. Do not mirror implementation with meaningless tests.
- Playwright: two isolated browser users/tenants, submit→evidence→review→simulated receipt, reload/reconnect, denial and stale approval journeys. Start fixture-backed full stack in CI; prohibit external delivery traffic.
- GitHub Actions: lint/typecheck (Python and TS), dependency integrity/secret scans, unit then integration/security/fault suites, web build, browser tests and retained reports. Actions pinned to commit SHA, images to digest, minimum permissions and no live secrets for untrusted PRs. OpenAPI drift fails client generation check.
- Run Alembic upgrade from empty DB and previous supported revision, data/backfill rehearsal and restore drill before release. Never infer migration compatibility from unit tests alone.
- Load and provider evaluation jobs are deliberate release jobs, not flaky public-network PR gates. Report actual p95, failure rates and spend with workload/sample sizes.

## Version and dependency policy

The registry observations below are candidate exact direct pins, not an installed/tested compatible set or a statement of vendor support. They were fetched from public PyPI JSON and npm registry endpoints during this design session on 2026-10-28. Resolve supported interpreter/runtime requirements, advisories and mutual compatibility in Stage 2A; choosing a supported older stable pin is acceptable if documented. No lockfiles or manifests are created in Phase 1.

| Python distribution | Observed version |
|---|---|
| fastapi | 0.162.0 |
| pydantic | 2.14.1 |
| SQLAlchemy | 2.1.6 |
| alembic | 1.20.1 |
| langgraph | 1.2.18 |
| langgraph-checkpoint-postgres | 3.2.0 |
| psycopg | 3.3.6 |
| redis | 8.1.0 |
| pytest | 9.2.0 |
| opentelemetry-sdk | 1.45.1 |

| npm package | Observed version |
|---|---|
| react | 19.3.1 |
| typescript | 7.0.2 |
| vite | 8.3.5 |
| tailwindcss | 4.3.3 |
| @xyflow/react | 12.12.0 |
| vitest | 5.0.5 |
| @playwright/test | 1.64.1 |

Sources: [PyPI JSON API](https://docs.pypi.org/api/json/) (`https://pypi.org/pypi/<distribution>/json`) and [npm registry](https://registry.npmjs.org/) (`/<package>/latest`). Registry results are mutable; lockfile + hashes, not these URLs, become the build authority. Also resolve and pin uvicorn, HTTP client, boto3/S3 client, pgvector Python adapter, embedding/model SDK, OIDC client, parser/scanner, opentelemetry instrumentation/exporter, React DOM, Vite plugin, shadcn dependencies, testing libraries and linters. shadcn components are source-managed: record CLI/source revision and pin imported Radix/other primitives rather than assuming a single runtime package version.

Python, build-only Node, PostgreSQL, pgvector extension, Redis, object storage, OIDC fixture and collector exact versions/image digests remain D-05. PostgreSQL 18 is the currently documented stable line consulted; extension/image compatibility is not yet verified. Redis license/deployment suitability and S3 distribution licensing must be reviewed for commercial use. Do not use `latest`, caret/range direct dependencies or floating action/image tags in implementation. Commit exact direct dependencies plus hash-verified transitive lockfiles; automate reviewed updates and compatibility tests. Pin graph/state/executor versions independently from library versions.

## Material risks and tradeoffs

The longest-risk item is checkpoint tenant isolation and write fencing, followed by business-action crash windows and data-policy/provider choices. Fixed graph + fixture model is the smallest way to verify those controls without conflating model quality with orchestration correctness. Live inference introduces nondeterminism, privacy obligations and unknown billing; live delivery introduces irreversible side effects and provider-specific reconciliation. Both wait for their gates. The shared-database monolith minimizes operations initially but needs strict role/schema policies and leaves privileged-runtime compromise as residual risk.
