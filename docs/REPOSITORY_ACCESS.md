# Public repository and write-access policy

Requested destination: `https://github.com/Anmol-Nayak-AI/orqentra`.

The intended branches are `main` (reviewed baseline/default) and `develop` (ongoing integration). Public readers receive no upstream write grant. Only the owner is to retain administration/write access; no collaborators are added by this setup. GitHub public repositories remain cloneable/forkable, so this policy cannot prevent someone modifying a separate copy.

Intended remote protections:

- `main`: pull request required, up-to-date backend/frontend/integration/dependency-security checks, conversation resolution, no force push or branch deletion; apply protections to administrators too.
- `develop`: no force push or deletion; normal owner commits remain possible.
- CODEOWNERS identifies the repository owner; it is not an access-control mechanism by itself.
- Secrets and private artifacts are ignored and scanned before the initial commit. Source templates contain placeholders; there are no customer records, database dumps, tokens or configured environment files in the publication tree.
- A GitHub no-reply author address is used locally for public commit metadata. Global Git identity settings remain unchanged.
- No open-source reuse license is selected. Repository visibility does not grant write access or assert production readiness.

Remote creation, push, security features and protection settings must be checked on GitHub before claiming they are active. See the observed publication results appended below. Public source publication does not deploy the application or authorize any provider call.
