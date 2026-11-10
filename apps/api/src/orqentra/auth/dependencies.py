from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from orqentra.auth.permissions import Role, permits
from orqentra.auth.verification import InvalidSession, VerifiedIdentity, verify_session
from orqentra.core.config import Settings
from orqentra.persistence.errors import translate_database_error
from orqentra.persistence.session import TrustedOrganizationContext

bearer = HTTPBearer(auto_error=False)


def current_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> VerifiedIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    config: Settings = request.app.state.settings
    if not config.auth_configured:
        raise HTTPException(503, "Authentication is not configured.")
    try:
        identity = verify_session(credentials.credentials, config)
    except InvalidSession:
        raise HTTPException(
            401, "Invalid or expired session.", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    origin = request.headers.get("origin")
    if origin is not None and origin not in config.allowed_origins:
        raise HTTPException(403, "Origin not permitted.")
    return identity


@dataclass
class AuthenticatedSession:
    session: Session
    user_id: UUID
    identity: VerifiedIdentity


def identity_session(
    request: Request, identity: Annotated[VerifiedIdentity, Depends(current_identity)]
) -> Iterator[AuthenticatedSession]:
    engine: Engine | None = request.app.state.database_engine
    if engine is None:
        raise HTTPException(503, "Database is not configured.")
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            flags = session.execute(
                text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            ).one()
            if any(flags):
                raise HTTPException(503, "Runtime database privileges are unsafe.")
            session.execute(
                text("SELECT set_config('app.external_auth_id',:subject,true)"),
                {"subject": identity.subject},
            )
            user_id = session.scalar(text("SELECT public.orqentra_provision_identity()"))
            if not isinstance(user_id, UUID):
                raise HTTPException(403, "Account is unavailable.")
            yield AuthenticatedSession(session, user_id, identity)
    except DBAPIError as exc:
        raise translate_database_error(exc) from None


@dataclass
class AuthorizedOrganization:
    authenticated: AuthenticatedSession
    context: TrustedOrganizationContext
    role: Role
    membership_id: UUID


class OrganizationPermission:
    def __init__(self, permission: str) -> None:
        self.permission = permission

    def __call__(
        self,
        organization_id: UUID,
        request: Request,
        authenticated: Annotated[AuthenticatedSession, Depends(identity_session, scope="function")],
    ) -> AuthorizedOrganization:
        session = authenticated.session
        # Narrow SECURITY DEFINER lookup scopes membership before setting a tenant GUC.
        membership = session.execute(
            text("SELECT role,membership_id FROM public.orqentra_membership_for_org(:id)"),
            {"id": organization_id},
        ).first()
        if membership is None:
            raise HTTPException(403, "Organization access denied.")
        role = Role(membership.role)
        if not permits(role, self.permission):
            raise HTTPException(403, "Permission denied.")
        session.execute(
            text("SELECT set_config('app.organization_id',:id,true)"), {"id": str(organization_id)}
        )
        return AuthorizedOrganization(
            authenticated,
            TrustedOrganizationContext(
                organization_id, authenticated.user_id, UUID(request.state.correlation_id)
            ),
            role,
            membership.membership_id,
        )
