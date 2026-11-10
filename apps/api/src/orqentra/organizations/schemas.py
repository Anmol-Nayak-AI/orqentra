from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from orqentra.auth.permissions import Role


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class MeResponse(Contract):
    id: UUID
    display_name: str
    status: str


class OrganizationCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class OrganizationResponse(Contract):
    id: UUID
    name: str
    slug: str
    status: str
    role: Role


class MembershipResponse(Contract):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: Role
    status: str


class MembershipUpdate(Contract):
    role: Role


class WorkspaceResponse(Contract):
    updated_at: datetime
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: str
