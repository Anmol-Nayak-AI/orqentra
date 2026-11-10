# Organization-first navigation — 2026-11-09

The organization directory previously exposed Command Center, Chat, Members and other tenant-specific controls as buttons which opened a destination-dependent organization chooser. That made clicking Command Center leave the user on the directory with an expanded sidebar, instead of following a clear organization-first flow.

The directory now shows only All organizations and the explicit organization selector in its main navigation. Open an organization from the directory or selector to enter its Command Center; only then do its workspace sections appear. Command Center is a direct organization-scoped link and does not open the selector. Switching organizations updates destinations, and returning to All organizations hides tenant sections again. The selector says Switch organization rather than Switch workspace. Existing server-side authorization remains unchanged.

Validation: frontend lint/types/build and 52 tests pass, plus 3 CSP checks. A combined navigation regression covers directory → organization → Command Center → organization switch → directory, scoped destinations and audit-role visibility. Two labeled synthetic presentation checks pass at 1440px and 375px with no horizontal overflow; previews were visually inspected. These are presentation/interaction tests, not new live Clerk acceptance evidence. No backend code, migrations or development records changed.

Deployment: Docker Desktop was found stopped and started without reset. The web image was rebuilt and the existing stack restored healthy using existing volumes. Readiness returns 200, and served JavaScript matches the tested final build by SHA-256.
