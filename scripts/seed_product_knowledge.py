"""Seed reviewed Orqentra product guides into owned local acceptance workspaces."""

import argparse
from uuid import uuid4

from database_support import ROOT, local_admin_url
from dotenv import dotenv_values
from orqentra.execution.routes import digest
from orqentra.persistence.models import (
    AuditEvent,
    KnowledgeDocument,
)
from orqentra.persistence.session import (
    TrustedOrganizationContext,
    database_engine,
    transaction,
)
from orqentra.rag.service import require_restricted
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser()
parser.add_argument("--local", required=True, action="store_true")
args = parser.parse_args()
config = dotenv_values(ROOT / ".env")
if config.get("POSTGRES_DB") != "orqentra":
    raise SystemExit("Refusing an unknown development database.")
admin = create_engine(local_admin_url(), hide_parameters=True)
with admin.connect() as c:
    targets = c.execute(
        text(
            "SELECT o.id,m.user_id,w.id FROM organizations o JOIN organization_memberships m ON m.organization_id=o.id JOIN users u ON u.id=m.user_id JOIN workspaces w ON w.organization_id=o.id WHERE o.status='ACTIVE' AND m.status='ACTIVE' AND m.role='OWNER' AND u.status='ACTIVE' AND u.external_auth_id IS NOT NULL AND w.status='ACTIVE' AND o.slug IN ('2c-acceptance-a','2c-acceptance-b') ORDER BY o.id,w.created_at"
        )
    ).all()
admin.dispose()
url = dotenv_values(ROOT / ".env.runtime").get("ORQENTRA_DATABASE_URL")
if not url:
    raise SystemExit("Restricted local runtime is required.")
runtime = database_engine(
    make_url(url)
    .set(host="127.0.0.1", port=int(config.get("POSTGRES_PORT") or "5432"))
    .render_as_string(hide_password=False)
)
guides = []
for path in sorted((ROOT / "docs" / "knowledge").glob("*.md")):
    lines = path.read_text().strip().splitlines()
    title = lines[0].removeprefix("# ")
    content = "\n".join(lines[1:]).strip()
    if not 1 <= len(title) <= 200 or not 1 <= len(content) <= 24000:
        raise SystemExit("Product guide exceeds supported limits.")
    guides.append((title, content))
if not guides:
    raise SystemExit("No reviewed guides found.")
added = 0
seen = set()
try:
    for org, actor, workspace in targets:
        if workspace in seen:
            continue
        seen.add(workspace)
        with transaction(
            runtime, TrustedOrganizationContext(org, actor, uuid4())
        ) as session:
            require_restricted(session)
            active_count = (
                session.scalar(
                    select(text("count(*)"))
                    .select_from(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.workspace_id == workspace,
                        KnowledgeDocument.status == "ACTIVE",
                    )
                )
                or 0
            )
            for title, content in guides:
                existing = session.scalar(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.workspace_id == workspace,
                        KnowledgeDocument.title == title,
                    )
                )
                if existing:
                    if (
                        existing.content_hash != digest(content)
                        or existing.status != "ACTIVE"
                    ):
                        raise RuntimeError(
                            "An existing guide differs or is revoked; review it instead of overwriting."
                        )
                    continue
                if active_count >= 20:
                    raise RuntimeError(
                        "Workspace knowledge limit reached; existing sources were preserved."
                    )
                doc = KnowledgeDocument(
                    organization_id=org,
                    workspace_id=workspace,
                    title=title,
                    content=content,
                    content_hash=digest(content),
                )
                session.add(doc)
                session.flush()
                session.add(
                    AuditEvent(
                        organization_id=org,
                        actor_user_id=actor,
                        action="knowledge.product_guide_added",
                        resource_type="knowledge",
                        resource_id=doc.id,
                        correlation_id=uuid4(),
                        safe_metadata={},
                    )
                )
                added += 1
                active_count += 1
    print(
        f"Prepared {len(guides)} product guides for {len(seen)} owned development workspaces; added {added} documents. Existing records preserved."
    )
finally:
    runtime.dispose()
