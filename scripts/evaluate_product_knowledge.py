"""Bounded live product-knowledge evaluation; no chat/identity writes."""

import argparse
import json

from database_support import ROOT, local_admin_url
from dotenv import dotenv_values
from orqentra.persistence.session import database_engine
from orqentra.rag.provider import answer
from orqentra.rag.service import retrieve
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser()
parser.add_argument("--local", required=True, action="store_true")
parser.add_argument("--live", required=True, action="store_true")
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
checks = [
    ("How do I use Orqentra chat?", "How to use Chat"),
    (
        "How does Orqentra use a vector database and RAG?",
        "Knowledge, vector database and RAG",
    ),
    (
        "How do I invite a real teammate and can demo users sign in?",
        "Real users, invitations and demo profiles",
    ),
    (
        "How can I request human intervention in Orqentra?",
        "Human intervention and support handoff",
    ),
    (
        "What can Orqentra AI teammates do with tasks and approvals?",
        "AI teammates, tasks and reviews",
    ),
    (
        "What is the price of Orqentra and is there a guaranteed support SLA?",
        "Current limits and honest answers",
    ),
]
key = dotenv_values(ROOT / ".env.ai").get("OPENAI_API_KEY")
if not key or not targets:
    raise SystemExit("Configured development provider and owned workspace required.")
org, _, workspace = targets[0]
results = []
try:
    for question, expected_title in checks:
        sources = retrieve(runtime, org, workspace, question, key)
        result, usage = answer(
            key, question, sources, ["What are the demo support hours?"]
        )
        allowed = {s["chunk_id"]: s for s in sources}
        valid = bool(result.citations) and all(
            str(c.chunk_id) in allowed
            and c.quote in allowed[str(c.chunk_id)]["content"]
            for c in result.citations
        )
        relevant = any(
            expected_title in allowed[str(c.chunk_id)]["title"]
            for c in result.citations
            if str(c.chunk_id) in allowed
        )
        passed = valid and relevant and not result.insufficient_evidence
        results.append(
            {
                "question": question,
                "answer": result.answer,
                "passed": passed,
                "exact_citations": valid,
                "expected_guide_cited": relevant,
                "source_titles": [
                    allowed[str(c.chunk_id)]["title"]
                    for c in result.citations
                    if str(c.chunk_id) in allowed
                ],
                "usage": usage,
            }
        )
        print(
            json.dumps(
                {
                    "question": question,
                    "passed": passed,
                    "exact_citations": valid,
                    "expected_guide_cited": relevant,
                }
            )
        )
    folder = ROOT / ".local"
    folder.mkdir(exist_ok=True)
    (folder / "product-assistant-evaluation.json").write_text(
        json.dumps(results, indent=2)
    )
    if not all(row["passed"] for row in results):
        raise SystemExit(
            "Some live knowledge checks failed; inspect the private report."
        )
finally:
    runtime.dispose()
