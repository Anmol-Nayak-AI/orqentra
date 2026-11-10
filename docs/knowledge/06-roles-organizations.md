# Orqentra guide · Organizations, roles and workspaces
Organizations are separate tenant boundaries in Orqentra. Use All organizations or the organization dropdown to select a team. The Command Center should show the selected organization's name. Organization creation assigns an active OWNER membership to its creator and creates a default workspace.

OWNER and ADMIN roles manage allowed administrative operations and handle human support. OWNER has ownership-management privileges; the last active owner is protected. MEMBER can participate in permitted work and edit teammate drafts. VIEWER has read-oriented permissions. Publishing teammates and managing approved knowledge require OWNER/ADMIN permissions. The backend checks the current role for every request; changing the dropdown does not grant permissions.

Workspace selection scopes knowledge retrieval and chat conversations within the organization. A user belonging to two organizations must switch into the correct one to see its resources. PostgreSQL forced row-level security and authenticated API checks enforce tenant isolation. Workspace-specific individual member grants are not yet implemented.
