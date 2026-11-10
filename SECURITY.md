# Security policy

Orqentra is under development and has not passed commercial production acceptance. Do not use development credentials, local records or demo fixtures for customer workloads.

Do not include credentials, session tokens, private documents, customer data or exploitable payloads in public issues or pull requests. Use GitHub's private vulnerability reporting feature on this repository when it is available. A response-time or remediation SLA is not currently offered.

Secrets belong in ignored environment files or an approved secret manager. Public frontend environment variables must never contain backend secrets. Provider account configuration alone must not enable payment or sandbox actions.

Tenant isolation uses application authorization, composite tenant keys and forced PostgreSQL RLS. Untrusted code may execute only through the separately authorized isolated sandbox path; never inside the API/worker containers or on the developer host.

See docs/RELEASE_ACCEPTANCE.md for known acceptance gaps. A passing fixture test is not proof of a safe live provider or production deployment.
