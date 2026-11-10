"""Idempotent, labeled development roster/knowledge/chat; never creates real identities."""

import argparse
from uuid import uuid4

from database_support import ROOT, local_admin_url
from dotenv import dotenv_values
from orqentra.execution.routes import digest
from orqentra.persistence.models import (
    AuditEvent,
    ChatConversation,
    ChatExchange,
    DemoMember,
    KnowledgeDocument,
)
from orqentra.persistence.session import (
    TrustedOrganizationContext,
    database_engine,
    transaction,
)
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
roster = [
    ("Mira Patel", "Customer Success Lead", "ADMIN"),
    ("Noah Chen", "Implementation Engineer", "MEMBER"),
    ("Sofia Reed", "Knowledge Manager", "ADMIN"),
    ("Alex Rivera", "Support Specialist", "MEMBER"),
    ("Priya Shah", "AI Operations Engineer", "MEMBER"),
    ("Liam Brooks", "Customer Onboarding", "MEMBER"),
    ("Elena Novak", "Compliance Reviewer", "VIEWER"),
    ("Omar Ali", "Solutions Architect", "MEMBER"),
    ("Zoe Martin", "Product Operations", "MEMBER"),
    ("Ethan Park", "Quality Analyst", "MEMBER"),
    ("Amara Okafor", "Program Manager", "ADMIN"),
    ("Jae Morgan", "Executive Observer", "VIEWER"),
]
content = "This is fictional Orqentra demo knowledge, not a real company policy. Demo support hours are Monday to Friday, 09:00–17:00 UTC. Demo incidents are escalated first to the Demo Support Lead, then to the Demo Operations Manager. Before activating a demo customer workspace, confirm the company name, requested region, and a designated reviewer. Never send external messages from this demo environment."
seen = set()
count = 0
try:
    for org, actor, workspace in targets:
        if org in seen:
            continue
        seen.add(org)
        with transaction(runtime, TrustedOrganizationContext(org, actor, uuid4())) as s:
            flags = s.execute(
                text(
                    "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            if any(flags):
                raise SystemExit("Unsafe runtime role.")
            added = 0
            for name, title, role in roster:
                email = name.lower().replace(" ", ".") + "@example.invalid"
                if (
                    s.scalar(select(DemoMember.id).where(DemoMember.email == email))
                    is None
                ):
                    s.add(
                        DemoMember(
                            organization_id=org,
                            display_name=name,
                            email=email,
                            job_title=title,
                            demo_role=role,
                        )
                    )
                    added += 1
            if (
                s.scalar(
                    select(KnowledgeDocument.id).where(
                        KnowledgeDocument.title == "Demo · Operations handbook"
                    )
                )
                is None
            ):
                active = s.scalar(
                    text(
                        "SELECT count(*) FROM knowledge_documents WHERE workspace_id=:id AND status='ACTIVE'"
                    ),
                    {"id": workspace},
                )
                if active is not None and active < 20:
                    s.add(
                        KnowledgeDocument(
                            organization_id=org,
                            workspace_id=workspace,
                            title="Demo · Operations handbook",
                            content=content,
                            content_hash=digest(content),
                        )
                    )
            if (
                s.scalar(
                    select(ChatConversation.id)
                    .join(
                        ChatExchange,
                        ChatExchange.conversation_id == ChatConversation.id,
                    )
                    .where(
                        ChatConversation.created_by == actor,
                        ChatExchange.idempotency_key == "demo-support-v1",
                    )
                )
                is None
            ):
                chat = ChatConversation(
                    organization_id=org,
                    workspace_id=workspace,
                    created_by=actor,
                    title="Demo · Support and escalation",
                )
                s.add(chat)
                s.flush()
                s.add(
                    ChatExchange(
                        organization_id=org,
                        conversation_id=chat.id,
                        idempotency_key="demo-support-v1",
                        question="What are the demo support hours, and how should I escalate a demo incident?",
                    )
                )
            if added:
                s.add(
                    AuditEvent(
                        organization_id=org,
                        actor_user_id=actor,
                        action="demo.roster_seeded",
                        resource_type="demo",
                        resource_id=org,
                        correlation_id=uuid4(),
                        safe_metadata={},
                    )
                )
            count += added
    print(
        f"Demo roster prepared for {len(seen)} owned acceptance organizations; added {count} fictional demo profiles. No users or real memberships created."
    )
finally:
    runtime.dispose()
