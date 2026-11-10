# RAG chat with human handoff — 2026-11-09

Workspace Chat already uses pgvector retrieval, OpenAI embeddings and source-checked answers. This addition lets a conversation owner explicitly share one chat with an authorized human support team. It does not create human accounts or make fictional demo profiles able to sign in.

## Customer flow

1. Open Chat and choose a conversation.
2. Select **Request human help**. Read the disclosure and select **Confirm request**. This shares that chat's AI and human history with the organization's current OWNER/ADMIN support team.
3. The state becomes **WAITING**, with AI replies paused. The requester may leave a human message while waiting. The UI does not pretend that someone has joined or promise a response time.
4. When an authorized teammate claims it, the state becomes **HUMAN**. Requester and assigned teammate exchange persistent messages, labeled by role, refreshed through three-second polling.
5. The requester or assigned teammate can select **Return to AI**. Previous human messages remain available to the requester, AI resumes for new questions, and staff access to another person's private chat closes. Human replies are not silently added to approved RAG knowledge or used as factual model evidence.

## Support flow

A separate real development account must have an ACTIVE OWNER/ADMIN membership in the same organization. In Chat, open **Human support inbox**, select a request, inspect the explicitly shared history, and select **Claim conversation**. Only the assigned teammate can send support replies. A requester cannot claim their own request. Another administrator's concurrent claim returns a conflict rather than replacing the assignee. No invitation/email/Slack notification is sent automatically.

The current development database has one actual user. End-to-end interaction between two real signed-in humans has not been observed. Controlled tests use separate cryptographically authenticated test identities in an isolated database; no production credentials or development identity impersonation is used.

## Security and persistence

- Additive migration **0007** preserves migrations 0001–0006 and all existing records. It adds conversation state/assignment and `human_chat_messages`, with composite tenant foreign keys, state/assignment checks, indexed history and forced RLS. There are now **17 forced-RLS domain tables**.
- Access to another person's AI chat is denied before explicit handoff and after return to AI. Regular members cannot inspect the support inbox or claim requests. Every request still requires verified authentication and current organization permission.
- Handoff fences queued/in-flight AI output without deleting questions or previous replies. A late model completion cannot overwrite the handoff cancellation.
- Claims and human-message writes lock the conversation. Sender identity and role come from verified server-side membership, never from the submitted body. Human message intake is idempotent and bounded to 4,000 characters. Up to the latest 100 human messages are displayed; older stored rows are retained.
- Request, claim, reply and resume transitions write sanitized audit events. Human message content, session tokens and provider keys are not logged. Browser text rendering does not execute model/human HTML.
- Polling, bounded inbox/history lists and no external notifications make this a development/pilot handoff feature. Pagination, staffing/availability, assignment recovery, notifications, abuse controls, load/latency measurements and retention/export policies need further release work.

## Actual validation

- **79 isolated PostgreSQL tests passed; 2 explicitly opt-in live model tests skipped** in the ordinary suite. New tests cover privacy before/after sharing, real test-role authorization, concurrent claims, only-assignee replies, idempotency, cross-tenant denial, AI pause/resume and in-flight reply fencing.
- **67 backend unit tests** pass; lint, formatting and type checks pass.
- **53 frontend tests** pass, including explicit sharing consent and honest waiting status. Frontend lint/types/build and **3 CSP tests** pass. Contract generation/check is synchronized.
- Migration backup: ignored `.local/backups/20261109T050338080522Z.dump`. The migration runner verified every preexisting table row count; runtime credentials were preserved and drift check reported no new upgrade operations.

This feature does not pass the outstanding genuine Clerk-invalidation interval. **Checkpoint 2C remains PENDING; production release is not approved.** Deployment results are recorded below.


## Deployment evidence

All four Compose services are healthy after sequential rebuild/deployment. Readiness returns HTTP 200; the served JavaScript SHA-256 matches the tested final build. A read-only query confirms revision 0007, 17 forced-RLS tables and all three existing chats still in AI mode with no human messages fabricated. The deployed anonymous browser suite passes **7 checks**, with **1 expected unconfigured-authentication-only skip**. These checks verify sign-in rendering and anonymous denial, not a real staffed conversation.
