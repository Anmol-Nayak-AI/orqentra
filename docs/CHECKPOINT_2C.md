# Checkpoint 2C — current acceptance gate

**Final status: PENDING — not accepted. The user clarified that organizations were shown after signing back in, which is expected persistence and does not establish a live sign-out failure. Signed-out route denial is now supported by an explicit human report; genuine session-invalidation recovery still requires evidence. The user authorized subsequent feature development on 2026-11-04 while keeping 2C pending.**

This reconciled status supersedes the historical pending/completed statements below. Evidence is limited to actual automated results, read-only database/server inspection, and explicitly labeled human reports/screenshots.

| Mandatory criterion | Current evidence | Gate status |
| --- | --- | --- |
| Real development Clerk authentication reaches FastAPI | User sign-in/onboarding screenshots; protected creation POST 201 and retrieval GET 200 in structured API logs | Verified |
| Exactly one local user for verified identity | Repeated read-only checks: one active Clerk-linked user, zero duplicate external subjects | Verified current state |
| Repeated sign-in retains the same local user | User clarifies sign-out followed by sign-in; read-only check finds one user, no duplicates, and an identity fingerprint identical to the saved baseline | Verified by human report and database comparison; screenshot is historical, not a new post-fix capture |
| Organization creation and creator ownership | A and B are ACTIVE; same local user has ACTIVE OWNER membership in each, with one default workspace and creation audit per organization | Verified |
| Authenticated organization retrieval/authorization | Protected organization/workspace GET 200; RBAC restrictions covered by 56 real PostgreSQL integration tests using signed SDK-verified sessions | Verified for observed live operations and automated denial cases |
| Authorized organization switching | Human A → B → A reports and screenshots show correct labels/workspaces; separate RLS/pool tests check isolation | Verified within this scope |
| Profile management integration | Real development Clerk Manage account/Profile/Security modal shown in screenshot; opening-panel check passed | Verified panel access; profile saves not tested and not required by the agreed non-destructive check |
| Live sign-out and subsequent protected-route denial | User explicitly reports sign-out followed by direct `/app` navigation showing sign-in with no organization cards, before reauthentication; independent anonymous API probe returns 401 | Verified human-operated route denial plus independent API denial; not instant JWT-revocation evidence |
| Live session-expiration recovery | Expired JWT rejection and UI recovery covered by automated tests; real user expiry-to-recovery transition not observed | **Pending live recovery observation** |
| PostgreSQL RLS / regressions / migration preservation | 59 API + 59 real DB + 33 frontend + 3 CSP passed; five configured browser checks passed; migration checks passed | Verified; no unnecessary rerun in this review |

## Skipped browser test disposition

The skipped test `unconfigured authentication keeps protected pages closed` is guarded by `E2E_EXPECT_UNCONFIGURED=1`. Its absence condition does not apply to the configured development deployment; it is not an outstanding real-user criterion and did not independently block that deployment's acceptance.

To remove the coverage uncertainty, the exact existing test was run separately against a temporary Vite server on 127.0.0.1:5175 with an empty publishable-key environment override. Command: `E2E_BASE_URL=http://127.0.0.1:5175 E2E_EXPECT_UNCONFIGURED=1 npm run test:e2e --workspace @orqentra/web -- --grep 'unconfigured authentication'`. **Result: 1 passed.** Protected `/app` displayed the missing-configuration state and access-restricted message. No saved environment file or Docker service was changed. The temporary server was stopped afterward. Together, the five configured checks and this separate run cover all six browser cases; this is not represented as six passes in one configured run.

## Only remaining mandatory live work

**Test A is complete within its recorded scope:** the user reported direct `/app` navigation reaching sign-in with no organization cards while still signed out; an independent anonymous API request returned 401. See the latest Test A entry below.

**Test B remains:** sign in with the same development account, invalidate only its current Orqentra browser device/session from the Clerk development dashboard, wait past the accepted JWT lifetime, and verify the existing tab/protected navigation requires recovery without stale private cards. Reauthenticate with the same account and compare server outcomes plus the saved local identity fingerprint. Manually opening `/session-expired` is not genuine expiry evidence.

Browser access remains unavailable, so the provider invalidation requires the authorized human action. The configured maximum accepted token lifetime is 300 seconds; wait six minutes after revocation to avoid treating the known already-issued-token validity window as a failure. Never revoke another user's device or all devices, and do not delete users or alter global session settings. No tokens are requested or captured. Final acceptance remains PENDING; Downstream development is now authorized; 2C acceptance remains pending.

## Historical evidence log

The following sections preserve earlier observations and test counts chronologically. Use the current gate above for the final status.

# Checkpoint 2C — identity and organizations

Implemented Clerk-backed browser authentication and signed bearer verification, JIT local users, local organization ownership/membership authorization, protected pages, role management and transactional audit events. Public health and the original foundation remain available. No AI execution or later checkpoint work has started.

Migration 0003 adds identity boundary functions, a self-user read policy, owner protection and constrained role-change audit metadata. Migrations 0001 and 0002 are retained. Forward migration preserves domain records; no development downgrade or Docker volume reset is used.

See [authentication setup](AUTHENTICATION.md), [authorization rules](AUTHORIZATION.md), and [migration operations](MIGRATION_GUIDE.md). Templates contain no live keys. The existing Clerk application is now configured locally. Live account-flow verification remains pending; this checkpoint must not be marked fully accepted until those checks pass.

Automated validation includes API/static checks, frontend types/lint/build/unit tests, actual SDK signature validation, disposable PostgreSQL authorization/RLS/migration tests, generated-contract drift checks, CSP generation tests and browser smoke checks. Test signing keys are confined to test helpers. Live Clerk identity-provider flows are not covered by mocked frontend unit tests.

## Local validation — 2026-11-03

- 51 API/unit tests passed; lint, formatting and Python type checks passed.
- 56 real PostgreSQL tests passed through the disposable-database runner (separately from the plain suite's explicit database skips).
- 12 frontend unit tests passed; frontend lint/types and production build passed.
- Three CSP generation tests passed; OpenAPI/TypeScript contracts match source.
- Three Chromium/container smoke tests passed, including spoofed identity-header denial and the unconfigured protected-page state.
- Development migration reached 0003 with a private pre-upgrade backup and preserved row counts; schema drift check passed. Original 0001/0002 checksums are unchanged.
- Rebuilt web, API and PostgreSQL containers are healthy at http://127.0.0.1:8080. No database volume was removed.

Live Clerk registration/login/logout/profile checks remain pending. Known tooling dependency advisories remain tracked in [DEPENDENCY_ADVISORIES.md](DEPENDENCY_ADVISORIES.md); the frontend build also reports a non-fatal bundle-size warning.

## Existing Clerk application configured — 2026-11-03

Validated saved configuration without printing its values: the publishable key matches the issuer and the RSA public key matches that issuer's live JWKS. Rebuilt the Docker stack; all three services are healthy. A clean Chromium browser rendered the actual Clerk sign-in component with inputs and no console errors. The configured API rejected an invalid bearer token with 401. No account was created or signed in during this check. The user must complete an actual sign-in before authenticated account/organization flows can be verified.

## Final acceptance attempt — 2026-11-03, 12:52 IST

**Decision: PENDING — CHECKPOINT 2C IS NOT YET ACCEPTED.** Live authenticated account scenarios require human participation and evidence. No Checkpoint 2D work has been started.

### Regression results from this attempt

`make check test-db` completed successfully: 51 API/unit tests passed, 12 frontend tests passed, three CSP tests passed, and 56 real PostgreSQL integration tests passed in generated disposable databases. The 56 database tests are explicitly skipped by the plain API invocation and then executed successfully by `make test-db`; they are not counted as passing from skips. Python lint/format/types, frontend lint/types/production build, and contract drift checks passed. The build retains its non-fatal bundle-size warning. Existing dependency advisories remain documented separately.

`make migration-check` reported no new upgrade operations. Original 0001/0002 migration checksums match the saved baseline. Direct HTTP probes against the running Docker deployment returned health 200 and missing-token, invalid-token, and spoofed-identity-header requests to `/api/v1/me` each returned 401.

### Development database baseline (read-only inspection)

- Migration revision: 0003.
- Local users: 0; users with external subject: 0; duplicate external subjects: 0.
- Organizations: 0; active OWNER memberships: 0.
- Eight domain tables have both enabled and forced RLS.
- Runtime role remains NOSUPERUSER and NOBYPASSRLS.

This empty baseline does **not** demonstrate successful live provisioning. No development records, tenant data or Docker volumes were reset or deleted during this attempt.

### Mandatory evidence tracker

| Required scenario | Evidence from this attempt | Status |
| --- | --- | --- |
| Real Clerk authentication | Existing configured sign-in form was observed in the previous check; no signed-in session observed in this attempt | Pending human sign-in |
| Valid session reaches FastAPI | Invalid/missing sessions return 401; a valid live request has not yet been observed | Pending |
| Exactly one user for verified subject | Baseline has zero users; actual first-login subject mapping remains unobserved | Pending |
| Repeated sign-in without duplicate user | Automated repeated/concurrent provisioning tests pass; live repetition remains unobserved | Pending live check |
| Creator receives OWNER | Atomic bootstrap integration test passes; no live organization exists at baseline | Pending live check |
| Organization switching changes scope | Database authorization and pooled-connection isolation tests pass; UI switching remains unobserved | Pending live check |
| Clerk profile management | No profile interaction observed | Pending |
| Sign-out and unauthorized rejection | Anonymous API rejection observed; authenticated-to-signed-out transition remains unobserved | Pending live check |
| PostgreSQL cross-tenant RLS | Restricted-role cross-tenant read/write and pool isolation integration tests passed on disposable tenants; development RLS flags confirmed | Automated database verification passed |
| 2A/2B/2C regressions | API, frontend, contract, CSP and real database suites passed; interactive browser regression could not be rerun through the available connection | Browser portion pending |

### Browser access and outstanding actions

The browser runtime reported no available browser, and its discovery list was empty. No alternate browser automation or authentication bypass was used to work around that limitation. The user was asked to sign in interactively at `http://127.0.0.1:8080/sign-in` with an approved development test account and report whether Organizations loads. Passwords, verification codes and session tokens must not be shared. Direct agent observation of profile, organization switching and sign-out will require a connected browser; any human-reported outcome must be labeled as such rather than presented as direct observation.

After sign-in, inspect the local subject mapping and membership records read-only, perform repeat-login verification, use clearly named development acceptance organizations for creation/switching tests, inspect profile management, then sign out and verify access rejection. Do not mark accepted until all mandatory live evidence is recorded. No production credentials, RLS disabling or changes to another tenant's data are authorized.

### Human sign-in report and follow-up inspection

The user reported: “Signed in; Organizations page loaded.” This is human-reported browser evidence, not direct agent observation. A subsequent read-only database inspection still found zero local users, zero subjects, zero organizations and zero OWNER memberships. Structured API request logs contained no organization-list requests since the current container started; the observed non-health requests were the expected `/me` 401 probes. Consequently, a valid live session reaching FastAPI and JIT provisioning cannot yet be marked passed. The user has been asked to refresh the exact Docker `/app` URL and provide its visible result or request ID, without sharing credentials or tokens. Acceptance remains pending while this discrepancy is investigated.

### Live provisioning evidence and routing correction — 2026-11-03

The user's supplied screenshots show a Clerk-signed-in account on the foundation homepage and, subsequently, the real organization-selection empty state. A follow-up read-only development database inspection found exactly **one local user**, exactly **one active Clerk-linked user**, and **zero duplicate external subjects**. This supersedes the earlier zero-user observation: the initial screenshot had shown the public homepage, whose health request does not provision a local user. Visiting `/app` triggered the verified identity boundary. Live repeated sign-ins, organization creation/switching, profile editing and sign-out remain pending; no later acceptance scenario is inferred from this single-user count.

The screenshots also exposed a confusing entry flow and disconnected account navigation. The UI now separates the public welcome/authentication layout from a nested protected application shell. Signed-in root and sign-in/sign-up entries redirect to `/app`; diagnostics remain explicitly available at `/status`. Organization pages share a sidebar, header, member/settings routes and responsive spacing. Organization onboarding has a clear empty state and a contained creation form. Session-expiry recovery signs out the stale provider session before returning to sign-in, preventing a signed-in redirect loop.

Frontend regression coverage now has 15 passing tests, including signed-in entry redirects and expired-session recovery. Frontend lint/types/production build and the three CSP tests passed. The existing browser smoke script now targets `/status` for public liveness, reflecting the new entry-route behavior. Interactive visual and signed-in browser regression verification remains pending because the browser connection is unavailable. Backend authorization and RLS were not relaxed or changed by this UI correction. Final acceptance remains pending.

Deployment note for the UI correction: the Docker build stalled during the web build stage and the Docker management API stopped responding, although the existing web health endpoint continued returning 200. Only the stalled build/status clients were interrupted; no engine restart, container stop, volume removal or database reset was performed. The corrected source passes local checks, but the running UI must not be reported as updated until Docker management access is restored and `make up` completes. Post-deployment browser verification remains pending.

Deployment recovery: after cancelling the stalled build clients, Docker management access recovered without restarting the engine. The web Docker build now bounds Node heap to 512 MB while retaining TypeScript checking; the same bounded build passed locally and the subsequent Docker build completed successfully. Only the web container needed replacement; API and PostgreSQL remained running. All three services report healthy. HTTP deep-link checks passed for `/`, `/app`, `/app/create-organization`, `/sign-in` and `/status`; the served JavaScript bundle's SHA-256 matches the tested local production output. Anonymous `/api/v1/me` still returns 401. These are deployment/routing checks, not a substitute for interactive visual or live account acceptance.

## Final acceptance recheck after successful `/app` onboarding

**Decision remains PENDING; CHECKPOINT 2C is not yet accepted.**

The user reports real development Clerk sign-in and successful authenticated `/app` onboarding. Read-only development inspection confirms **one user**, **one active user linked to a Clerk subject**, and **zero duplicate external subjects**. Combined with the previously observed protected organization-list empty state, this supports successful live identity provisioning. This proves the current single-record state; an explicitly observed sign-out/sign-in repetition is still needed to verify the live repeated-login scenario.

The same inspection found **zero organizations and zero organization.created audit events**. Therefore the requested “newly created organization” and its OWNER membership cannot be verified in this database yet. No organization records were created with privileged SQL to simulate authenticated API success. The user has been asked to create `2C Acceptance A` / `2c-acceptance-a` through the authenticated app so creation, membership and audit evidence can be checked without bypassing authentication.

The mandatory regression command `make check test-db migration-check` passed: **51 API/unit**, **56 real PostgreSQL integration**, **15 frontend unit**, and **3 CSP generation tests**. Lint, formatting, Python/TypeScript checks, production build, OpenAPI contract drift and Alembic schema drift checks passed. The plain API run's 56 database skips are covered by the separate successful real-database invocation. RBAC, cross-tenant RLS, owner protection, pooled-connection context reset, identity provisioning and migrations are exercised by that integration suite on disposable test databases, preserving development data and Docker volumes.

Live organization creation/retrieval, authorized switching between two organizations, profile management, expired-session behavior and authenticated-to-signed-out access rejection remain unverified. Anonymous rejection and automated session-recovery tests do not establish live sign-out invalidation. The backend validates short-lived JWTs locally: a previously captured token may remain valid until its expiration after provider sign-out; this is the documented revocation limitation, not an instant-revocation guarantee. No tokens were captured or printed. Browser discovery still returns an empty list, so interactive steps currently require human participation. No production credentials or Checkpoint 2D work are used.

Browser regression rerun: `E2E_BASE_URL=http://127.0.0.1:8080 make e2e` completed with **2 passed, 1 skipped**. Public status/navigation and anonymous identity-header rejection passed in a clean Chromium test context. The explicitly unconfigured-deployment test was skipped because this deployment is configured; it is not counted as a pass. This isolated regression run does not access the user's signed-in browser session and does not prove live account scenarios.

### Live organization A verified

After the user reported “Created; Command Center loaded,” read-only inspection confirmed organization `2c-acceptance-a` (`0cc68aaf-e894-4180-a0c6-643e89265c8c`) is ACTIVE with exactly one ACTIVE OWNER membership linked to the active Clerk-provisioned local user, one ACTIVE default workspace, and one organization.created audit attributed to that owner. The local user count remains one with zero duplicate external subjects.

Structured API logs independently show creation POST returning **201** (correlation `3794d3c4-7fe5-4cd6-a9f1-3f1f94f29915`), organization retrieval GET returning **200** (`3efbc6d9-a674-464e-95df-1c14ea323afd`), and workspace retrieval GET returning **200** (`3b88a2cc-e2b7-4016-91a5-ceb8e99900fe`). Because these endpoints require the verified identity dependency, these outcomes establish a live authenticated request reaching FastAPI and successful organization creation/retrieval. Browser rendering is supported by the user's report; no session token was obtained or logged by the acceptance inspection.

This supersedes the earlier zero-organization baseline. Live creation, retrieval and creator OWNER membership now have evidence. Two-organization switching, profile management, explicit repeat-login, expiry and sign-out transition checks remain pending; final acceptance is still PENDING.

### Two-organization UI evidence — screenshots at 13:39 IST

User-supplied screenshots show separate Command Centers for `2C Acceptance A · OWNER` and `2C Acceptance B · OWNER`, each displaying a Default workspace and the expected contextual navigation. Read-only database inspection confirms both organizations are ACTIVE, each has one ACTIVE OWNER membership, one ACTIVE default workspace and one owner-attributed creation audit. The same single local user owns both; the local users table still contains one user.

These screenshots support successful navigation between the two authorized organizations with the correct organization label rendered. They do not alone demonstrate the requested A → B → A sequence or prove absence of all tenant-data leakage: both workspaces have identical names, and the screenshots contain no distinct workspace identifiers. The previously passing restricted-role RLS and pool-reuse integration tests provide separate evidence of tenant isolation. Do not characterize the screenshots as an adversarial cross-tenant test. Live profile, expiry recovery, sign-out/re-login and explicit return-to-A verification remain pending. Acceptance remains PENDING.

### Return-to-A navigation confirmed — screenshot at 13:46 IST

The user explicitly reports switching from B back to A and supplies a screenshot showing `2C Acceptance A · OWNER`, its Command Center, Default workspace and contextual navigation. Together with the earlier A/B screenshots, this completes the human-operated A → B → A navigation scenario with the correct organization label after each selection. This supersedes the earlier pending return-to-A item. It demonstrates authorized UI switching; adversarial cross-tenant isolation remains supported separately by the restricted-role PostgreSQL regression tests, rather than inferred solely from identical workspace labels. Profile management, explicit live session-expiration recovery, sign-out and repeat sign-in remain pending. Final acceptance remains PENDING.

### Clerk profile management panel observed — 13:47 IST

The user's screenshot shows the real Clerk Account modal in Development mode, with Profile details, an Update profile action, and Profile/Security navigation. This confirms that Orqentra's avatar/Manage account integration opens the provider's account-management UI. Personal profile values from the screenshot are intentionally not transcribed into this report. No profile mutation or successful save was performed or claimed. The agreed non-destructive profile-panel opening check has passed; editing/persistence remains untested. Live sign-out/access rejection, repeat sign-in uniqueness and explicit session-expiration recovery remain pending. Acceptance remains PENDING.

### Sign-out evidence review — screenshots at 13:50 IST

The screenshot of `/api/v1/me` displays the API's generic sanitized error envelope with correlation `6400fe1c-418f-4309-8222-4cb95fbd7e57`. Matching structured server logs confirm **HTTP 401** at 08:19:55 UTC. The earlier instruction predicting literal “Sign in required” text was inaccurate: global error handling deliberately returns a generic message. This is expected anonymous bearer-API rejection, not a server failure; direct address-bar API navigation supplies no bearer token even when Clerk browser cookies exist.

The final screenshot shows `/app` rendering the two organizations. It does not establish whether this was after reauthentication or while supposedly signed out. The user was asked to clarify the sequence before marking sign-out protection or repeat-login passed. Read-only inspection still shows one local user and zero duplicate subjects. No signed-out route protection failure is inferred or dismissed without that clarification. Final acceptance remains PENDING.

## UI reliability review after request to stop manual retesting

The user requested that the agent finish the UI review without repeatedly asking them to test. No further interactive checklist was issued. This request does not waive evidence requirements or convert pending live authentication scenarios into passes.

Implemented and tested the following corrections:

- Sign-out has pending/failure handling. Protected content is hidden during the operation; the departing user's query requests are cancelled and cached private results removed. Failed provider sign-out presents a recoverable error rather than silently claiming success. Account-change cleanup also cancels old-user requests.
- Thrown or missing SDK token retrieval routes to session recovery without sending an unauthenticated application request. Session-recovery navigation replaces the previous history entry.
- Failed organization/workspace reads offer explicit retry. Authentication/authorization errors are excluded from automatic query retries.
- Organization creation blocks duplicate pending submissions, disables editable fields during submission and provides cancellation navigation. Inputs remain available after a failed creation attempt.
- Membership removal requires an explicit confirmation step before any mutation request is sent.
- Settings show labeled organization details; workspace lists have an explicit empty state. Mobile public headers can wrap, form controls have visible keyboard focus, and the duplicate public main landmark was removed.
- Public mobile/desktop screenshots were reviewed; a wrapped numeric feature label was corrected with a fixed-width, nonshrinking label.

Validation: **21 frontend tests passed**, including pending/failed sign-out, private-cache scope, token exceptions, read retry and removal confirmation. Frontend lint/types/build and **3 CSP tests** passed. Production-container browser regression completed with **5 passed, 1 skipped**: public status/theme/navigation, anonymous API denial, 375px/1280px public layouts without horizontal overflow, signup navigation and fresh-browser protected-route denial. The skipped case is specifically for an unconfigured deployment and is not a pass. Initial new browser tests hit the 5-second assertion limit while the live Clerk SDK was still loading; assertions now wait up to 20 seconds for identity-provider initialization, and the subsequent run passed. There is no authentication bypass or mocked live provider in these browser checks; SDK mocks remain confined to frontend unit tests.

The existing backend/database regression result remains 51 API/unit and 56 real PostgreSQL tests passed; backend authorization/schema were unchanged by this review. The global API error envelope remains deliberately generic; anonymous API denial is determined by HTTP 401, not assumed response wording. Existing data and Docker volumes are preserved.

**Acceptance remains PENDING.** Direct control of the user's browser session is still unavailable, the earlier sign-out-versus-re-login screenshot sequence remains ambiguous, and live expiry recovery has not been observed. Automated browser denial and SDK-mocked sign-out tests are separate evidence, not claims of a completed live sign-out or immediate JWT revocation. No zero-defect guarantee or Checkpoint 2D implementation is implied.


## Live sign-out failure and remediation

The user explicitly answered “Protected content remained after sign-out” to the prescribed sign-out → direct `/app` navigation check. This fails that mandatory live criterion and supersedes the earlier ambiguous screenshot sequence. No successful sign-out, repeat-login or final acceptance is claimed.

Code review identified a reproducible race: `useEndSession` previously reset its local closing flag in `finally`, regardless of whether Clerk's React auth state had actually changed. A fulfilled signOut promise with stale isSignedIn=true could therefore release the guard and allow public-entry navigation to redirect back into the app. Earlier tests used a placeholder home route and did not cover the real root redirect; that coverage gap has been corrected.

The correction retains a per-session logout barrier across SPA navigation and refresh, keeps protected content and token-bearing API requests blocked, and releases the barrier only after the provider reports signed out or a different session. The barrier stores only a session identifier in sessionStorage, never a JWT, password or key. This is an additional local denial control, not a replacement for Clerk/FastAPI verification and not proof of server-side instant revocation. Provider logout failure keeps the workspace locked and offers retry. Page restoration resynchronizes the local barrier. A genuine new sign-in can restore access.

New regression cases reproduce a resolved logout promise with stale auth state at the real root route, persistence across provider remount with the same session, admission of a different session, and clearing after provider-confirmed sign-out. Frontend tests now total 24 passing cases before the final restoration-hook verification. Live confirmation of the remediated behavior and actual expiry recovery remain outstanding. Existing development records, Docker volumes and migrations are untouched.

Deployment and verification: the corrected web image is deployed; web/API/PostgreSQL are healthy, and the served bundle matches the tested production output. All **24 frontend tests**, **3 CSP tests**, lint, types and production build pass. The focused deployed-browser checks for anonymous protected-route/API denial passed (**2 tests**). Unchanged organization/profile checks were not repeated. The remaining live sign-out test must confirm provider termination as well as denial of private content; a “Workspace locked” screen is safe denial while termination is unconfirmed, not proof that Clerk has ended the session. Final status is NOT ACCEPTED pending the live transition and expiry-recovery evidence.


## Clarification of the organization-list screenshot

The user clarified: “after signing out then signing in I get the previous created organisations.” The supplied image is the previously supplied 13:50:18 screenshot; it is not new post-fix browser evidence. Existing organizations appearing after reauthentication is expected data persistence, not evidence that protected content was accessible while signed out. The earlier classification of that image/report as a confirmed live sign-out failure is superseded by this clarification. The independently reproduced stale-SDK-state race and its regression fix remain valid code/test findings; they are not proof that the user's actual browser encountered that race.

Read-only comparison now confirms one local user, zero duplicate external subjects, the exact same local-user/subject fingerprint as the saved acceptance baseline, and both ACTIVE acceptance organizations preserved. Together with the user's explicit reauthentication report this supports repeat-login uniqueness. No raw subject or session token was printed. The signed-out interval itself remains unobserved: the API address-bar 401 is anonymous bearer rejection, not proof of route/session termination. The remaining live gates are signed-out protected-route denial and actual session-expiration recovery. Final status remains PENDING, not ACCEPTED; no 2D work is started.


## Test B — controlled genuine session-invalidation recovery (in progress)

The user authorized a controlled development test of an expired or invalidated session. No Clerk management connector or connected browser is available (browser discovery returned no entries), so remote revocation of the approved account's session requires a human action in the existing development Clerk dashboard. No secret key is requested or introduced. No live success is claimed yet.

Review found that the prior API 401 branch navigated to recovery without immediately removing cached private results while SDK auth could remain stale. Corrected 401/missing-token/token-exception handling now marks the session invalid, cancels the user's private query requests, removes those cached results, and routes to recovery; guards and API calls stay blocked for that session until confirmed termination/new authentication. Public health cache remains separate.

Focused automated validation:

- New real-PostgreSQL HTTP case: valid ephemeral RSA-signed test session → expired correctly signed token rejected with 401 → fresh token for the same subject returns the exact same user; exactly one local identity remains. **1 passed, 56 deselected** with `scripts/test_database.py -k expired_session_recovers`. The test suite now contains 57 database cases, but this is not a claim that all 57 were rerun. Test credentials/signing keys are isolated fixtures; this does not establish genuine Clerk-session revocation.
- **27 frontend tests passed**, including three new cases for API 401, missing token and token-retrieval exception. They verify private-cache removal, preserved public cache, recovery display and blocked return to stale protected content. These use SDK mocks and are not labeled live provider evidence.
- Frontend lint/types/production build, Python lint/format, and **3 CSP tests passed**.

A private ignored Test B baseline records one local user and an identity fingerprint for comparison after recovery, plus the server-log start time. Values of Clerk subjects/tokens/keys are not printed. The configured maximum accepted JWT lifetime is 300 seconds. Revocation prevents further valid refreshes, but an already issued JWT can remain locally verifiable until expiry. The controlled test should wait six minutes after revoking only the approved account's current device/session, then trigger a protected action and sign back in with the same account. Record the actual UI outcome, matching request statuses/correlation IDs if a request reached FastAPI, and the post-login identity comparison. If SDK denial prevents a request, explicitly record that rather than inventing an expired-bearer HTTP response.

Provider procedure reference: [Clerk session options — ending existing sessions](https://clerk.com/docs/guides/secure/session-options), [revokeSession](https://clerk.com/docs/reference/backend/sessions/revoke-session). Revoke only the identified development test device; do not revoke all devices, delete users or change global lifetime settings. Data, Docker volumes and prior migrations remain preserved. **Test B and final acceptance remain PENDING.**

Test B browser-operation attempt: the user asked the agent to open the tab and perform the invalidation test. Browser discovery again returned an empty list. Integration discovery did not expose a usable local signed-in browser connection; a cloud browser is not a replacement for the existing localhost app and its signed-in device. No device was revoked, no signed-in browser was operated, and no genuine Test B result is claimed. Automated results remain valid; live invalidation/recovery and acceptance remain pending local browser access or the previously described human action.


## Enterprise foundation hardening and product positioning

The user selected **Orqentra — Your workforce, intelligently orchestrated.** The public heading and page metadata now use that positioning. [Enterprise readiness](ENTERPRISE_READINESS.md) documents the general AI teammate platform direction, onboarding-first use case, implemented controls and outstanding enterprise release requirements. Video title/author metadata were verified; unavailable transcript contents were not treated as requirements. This positioning does not claim that model execution, connectors or orchestration are implemented.

Implemented within foundation scope: configurable bounded request buffering (64 KiB default, including chunked requests), matching ingress limit and idle body timeout, a local auth/database readiness endpoint, production configuration guards (auth/runtime DB required, HTTPS frontend origins, no API migration credentials), bounded DB connection/pool waits, and engine disposal at application shutdown. No domain table migration or later-checkpoint execution capability was added.

Validation: **59 API/unit tests**, **59 real PostgreSQL integration tests**, **27 frontend tests**, and **3 CSP tests** passed. Backend/frontend lint and types, production build, contract drift and schema drift checks passed. Original migrations 0001/0002 retain their saved SHA-256 checksums. The rebuilt local containers are healthy; deployed `/api/v1/health` returned 200, `/api/v1/ready` returned 200 with a safe ready status, and an oversized ingress request returned 413 without a business mutation. The readiness endpoint does not validate the live IdP or satisfy the pending genuine-session recovery gate. No data or Docker volumes were reset. Final 2C acceptance remains PENDING; 2D has not started.

Post-deployment branded browser regression: **5 passed, 1 skipped** on the configured app (desktop/mobile navigation, status/theme, anonymous API rejection and protected-route denial). The skipped unconfigured-app case remains covered by its earlier separate successful run; it is not counted as a configured pass. The updated mobile screenshot was inspected for tagline wrapping and horizontal overflow.


## Authentication presentation redesign

The user identified the isolated default authentication card and redundant public header as visually unfinished. Authentication routes now use a dedicated responsive split layout: Orqentra wordmark/tagline and a decorative organization/workspace/access illustration on desktop, plus a focused provider form with consistent theme colors, typography, spacing and recovery routes. Mobile collapses the decorative panel; duplicate sign-in navigation is removed. Clerk's development indicator and provider attribution remain visible. No credentials, auth transport, tenant policy or session acceptance gate were changed by this presentation pass.

Validation: 27 frontend tests, lint/types/build and 3 CSP tests passed. Deployed browser regression has **7 passed, 1 configuration-specific skip**, including two new checks of the real development Clerk form at 375px and 1440px. Desktop dark, desktop light and mobile screenshots were inspected. A focused light-theme check waits for the actual input/button colors to settle before capturing, avoiding misleading mid-transition screenshots. Anonymous access denial remains covered. No live sign-in or expiry success is inferred from these visual checks; final 2C acceptance remains PENDING. Preview artifacts are stored under ignored `.local/previews/`.


## Signed-in workspace presentation redesign

The user correctly noted that the sign-in redesign had not changed the signed-in organization directory and that the complete product was still unbuilt. This pass changes the actual signed-in shell and existing 2C screens: navy contextual navigation, a light default canvas with a persisted dark option, real organization/role summary counts, accessible organization table, search/sort/clear states, compact account controls, and consistent organization overview/settings views. Organization summaries and workspace counts use returned API data; no execution or usage statistics were invented. Members retain the existing protected mutation flow and confirmation; settings remain read-only because no settings-write endpoint exists.

Production presentation components are separated from authentication/data fetching to permit static screenshot review without a signed-in browser or an auth bypass. Static previews explicitly use synthetic organizations and are labeled “Design preview · synthetic data”; no preview account or fixture API route is deployed. Four static presentation checks (directory desktop/mobile, overview, settings) passed and screenshots were inspected. **30 frontend tests**, lint/types/build and **3 CSP tests** passed, including search, sort, role/destination preservation and organization-scoped workspace links. Authentication, RLS, prior migrations and development records are preserved. Existing API/data services were not expanded into 2D.

[BUILD_STATUS.md](BUILD_STATUS.md) explicitly lists the implemented foundation and missing teammate builder, execution, integrations, knowledge and approval capabilities. This is not completion of the full AI workforce platform. The live session acceptance gate remains PENDING.

Deployment confirmation for the workspace redesign: the web container is healthy and serves a JavaScript bundle whose SHA-256 matches the tested production build. Readiness returns 200. Read-only inspection confirms the same one local user and both existing acceptance organizations remain present. The configured deployment's existing browser suite passed **7 tests with 1 unconfigured-only skip** after deployment; the four synthetic presentation checks are counted separately and do not establish live authentication. No request to recreate user organizations or bypass the 2C gate was made.


## Sequencing reaffirmed by the user

The user explicitly selected “Preserve gate; finish live 2C verification first.” No 2D development is authorized before acceptance. Browser discovery was rechecked and still returned no entries. A new ignored read-only baseline was saved for correlating the next live test and comparing identity after reauthentication. No completed regression suite was rerun, no credentials were printed, and no development records or Docker volumes were changed. Mandatory gaps remain the observed signed-out interval and real invalidated-session recovery. Human participation is required until a local signed-in browser is connected.


## Test A — signed-out interval recorded

The user explicitly reported “Sign-in page; no organization cards” after clicking Sign out, directly opening `/app`, and remaining signed out. This is human-operated browser evidence, not direct agent browser control. It resolves the previously ambiguous signed-out interval and supersedes that pending item. A separate agent HTTP request without bearer credentials returned **401** with correlation `d04f80e4-804f-44d1-a256-3634d173cf55`. This is independent anonymous API rejection, not a captured request from the user's browser and not a test of an already issued JWT's immediate revocation.

Read-only comparison confirms one local user and the same identity fingerprint as the pre-test baseline. No records, credentials, migrations or Docker volumes were changed. Test A is verified within the stated evidence scope. **The only remaining mandatory live gate is Test B: genuine provider-side invalidation/expiration, denied access, stale-data removal and recovery with the same local identity. Final 2C acceptance remains PENDING; 2D remains blocked.**


## Test B — post-revocation reauthentication evidence

The user reports “I got this page after signing in after revoking” and supplies the 23:38:51 IST screenshot showing the real organization directory, two organizations, OWNER access to both, and the account control. Read-only inspection confirms exactly one local user, zero duplicate external subjects, the same identity fingerprints as both saved live-gate/Test-B baselines, and both ACTIVE acceptance organizations preserved.

Structured server logs show protected organization listing returned 200 at 23:38:46 IST (18:08:46 UTC), correlation `87ab1467-1d10-49ce-bd63-198301312ca4`. This supports successful reauthenticated API access and recovery without duplicate provisioning. The user reports provider revocation; the agent did not operate or independently inspect the Clerk dashboard.

The post-login screenshot does not establish what happened in the old tab after revocation but before signing back in, nor the revocation timestamp or elapsed wait. No expired-session API denial is inferred from a successful fresh-session request; SDK-side rejection may prevent any such API request. The agent asked for clarification of the observed invalidated interval, without requiring another test cycle. Test B's reauthentication/identity consistency portion is verified within this scope. The invalidated-session denial/stale-content interval remains pending confirmation; final acceptance remains PENDING, and 2D remains blocked.


### Test B interval clarification

The user clarified “I signed it first,” in response to whether the revoked-session interval was checked before reauthentication. This is understood as signing in again before checking organization access. Access to both owned organizations after reauthentication is expected. The successful recovery and unchanged local identity evidence remain valid, but the old-session denial/stale-content interval was not observed. Do not classify this as either a passing invalidation test or a confirmed access-control failure. No additional regression run or application change is justified by this clarification. **Final 2C status remains PENDING; the user's preserved sequencing gate continues to block 2D.**


### Protected-route screenshot at 23:54 IST

The user followed the instruction to open `/app` while not reauthenticated and provided a screenshot whose address bar shows `/sign-in`. The real Clerk sign-in form is visible; no organization A/B entries or signed-in workspace navigation are displayed. This directly supports protected-route denial in the current signed-out/invalid-session state. A separate anonymous API probe again returned HTTP 401 (correlation `fba946cb-0622-438e-a1cc-20375f7f6221`); it is not attributed to the user's browser or an expired bearer token. The local identity still matches the saved baseline with one user.

To avoid confusing normal logout with provider invalidation, the user has been asked only to confirm whether this observed route followed Clerk's Revoke device action and the six-minute wait. The screenshot does not expose that initiating event or timing, so Test B must not be labeled fully verified from the image alone. No repeat regression suite, authentication bypass or data mutation was performed. Final acceptance remains PENDING until the genuine-invalidation provenance is confirmed.


## Redirect diagnosis following the user's correction

The user corrected the agent: the page initially reached was the previously supplied public homepage, and opening `/app` subsequently showed the sign-in page. The agent had treated the destination difference as grounds for repeatedly requesting clarification. That interpretation was incorrect: `ClerkProvider.afterSignOutUrl` and the explicit sign-out action target `/`, whose signed-out entry renders the public welcome page; the protected guard independently targets `/sign-in`. A public homepage with Sign in and then a protected-route sign-in screen is expected behavior. These images do not demonstrate an authorization failure. The user requested no further repetitive manual questioning; none was issued in this investigation.

Code review separately found that cache cleanup tracked only user ID. It now observes provider-confirmed signed-out state and session changes as well, including a fresh session for the same user. During a session switch, protected children are withheld until old-session cache eviction completes. A temporary SDK loading state is not misclassified as a confirmed identity transition. Three targeted SDK-adapter tests cover provider invalidation, same-user reauthentication and transient loading, bringing the frontend suite to **33 passed**. Lint/types/build and **3 CSP tests** passed. These are explicit SDK-mocked transition tests, not claims that the agent revoked a live Clerk session.

The homepage-versus-sign-in destination issue is resolved as expected routing; there is no confirmed access-control bug in the screenshots. The agent will not claim an independently observed remote revocation event or measured wait from them. The formal genuine-provider Test B provenance remains unverified, so final acceptance remains PENDING under the preserved gate. No 2D work, data reset or credential change was performed.

Deployment verification for the session-cache correction: all three Compose services are healthy, readiness returns HTTP 200, and the served JavaScript asset matches the tested local production build by SHA-256. The focused deployed browser regression passed **3/3**: anonymous protected-content rejection and actual Clerk sign-in usability at 375px and 1440px. These anonymous checks supplement the **34 frontend** and **3 CSP** passing checks; they do not establish provider-side revocation of the user's live session. Existing backend/database checks were not unnecessarily repeated for this frontend-only correction. No development records, migrations or Docker volumes were reset. Final status: **CHECKPOINT 2C PENDING**, solely for the outstanding genuine-provider invalidation interval evidence; 2D has not begun.


## Organization selector and directory navigation repair — 2026-11-04

The screenshot exposed a presentation/interaction defect: the sidebar control displayed a dropdown chevron but was a plain link to `/app`. It now opens an organization chooser populated from the authenticated organization API. Within an organization it displays the selected name; choosing another organization navigates to that tenant's Command Center. From the directory, Members and Settings now open the chooser with destinations scoped to the chosen organization, rather than being disabled controls. The directory summary now says “Other organization roles” to distinguish non-OWNER roles from a count of people.

A read-only development database query confirmed `2c-acceptance-a` and `2c-acceptance-b` each have exactly one ACTIVE OWNER membership. No missing-member conclusion is supported by the directory's previous zero non-owner-role count. Invitations remain unimplemented; this fix does not fabricate members or invite functionality.

Validation: 34 frontend tests passed, including chooser destinations for Command Center, Members and Settings; lint, types, production build and three CSP tests passed. The test uses explicit organization fixtures and establishes routing behavior, not a new live-user acceptance result. The outstanding genuine-provider invalidation interval remains unverified. **2C remains PENDING; 2D has not begun**, consistent with the user's preserved sequencing instruction. No development data, migrations or Docker volumes were reset.

Deployment completed: web/API/PostgreSQL are healthy, readiness returned 200, and the served JavaScript SHA-256 matches the tested production build. Three focused deployed anonymous browser checks passed (protected route denial and real Clerk sign-in at mobile/desktop widths). The chooser's authenticated destinations are covered by the frontend interaction test; no live authenticated browser control or provider-revocation result is inferred from these checks.


## Sequencing superseded by explicit authorization — 2026-11-04

The user selected “Proceed with development; keep 2C pending.” This supersedes the earlier prohibition on starting 2D; it does not pass the 2C acceptance gate. Teammate/knowledge/task/invitation development and additive migrations 0004/0005 followed that authorization. The new build's results are recorded in WORKFORCE_RELEASE.md and BUILD_STATUS.md. Existing migrations 0001–0003 remain intact. The real-model workflow test uses isolated cryptographic test authentication and cannot be substituted for the outstanding genuine Clerk-invalidation interval. **Checkpoint 2C remains PENDING.**


## Vector/chat development verification — 2026-11-06

Following the explicit authorization to continue development with 2C pending, additive migration 0006 and vector/chat features were deployed. A read-only query still finds one user, two organizations, two real memberships and two workspaces. The 24 fictional profiles reside separately and grant no access. Clean regression results and deployed service evidence are recorded in [RAG_AND_CHAT.md](RAG_AND_CHAT.md). They do not establish the missing genuine-provider invalidation interval. **CHECKPOINT 2C PENDING.**


## Account navigation and recovery regression — 2026-11-06

Frontend fixes preserve protected destinations/invitation fragments through sign-in, retry a rejected cached token once through Clerk before fail-closed recovery, and distinguish real member access from fictional profiles. All 51 frontend tests pass, including repeated-401 cache clearing, token retrieval failure, sign-out barriers and safe return-target validation. These are controlled regressions rather than a live provider-invalidation test; no browser was connected. **CHECKPOINT 2C remains PENDING.** Details and observed HTTP/SQL evidence are in RAG_AND_CHAT.md.


## Human support feature development — 2026-11-09

Per the prior authorization to continue features without accepting 2C, additive migration 0007 adds explicit human handoff to RAG chat. All existing records were preserved. Controlled two-role tests verify sharing, claim exclusivity, AI fencing and tenant isolation; no live two-human Clerk session was observed. See [HUMAN_HANDOFF.md](HUMAN_HANDOFF.md). **CHECKPOINT 2C remains PENDING.**


## Functional development continuation — 2026-11-10

Authorized feature development continued with 2C pending. See [functional release evidence](FUNCTIONAL_RELEASE_2026_11_10.md). None of its synthetic-identity tests, live OpenAI checks or anonymous browser smoke checks establish the outstanding genuine Clerk-invalidation interval. **CHECKPOINT 2C remains PENDING.**
