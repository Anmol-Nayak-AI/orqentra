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

## Observed publication — 10 November 2026

The repository was created and verified **public** at https://github.com/Anmol-Nayak-AI/orqentra. Both `main` and `develop` were pushed at the initial application commit `51ffcf2`; default branch is `main`. GitHub API verification confirms:

- The only collaborator is `Anmol-Nayak-AI`, with admin access. No additional write grants were created.
- `main` requires a pull request, current `backend`, `frontend`, `integration` and `dependency-security` checks, and conversation resolution. Admin enforcement is enabled. No force pushes or deletion are allowed.
- `develop` permits owner development commits but prohibits force pushes/deletion, including for administrators.
- GitHub secret scanning, push protection and private vulnerability reporting are enabled. Workflow tokens default to read access and cannot approve pull requests.
- No deployment workflow was triggered. Application deployment, E2B execution and live payments remain unauthorized.

Gitleaks 8.30.1 found zero findings in the 259-file initial publication tree and initial Git history. A separate comparison found zero matches against configured local credentials. Configured `.env` files, `.local` records/backups, dependency directories and generated test artifacts are excluded. This is evidence of the performed scan, not a guarantee that a scanner detects every possible disclosure.

Remote CI results are separate from the previously observed local test results. Changes to `main` must follow its enforced PR/check gate; creating public branches does not imply that those checks have already run on GitHub. No protection bypass or forced update is used.
