"""Add published starter definitions to the two owned local acceptance organizations."""

import argparse
from uuid import uuid4

from database_support import ROOT, local_admin_url
from dotenv import dotenv_values
from orqentra.agents.schemas import TeammateConfiguration
from orqentra.persistence.models import AgentDefinition
from orqentra.persistence.repositories import AgentRepository
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
parser.parse_args()
config = dotenv_values(ROOT / ".env")
if config.get("POSTGRES_DB") != "orqentra":
    raise SystemExit("Refusing an unknown development database.")
admin = create_engine(local_admin_url(), hide_parameters=True)
with admin.connect() as connection:
    targets = connection.execute(
        text(
            "SELECT o.id,m.user_id,w.id FROM organizations o JOIN organization_memberships m "
            "ON m.organization_id=o.id JOIN users u ON u.id=m.user_id JOIN workspaces w "
            "ON w.organization_id=o.id WHERE o.status='ACTIVE' AND m.status='ACTIVE' "
            "AND m.role='OWNER' AND u.status='ACTIVE' AND u.external_auth_id IS NOT NULL "
            "AND w.status='ACTIVE' AND o.slug IN ('2c-acceptance-a','2c-acceptance-b') "
            "ORDER BY o.id,w.created_at"
        )
    ).all()
admin.dispose()
url = dotenv_values(ROOT / ".env.runtime").get("ORQENTRA_DATABASE_URL")
if not url:
    raise SystemExit("Restricted runtime required.")
runtime = database_engine(
    make_url(url)
    .set(host="127.0.0.1", port=int(config.get("POSTGRES_PORT") or "5432"))
    .render_as_string(hide_password=False)
)
starters = [
    (
        "Starter · Onboarding specialist",
        "starter-onboarding",
        "onboarding.v1",
        "Prepare evidence-backed onboarding plans and draft replies from approved workspace sources. Ask for missing facts and never claim external delivery.",
    ),
    (
        "Starter · Python analyst",
        "starter-python-analyst",
        "python-analysis.v1",
        "Prepare source-backed Python analyses for human review. Use approved facts, print text results, avoid network calls and credentials, and never execute code.",
    ),
]
seen, added = set(), 0
try:
    for organization, owner, workspace in targets:
        if organization in seen:
            continue
        seen.add(organization)
        context = TrustedOrganizationContext(organization, owner, uuid4())
        with transaction(runtime, context) as session:
            require_restricted(session)
            repository = AgentRepository(session, context)
            for name, slug, workflow, instructions in starters:
                if session.scalar(
                    select(AgentDefinition.id).where(
                        AgentDefinition.workspace_id == workspace,
                        AgentDefinition.slug == slug,
                    )
                ):
                    continue
                model = TeammateConfiguration(
                    instructions=instructions,
                    workflow=workflow,
                    output_schema="python_analysis_plan.v1"
                    if workflow == "python-analysis.v1"
                    else "onboarding_plan.v1",
                )
                item = repository.create(
                    workspace_id=workspace,
                    name=name,
                    slug=slug,
                    configuration=model.model_dump(mode="json"),
                )
                repository.publish(item.id, expected_revision=item.revision)
                added += 1
    print(
        f"Created/published {added} starter definitions in {len(seen)} owned development organizations. No tasks queued, code executed or identities created."
    )
finally:
    runtime.dispose()
