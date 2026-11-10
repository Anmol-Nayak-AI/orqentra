# Orqentra product assistant — 2026-11-09

## Why a product question was unanswered

The approved knowledge previously contained a fictional operations policy, but no application user guide. RAG cannot reliably explain undocumented product features. Ten reviewed guides in `docs/knowledge/` now cover overview/navigation, chat, pgvector/RAG ingestion, human handoff, real accounts/invitations/demo profiles, organizations/roles, teammates/tasks/reviews, sign-in/profile/recovery, audit/troubleshooting and current release limits.

These guides describe implemented development behavior rather than planned enterprise promises. They are normal tenant/workspace-scoped knowledge documents, not an authentication bypass or a global private-data index. Organization-specific facts still require approved organization sources; live account state is not inferred from static guides. No promise that every possible question can be answered is made. Unsupported questions should be acknowledged and can be escalated to an authorized human.

## Changes

- Seeded ten product guides into each of the two owned development acceptance workspaces: **20 new documents, all READY**. Original demo handbooks remain ACTIVE/READY, and existing histories are preserved. The guides count toward the current 20-active-document workspace cap.
- Added idempotent `scripts/seed_product_knowledge.py --local`, using restricted runtime writes, reviewed repository Markdown, audited additions and local ownership checks. Re-run adds zero documents. It refuses to silently overwrite changed or revoked sources. It does not automatically provision guides/workers for future organizations.
- Chat retrieval now embeds the current question, avoiding topic pollution from concatenating prior unrelated questions. Prior questions remain available to the answer model as untrusted conversational references, not factual evidence. Very ambiguous follow-ups may need a more explicit question.
- Citation prompt/schema version **rag-chat.v3** constrains each cited chunk ID and quote together using nested `anyOf` branches with enums of exact contiguous source passages. Quotes preserve Unicode and punctuation. Existing server-side exact quote, membership and source-revocation checks remain. This uses [official OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs); schema compliance does not by itself prove that every generated claim is supported.
- Chat copy/examples now explicitly mention Orqentra product questions. Old lack-of-evidence answers are preserved; submit a new question to use the new knowledge.

## Actual verification

- **68 backend unit tests**, **80 isolated PostgreSQL tests** and **53 frontend tests** pass, plus **3 CSP tests**. The ordinary database suite skips its **2 explicit opt-in provider tests**. Lint/format/types/build pass. New regressions cover topic changes and source-bound exact Unicode citation choices.
- A separate bounded evaluation made six real embedding/retrieval/OpenAI calls against the approved development workspace, without creating chat messages or identities. Questions covered chat usage, pgvector/RAG, real invitations versus demo users, human intervention, teammate tasks/reviews, and unpublished pricing/SLA.
- Initial evaluation: **5/6 passed**; the vector explanation altered a quote and failed validation. This prompted the stricter source/quote schema rather than relaxing validation. Re-run: **6/6 passed** with nonempty exact citations, the expected guide cited and no insufficient-evidence flag. The private report is `.local/product-assistant-evaluation.json`.
- Observed chat answer explained organization → Chat → workspace → existing/New chat → type question → Send → inspect Sources. Observed pricing answer stated that this development build has no published pricing or guaranteed support SLA.
- These six smoke cases are not exhaustive coverage, a hallucination-rate measurement, a staffed support test or a new live Clerk acceptance result. The existing **2C pending** and production-release limits remain unchanged.

## Reproduce

```sh
uv run --locked --package orqentra-api python scripts/seed_product_knowledge.py --local
uv run --locked --package orqentra-api python scripts/evaluate_product_knowledge.py --local --live
```

The evaluation uses the existing ignored backend provider key and makes bounded billable development calls. Neither script prints keys or session tokens. The worker's existing explicit organization allowlist remains in force.


## Proxy recovery found during deployment

API/worker replacement exposed an existing web proxy issue: static startup DNS retained the previous API address, causing HTTP 502. The first browser regression run reported 5 passes, 2 failures and 1 expected skip; that is not counted as a passing deployment. Restarting web restored routing. The proxy configuration now uses Docker's embedded resolver with a five-second validity and a fixed backend hostname variable, following [NGINX proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass) and [resolver](https://nginx.org/en/docs/http/ngx_http_core_module.html#resolver). This avoids pinning the API address for the lifetime of the web process. Authentication and CSP policies are unchanged. Final verification follows below.


## Final deployed verification

All Compose services are healthy and readiness returns HTTP 200. Served JavaScript matches the tested production build; installed worker provider/retrieval sources match the tested local source by SHA-256. The proxy recovery experiment replaced API/worker containers, confirmed the API address actually changed and the web container remained unchanged, and observed successful readiness routing without a web restart. The final deployed browser suite passes **7 tests with 1 expected unconfigured-auth-only skip**. This supersedes the earlier two proxy-related failures. No existing development identities, memberships, histories or volumes were reset.
