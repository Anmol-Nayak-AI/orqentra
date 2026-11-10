# Phase 2 inspection and dependency-aware plan

## Inspection before changes

The workspace `/Users/adityaansuman/Desktop/Orqentra` contains nine Phase 1 documents and a newly initialized nested Git repository `orqentra/`. The Git repository had only empty apps/packages/infrastructure/docs/scripts directories and standard Git metadata/hooks. There was no implemented functionality, dependency manifest, schema, migration, authentication, tests, application code or applicable AGENTS.md to preserve. Phase 1 requirements, architecture, schema, orchestration, security, threats, acceptance criteria, implementation plan and decisions were read. Reference copies are under [phase-1](phase-1/PRODUCT_REQUIREMENTS.md); originals remain untouched outside the Git root.

The local system Python is 3.9.6, unsuitable for this brief; uv-managed Python 3.12.15 is available and selected. Original host Node is 22.14.0; the target build/CI runtime is Node 22.22.2. Foundation dependency engine ranges also permit the installed 22.14.0 for host verification; current-patch deployment remains recommended. Docker CLI and Compose are installed; daemon responsiveness is a verification prerequisite, not an assumption.

## Scope precedence and recorded architecture updates

The explicit Phase 2 brief updates the prior proposed roadmap:

- API is `apps/api`, not `services/backend`; infrastructure is `infrastructure`, not `infra`. Python remains the application backend; Node is only tooling.
- Clerk React session tokens and verified backend JWTs replace the proposed opaque server-side OIDC session/fixture-provider design. 2A has **no** authentication implementation or bypass. 2C must verify issuer/signature/exp/nbf and configured audience/authorized-party constraints per supported Clerk guidance, map verified subject to local identity, and resolve membership from the database. CORS/CSRF design must follow the actual bearer-token transport; do not reuse the old opaque-cookie model unexamined.
- Organization roles are OWNER/ADMIN/MEMBER/VIEWER. Phase 1 reviewer/operator privileges are future scoped capabilities, not new Phase 2 organization roles. Define the explicit role matrix before 2C/2D.
- Phase 2A is foundation only, followed by schema, Clerk auth, Forge services, UI, integration/security. The earlier proposal of starting an onboarding graph/checkpoint spike immediately is superseded by the new checkpoint order. No LangGraph/worker/execution is added in Phase 2A.
- Preserve the Phase 1 principles: scoped queries plus persistence isolation, immutable published versions, runtime policy checks, audit consistency and no secrets in domain records. Agent workspace ownership vs organization-scoped routes must be decided in 2B: recommended required workspace FK and organization/workspace composite constraints, with workspace selector in creation/query contracts. Do not silently turn workspace agents into global organization records.

These updates follow explicit user instructions; no separate approval is inferred. Unresolved schema/role/Clerk transport details are documented choices for the next checkpoints, not implemented assumptions.

## Missing components and sequence

| Checkpoint | Work and dependencies | Verification before next checkpoint |
|---|---|---|
| 2A (this run only) | Monorepo, exact/locked dependencies, public health API, minimal real health UI, shared contracts, Compose/PostgreSQL, Dockerfiles, local env setup, foundation tests, CI/docs | Host lint/types/tests/build/contracts and health integration; Compose validation; report container daemon limitations |
| 2B | Decide workspace ownership/lifecycle/role boundaries; SQLAlchemy entities, composite tenant FKs, indexes/uniqueness, timestamps/archive/status, immutable publication enforcement, separate runtime/migration roles, Alembic migrations | PostgreSQL empty/prior revision migration checks, FK/RLS role tests, immutability/concurrency constraints; no create_all |
| 2C | Clerk provider/front-end sign-in, secure bounded JWKS handling/JWT verification, local subject association, application membership policy | Valid identity plus invalid signature/issuer/exp/nbf/aud/azp, revoked membership and tenant isolation tests; no trusted identity headers or production bypass |
| 2D | Forge services/repositories/controllers/contracts, validation/model/tool allowlist, draft CAS, immutable publish, archive, search/pagination, transactional audit | Full lifecycle, cross-organization/workspace denial, schema validation, concurrent publish/edit, safe audit records; generated frontend types |
| 2E | Authenticated workspace selection, Command Center, Forge list/create/config/history, org settings, loading/errors, dark/light and accessible responsive UI | Real API integration, RHF/Zod validation, auth/error state tests, meaningful motion only where useful |
| 2F | Lifecycle Playwright with isolated Clerk test users/orgs, security/migration tests, CI and setup rehearsal | Execute all Phase 2 acceptance criteria, publish results/gaps; no production-readiness claim from scaffold alone |

Clerk credentials/test-user provisioning are required before proving live identity integration; do not fabricate a sign-in result. Provider keys and test passwords must stay outside source/CI logs. Phase 3 orchestration, inference, tool execution and external delivery remain excluded.

## Foundation layout

API controllers/contracts are in `api/`, configuration/error/logging mechanics in `core/`. Domain services, repositories, SQLAlchemy models, auth and transactional audit modules will be added when their checkpoint starts, rather than empty speculative implementation layers. `packages/contracts` holds generated OpenAPI/frontend types. `apps/web` owns Vite/React, routing, query cache, UI source and component/browser tests. Infrastructure and scripts contain no tenant business logic.

## Source guidance

Checked during this phase: [Vite requirements](https://vite.dev/guide/), [Clerk React SDK](https://clerk.com/docs/reference/react/overview), [Clerk session claims](https://clerk.com/docs/guides/sessions/session-tokens), [Clerk manual verification](https://clerk.com/docs/guides/sessions/manual-jwt-verification), and [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/). Lockfiles and executed compatibility checks, rather than Phase 1 registry candidate versions, govern this implementation. Clerk provisioning, CLI setup and authentication integration are not performed in 2A.
