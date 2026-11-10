"""Adapter fixtures only. No E2B resource or untrusted host process is ever created."""

import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from e2b_code_interpreter import Sandbox

from orqentra.core.config import Settings
from orqentra.sandbox.provider import ApprovedCode, SandboxUnavailable, provider


def permit(code):
    return ApprovedCode(
        uuid4(),
        uuid4(),
        uuid4(),
        hashlib.sha256(code.encode()).hexdigest(),
        datetime.now(UTC) + timedelta(minutes=1),
    )


def configured():
    return Settings(
        sandbox_provider="e2b",
        sandbox_execution_approved=True,
        E2B_API_KEY="synthetic-only",
        e2b_template_id="synthetic-template",
    )


def test_sandbox_default_and_credentials_alone_never_create_resource(monkeypatch):
    monkeypatch.setattr(Sandbox, "create", lambda **kwargs: pytest.fail("must not create"))
    code = "print('synthetic')"
    for settings in (Settings(), Settings(sandbox_provider="e2b", E2B_API_KEY="synthetic-only")):
        with pytest.raises(SandboxUnavailable):
            provider(settings, lambda event: None).execute(code, permit(code))
    with pytest.raises(SandboxUnavailable):
        provider(configured(), lambda event: None).execute(code, permit("changed"))


@pytest.mark.parametrize(
    "scenario", ["completed", "network_mismatch", "output_limit", "cleanup_failed"]
)
def test_remote_policy_output_and_cleanup(monkeypatch, scenario):
    created, killed, events = [], [], []

    class FakeSandbox:
        sandbox_id = "synthetic-sandbox"

        def get_info(self, **kwargs):
            return SimpleNamespace(
                template_id="synthetic-template",
                cpu_count=1,
                memory_mb=512,
                allow_internet_access=False,
                volume_mounts=[],
                network=SimpleNamespace(
                    allow_public_traffic=scenario == "network_mismatch",
                    allow_out=[],
                    deny_out=["0.0.0.0/0", "::/0"],
                ),
            )

        def run_code(self, code, **kwargs):
            assert not kwargs["envs"] and kwargs["timeout"] == 20
            assert scenario != "network_mismatch"
            kwargs["on_stdout"](
                SimpleNamespace(line="x" * (9000 if scenario == "output_limit" else 2))
            )
            return SimpleNamespace(error=None)

        def kill(self, **kwargs):
            killed.append(True)
            return scenario != "cleanup_failed"

    def create(**kwargs):
        created.append(kwargs)
        return FakeSandbox()

    monkeypatch.setattr(Sandbox, "create", create)
    code = "print('synthetic fixture')"
    adapter = provider(configured(), events.append)
    if scenario == "completed":
        assert adapter.execute(code, permit(code)) == "xx"
    else:
        with pytest.raises(SandboxUnavailable):
            adapter.execute(code, permit(code))
    assert len(killed) == 1
    assert created[0]["allow_internet_access"] is False
    assert created[0]["envs"] == {}
    assert created[0]["network"]["allow_public_traffic"] is False
    assert events[0]["outcome"] == "requested"
    assert events[-1]["outcome"] == (
        "completed"
        if scenario == "completed"
        else "cleanup_unconfirmed"
        if scenario == "cleanup_failed"
        else "failed"
    )
    assert all(code not in str(event) and "synthetic-only" not in str(event) for event in events)


def test_audit_failure_prevents_remote_resource_creation(monkeypatch):
    monkeypatch.setattr(Sandbox, "create", lambda **kwargs: pytest.fail("must not create"))

    def unavailable(event):
        raise RuntimeError("synthetic_audit_unavailable")

    code = "print('synthetic fixture')"
    with pytest.raises(RuntimeError, match="synthetic_audit_unavailable"):
        provider(configured(), unavailable).execute(code, permit(code))
