# Free public recruiter preview

**Live:** https://orqentra-demo.onrender.com · **Guided chat:** https://orqentra-demo.onrender.com/#chat

Deployed on 10 November 2026 as a Render static site. This is an interface preview, not a hosted full-stack or production-accepted release.

This is a separate static entry point for a free-only public demo. It does not replace the React/FastAPI application or bypass its authentication. The existing database, volumes, migrations and configured provider integrations remain local and unchanged.

The preview includes fictional organizations and profiles, navigation, teammate role descriptions, searchable static product guidance, guided/scripted chat answers with inspectable excerpts, and a browser-local review interaction. The persistent preview banner and Release status page explain its limits. It is not a live RAG chatbot, authenticated tenant-isolation test, sandbox run or payment integration. Changes live only in the browser tab and reset on refresh or organization switch.

Build with `npm run build:demo --workspace @orqentra/web`. Vite uses a separate config/entry with environment-file discovery disabled. Output is `apps/web/dist-demo`; it imports no Clerk provider or application API client. HTTP CSP headers and the HTML meta policy deny API/network connections, framing and form submission. The production application build/authentication routes retain their existing implementation.

`infrastructure/render/free-preview.yaml` describes one static site only. There is no compute plan, backend, database, worker, disk, custom domain, paid workspace change or provider credential. Automatic deploys and pull-request previews are off to bound build usage. Render static sites use included bandwidth/build allowances; monitor those allowances and do not enable paid upgrades. No OpenAI, Razorpay, E2B, Clerk secret or Render control-plane key is supplied to the site build or browser.

`scripts/deploy_free_preview.py` loads Render control-plane credentials from ignored `.env.render`, validates a static-only manifest and an explicitly selected workspace, records a creation intent before one POST, and refuses uncertain automatic retries or blind modification of existing services. The Render API key is never a frontend environment variable. The user's existing Render service must not be modified.

Local validation: 105 backend unit tests, 63 frontend tests and 4 CSP checks pass. Two separate browser regressions pass at 390px and 1440px, observing sample organization reset, local guided answers, search/review behavior, no private/API network calls and no browser runtime errors. The tests also cover rejection of paid plans and durable handling of uncertain resource creation using a synthetic control plane. Production build, type/lint checks pass; CSS ordering warnings and the existing main-application bundle warning are non-blocking known warnings. No live model/payment/sandbox call is used by these checks.

## Observed deployment evidence

Render reports deploy `dep-dbpi8hbbc2fs73a9d07g` LIVE from source commit `167ea021d180b6d1cbe4e535962032b56325bb1b`. The service type is `static_site`; no paid compute plan, database, worker, disk or live-provider credential was created/configured. Autodeploys and previews are off. Existing Render services were not modified.

The actual HTTPS URL returns 200. Its HTML and JavaScript/CSS bytes match the tested local preview build. CSP includes `connect-src 'none'`; frame protection is DENY and content-type sniffing is disabled. Two browser checks passed against the real URL at 390px and 1440px, including functional navigation and source/member filtering, guided local answers, reset on organization switch, sample review and deep-link reload, with no JavaScript errors or API calls. Both live screenshots were visually inspected. These are observations of a static preview, not proof of a live model, authorization, tenant isolation or payment flow.

The separate production application build and existing UI suite still pass (63 component tests plus four CSP/build-policy checks). Database/identity records, Docker volumes and migrations were not changed by this deployment. Full commercial acceptance remains pending in RELEASE_ACCEPTANCE.md.
