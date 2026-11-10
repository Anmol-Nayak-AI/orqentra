# Persistent orchestration and isolated execution boundary — 2026-11-09

Status: local implementation under verification; **commercial acceptance pending**. This increment extends the existing application. It does not enable public deployment, customer charges, outbound business actions or paid sandbox resources.

## LangGraph integration

The existing onboarding worker now uses LangGraph 1.2.20 for retrieve → draft → validate → review. The graph pauses before review; the existing authenticated, revision/artifact-bound approval API remains the authority. Approved action receipts remain **SIMULATED**. No graph node sends a customer message or runs arbitrary code, and graph completion cannot substitute for human authorization.

Migration 0009 adds `workflow_checkpoints` and `workflow_writes`, each with forced tenant RLS, composite tenant/run foreign keys and indexes from uniqueness constraints. Checkpoints are immutable. Runtime credentials cannot delete either table or modify checkpoint history. No vendor setup method creates public checkpoint tables or bypass roles. All reads/writes verify the restricted runtime; writes also verify the current RUNNING task's claim and lease under a row lock.

The graph's storage namespace derives from the immutable agent version and request. A clarification creates a different namespace, preserving previous history. Clients cannot supply a graph thread ID or checkpoint payload. Each run permits at most 128 checkpoints, graph recursion is limited to eight, and stored payloads have a 3 MB database limit. Checkpoint serialization disables pickle and JSON/msgpack class reconstruction. Private graph state is excluded from inherited LangSmith tracing configuration.

The existing bounded worker retry/cost reservation policy remains in force. There are no hidden provider retries inside graph nodes. Successful graph nodes persist synchronously before advancement. Recovery after a committed draft checkpoint can reuse it, preserving its original usage identity instead of counting its tokens twice. The fault test injects a process failure after checkpoint completion and before final task-state commit, then expires the lease and restarts the worker. It verifies one model invocation, one token charge record and AWAITING_REVIEW after recovery. This is synthetic provider output, not a new live OpenAI result.

Important limits: a crash after a provider call but before its checkpoint commits can cause a repeated call. Conservative per-attempt reservations limit exposure; known-usage metering is not complete provider invoice reconciliation. Recovery currently applies to onboarding preparation, not every chat/support workflow or a general multi-agent graph editor. A suspended graph's review is represented by the existing application workflow rather than an exposed LangGraph resume endpoint. Retention, pruning/archival, encrypted managed backups, high-volume recovery/load evidence and multi-worker production acceptance remain open.

## E2B adapter

The provider interface includes a default disabled implementation and an E2B SDK adapter (e2b-code-interpreter 2.11.9). No local `exec`, `eval`, subprocess or Docker-socket fallback exists. `.env.sandbox.example` is a template only; no key file or E2B resource was created. Credentials alone cannot enable execution: a separate server-owned resource-authorization flag and reviewed immutable template ID are required. That flag remains false.

The adapter accepts a code-specific permit containing organization, run, approval ID, SHA-256 and expiry; it rejects changed/expired/oversized input. It requires an audit callback before resource creation and after completion/failure. Future application callers must load and revalidate a persisted, code-specific approval and provide durable audit writes. Existing onboarding-plan approval is **not permission to run code**. No current API/tool issues this permit or invokes the adapter, so execution remains unavailable even if an operator merely installs/configures the SDK.

Requested provider policy: fresh sandbox, no forwarded application keys or mounts, no outbound IPv4/IPv6 traffic, no public ingress, kill-on-timeout (60 seconds), Python-only execution (20-second call limit), bounded request timeouts and 8 KB text output. Before submitting code, the adapter checks returned template, CPU/memory ceilings (2 cores / 1024 MiB), internet flag, network policy and absence of volume mounts. It rejects rich results and requires cleanup confirmation; cleanup uncertainty is a failure. Code, output and API keys are excluded from audit metadata and surfaced error messages.

Fixtures verify default denial, credentials-without-authorization denial, code-hash binding, request parameters, returned-policy mismatch, output limit and cleanup handling. These tests substitute an in-memory SDK transport; **they do not prove real E2B isolation, CPU/memory enforcement, IPv6/DNS/network denial, escape resistance or timeout behavior**. SDK buffering, template hardening, provider failure/cancellation reconciliation and actual network/escape tests require a real approved account. Paid resource creation still requires the user's explicit approval. The adapter is prepared, not production accepted.

## Release acceptance boundary

No real E2B sandbox, Razorpay event delivery, production Clerk instance, managed database or Render deployment has been verified. 2C genuine session-invalidation acceptance and two-real-user support acceptance remain pending. See COMMERCIAL_ROADMAP.md and COMMERCIAL_OPERATIONS.md for the remaining release gates. Local tests and an SDK installation do not make the product production-ready.

## Observed local results

- Backend lint, format and strict type checks passed; **92 unit tests passed** (database tests are run separately).
- Final full disposable-PostgreSQL run: **87 passed, two live-model opt-ins skipped**. A prior full run had one expired-claim recovery failure; its focused rerun and the final full rerun passed. The cause is not established, so it remains an intermittent regression item and production acceptance is blocked. The retained local diagnostic summary is `.local/workflow-regression.txt` (ignored).
- Six sandbox fixture cases passed, including audit-recorder failure preventing resource creation. No real sandbox was started.
- Migration drift check passed at **0009**. All previous table counts were preserved. Runtime inspection finds **23 forced-RLS tables**, one real user, two organizations, two real memberships and two workspaces; new checkpoint/write tables are empty in development because no development task was fabricated.
- The private revision-0008 backup restored into a separate disposable database with all 21 prior forced-RLS tables and recorded counts intact. The existing database was not overwritten or downgraded.
- Sequential local container rebuild completed; API, worker, web and PostgreSQL are healthy. Health/readiness return 200 and anonymous `/me` returns 401.
- pip-audit 2.10.1 reported no known vulnerabilities among 78 host-applicable exported runtime dependencies; `npm audit --omit=dev` reported zero findings. These are dependency-database results, not OS-image or penetration-test clearance. A pinned dependency-audit CI job was added and its YAML parsed locally; remote CI has not run.

Frontend source/flows were unchanged in this backend increment; the previous 53 frontend and four CSP checks remain the baseline. Browser/container smoke results are recorded in the roadmap after completion. No new live Clerk, OpenAI, Razorpay or E2B acceptance result is inferred.

Post-rebuild browser smoke completed: **seven passed, one expected configuration skip**. The skipped test covers absence of authentication configuration and is inapplicable to this configured build. It does not resolve 2C's separate real-session evidence gap.


## Functional integration update — 2026-11-10

The [functional release](FUNCTIONAL_RELEASE_2026_11_10.md) supersedes the earlier unexposed-adapter limitation: persisted independent code approvals, queue/start controls, worker dispatch, audit/reference recording and result states are implemented. Python analysis is a second grounded proposal workflow. The pending-write race was reproduced and corrected through migration 0010; prior migrations were preserved. Real E2B execution is still disabled and unverified, and production acceptance remains pending.

## Provider preparation — 10 November 2026

Sandbox admission now serializes on the tenant organization row and counts committed RUNNING attempts before claiming another queued job. `ORQENTRA_SANDBOX_MAX_CONCURRENT_PER_ORGANIZATION` defaults to one and accepts only 1–2. A controlled two-worker regression observed the second worker leave queued work untouched until the first attempt completed. This is per-tenant admission control, not an account-wide E2B spend limit. Existing 60-second remote lifetime, two-minute claim uncertainty interval, independent approval, quotas and disabled-by-default configuration remain in force. Real multi-organization/global-account concurrency and provider billing/cleanup acceptance require explicit authorization; see PROVIDER_ACCEPTANCE.md.
