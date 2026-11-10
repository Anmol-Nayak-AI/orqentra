# Orqentra guide · Sign-in, profile and sign-out
Sign in through Orqentra's Clerk sign-in form using an approved account. Clerk manages identity, connected login providers and profile settings. Open your avatar/account menu to manage your profile. Never paste passwords, verification codes or session tokens into the knowledge assistant.

After successful authentication, the backend provisions one local user for the verified Clerk subject. Repeated sign-ins with the same Clerk identity reuse that local account. Organization access depends on local active memberships; signing in alone does not grant access to every organization.

Sign out closes local protected access and clears private session caches. Protected pages should then require sign-in. A rejected cached token gets one Clerk refresh attempt; a missing or rejected fresh token locks the workspace and requires recovery. Sign in again with the same account to recover. If the provider or network is unavailable, the assistant cannot repair credentials or bypass authentication. Account-specific failures need investigation using a visible Request ID, without sharing tokens.
