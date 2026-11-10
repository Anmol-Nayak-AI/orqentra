# Database relationships — Phase 2B

The diagram is Mermaid source. Relationships are implemented by named PostgreSQL foreign keys; rendering is not claimed as an automated test.

```mermaid
erDiagram
  organizations ||--o{ organization_memberships : contains
  users ||--o{ organization_memberships : joins
  organizations ||--o{ workspaces : owns
  organizations ||--o{ agent_definitions : scopes
  workspaces ||--o{ agent_definitions : contains
  organization_memberships ||--o{ agent_definitions : creates
  agent_definitions ||--o{ agent_versions : publishes
  organization_memberships ||--o{ agent_versions : publishes
  agent_definitions ||--o{ agent_tool_permissions : configures
  organizations ||--o{ audit_events : records
  organization_memberships ||--o{ audit_events : acts
  organizations {
    uuid id PK
    string slug UK
    string status
  }
  users {
    uuid id PK
    string external_auth_id UK
    string email
  }
  organization_memberships {
    uuid id PK
    uuid organization_id FK
    uuid user_id FK
    string role
    string status
  }
  workspaces {
    uuid id PK
    uuid organization_id FK
    string slug
  }
  agent_definitions {
    uuid id PK
    uuid organization_id FK
    uuid workspace_id FK
    uuid created_by FK
    jsonb draft_configuration
    int revision
    string lifecycle_status
  }
  agent_versions {
    uuid id PK
    uuid organization_id FK
    uuid agent_definition_id FK
    int version_number
    uuid published_by FK
    jsonb configuration_snapshot
  }
  agent_tool_permissions {
    uuid id PK
    uuid organization_id FK
    uuid agent_definition_id FK
    string tool_identifier
    jsonb permission_scope
  }
  audit_events {
    uuid id PK
    uuid organization_id FK
    uuid actor_user_id FK
    uuid resource_id
    uuid correlation_id
    jsonb metadata
  }
```

## Composite consistency rules

| Child key | Referenced unique key | Prevented inconsistency |
|---|---|---|
| agents(organization_id, workspace_id) | workspaces(organization_id, id) | Agent owned by A referencing B's workspace |
| agents(organization_id, created_by) | memberships(organization_id, user_id) | Creator who is not a member of the owning organization |
| versions(organization_id, agent_definition_id) | agents(organization_id, id) | A's version referencing B's definition |
| versions(organization_id, published_by) | memberships(organization_id, user_id) | Publisher with no membership in that organization |
| tool permissions(organization_id, agent_definition_id) | agents(organization_id, id) | Foreign-organization tool grant |
| audit(organization_id, actor_user_id) | memberships(organization_id, user_id) | Audit actor unrelated to the owning organization |

Composite membership FKs establish association, not active membership or authorization; active membership/roles require trusted service checks. Versions inherit workspace through their immutable definition reference; duplicate workspace_id is not stored on versions. Definitions cannot move organizations/workspaces, so prior version scope cannot silently change.

Audit resource_id is a polymorphic UUID rather than an FK to every possible resource type; consistency with resource_type is an application responsibility. correlation_id is an opaque UUID, not an identity credential. ORM view-only relationships allow traversal without silently assigning ownership through relationship writes. All deletion FKs are RESTRICT, preserving historical references.

See [full table and index specification](DATABASE_SCHEMA.md).

Checkpoint 2C retains these foreign-key relationships. A verified Clerk subject maps to one local user through unique external_auth_id; active local organization memberships, rather than provider organization claims, authorize traversal to tenant-owned records. Organization bootstrap creates an OWNER membership and a default workspace atomically. See [authorization](AUTHORIZATION.md).
