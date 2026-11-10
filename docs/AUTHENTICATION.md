# Authentication (checkpoint 2C)

The browser uses Clerk React 6.18.4; the API verifies bearer session tokens using Clerk Backend API 7.0.0 and a pinned RSA public signing key. No Clerk secret key is needed by this integration. Passwords, session tokens and private signing keys are never persisted by Orqentra.

## Configure your existing Clerk application

Use the existing application's dashboard; do not create a second application. Copy the publishable key into the ignored root `.env` as `VITE_CLERK_PUBLISHABLE_KEY`. Copy `.env.auth.example` to ignored `.env.auth` and configure all three settings together:

- `CLERK_ISSUER`: exact HTTPS session issuer for that same application, without a trailing slash.
- `CLERK_JWT_KEY`: that application's RSA **public** signing key in PEM form. A quoted value with escaped `\n` newlines is supported. Never use a private key or `sk_` key here.
- `CLERK_ALLOWED_ORIGINS=http://127.0.0.1:8080` (add `http://127.0.0.1:5173`, comma separated, for Vite development).

Use the same host consistently: localhost and 127.0.0.1 are different origins. Configure the existing Clerk application's permitted local URLs and sign-in options if needed. Then run `make up` to rebuild the browser with its public key and reload API configuration. Host API development needs these variables exported explicitly; Python deliberately does not discover environment files automatically. Keep all environment files private. Only the publishable key may have a VITE prefix.

With no configuration, public health stays available and protected routes deny access. Partial or invalid configuration fails startup. Public browser configuration cannot substitute for API verification.

## Verification boundary

The API accepts only Authorization bearer tokens. It rejects malformed/oversized tokens and algorithms other than RS256. The official verifier checks signature, authorized party, optional configured audience and token times; Orqentra additionally enforces the exact issuer, required integer exp/iat/nbf, required user subject and session ID, and a maximum token lifetime of 300 seconds. Pending and impersonated sessions are rejected. Browser Origin, when present, must also be allowlisted. There is no cookie-based API authentication or client-supplied user/role bypass. Responses and logs do not include tokens.

The signing key is pinned locally, so key rotation requires updating the public key and restarting the API. No network request follows an untrusted token issuer or key ID. Verification does not call Clerk for each request: provider-side revocation can take until a previously issued token expires. Local disabled users and revoked memberships are checked in the database on every request. `ORQENTRA_CLERK_MAX_TOKEN_LIFETIME` can explicitly adjust the accepted lifetime (30–3600 seconds); keep it aligned with the existing application's short-lived session tokens.

Verified subject maps uniquely to `users.external_auth_id`; concurrent first requests create a single local user. No email matching, legacy-account adoption, reactivation, password copying or Clerk role/organization claims grant local access. Local profile fields start empty/generic; Clerk's UserButton manages the provider profile. Provider profile synchronization and invitation acceptance are outside this checkpoint.

## Live verification still required

Automated tests use ephemeral test signing keys and the actual SDK verifier with disposable PostgreSQL databases. They do not prove that the existing Clerk application is configured correctly. Once configured, verify actual sign-up/sign-in, refresh, sign-out, profile management, organization creation/switching, denied foreign organization access and session expiry in the browser. Confirm browser CSP permits the configured application's required requests. Never add production auth bypasses to make these checks pass.

References: [Clerk React integration](https://clerk.com/docs/react/getting-started/quickstart), [Python SDK](https://github.com/clerk/clerk-sdk-python), [Clerk CSP guidance](https://clerk.com/docs/guides/secure/best-practices/csp-headers).
