"""E2B boundary, not an exposed tool. Code-specific approval is mandatory for future callers."""

import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from orqentra.core.config import Settings


class SandboxUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovedCode:
    organization_id: UUID
    run_id: UUID
    approval_id: UUID
    code_hash: str
    expires_at: datetime


class SandboxProvider(Protocol):
    def execute(self, code: str, permit: ApprovedCode) -> str: ...


class DisabledSandbox:
    def execute(self, code: str, permit: ApprovedCode) -> str:
        raise SandboxUnavailable("sandbox_disabled")


class E2BSandbox:
    def __init__(self, settings: Settings, audit: Callable[[dict[str, str]], None]):
        self.settings, self.audit = settings, audit

    def execute(self, code: str, permit: ApprovedCode) -> str:
        config = self.settings
        # Account configuration alone must never create a paid resource.
        if not (
            config.sandbox_execution_approved and config.e2b_api_key and config.e2b_template_id
        ):
            raise SandboxUnavailable("sandbox_not_authorized_or_configured")
        if (
            not code.strip()
            or len(code.encode()) > 16384
            or permit.expires_at <= datetime.now(UTC)
            or hashlib.sha256(code.encode()).hexdigest() != permit.code_hash
        ):
            raise SandboxUnavailable("sandbox_approval_mismatch")
        from e2b_code_interpreter import Sandbox  # type: ignore[import-untyped]

        logger = logging.getLogger("orqentra.sandbox.transport")
        logger.disabled = True
        logger.propagate = False
        metadata = {
            "organization_id": str(permit.organization_id),
            "run_id": str(permit.run_id),
            "approval_id": str(permit.approval_id),
            "code_hash": permit.code_hash,
        }
        # Audit failure denies execution before any resource is created.
        self.audit({**metadata, "outcome": "requested"})
        sandbox: Any = None
        outcome = "failed"
        output: list[str] = []
        size = 0

        def capture(message: Any) -> None:
            nonlocal size
            line = str(message.line)
            size += len(line.encode())
            if size > 8192:
                raise SandboxUnavailable("sandbox_output_limit")
            output.append(line)

        def no_rich_results(result: Any) -> None:
            raise SandboxUnavailable("sandbox_rich_result_disabled")

        try:
            sandbox = Sandbox.create(
                template=config.e2b_template_id,
                timeout=60,
                envs={},
                metadata=metadata,
                api_key=config.e2b_api_key.get_secret_value(),
                allow_internet_access=False,
                network={
                    "deny_out": ["0.0.0.0/0", "::/0"],
                    "allow_out": [],
                    "allow_public_traffic": False,
                },
                lifecycle={"on_timeout": "kill"},
                request_timeout=10,
                logger=logger,
                idempotency_key=str(permit.approval_id),
            )
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", sandbox.sandbox_id):
                raise SandboxUnavailable("sandbox_reference_invalid")
            self.audit({**metadata, "outcome": "created", "sandbox_id": sandbox.sandbox_id})
            info = sandbox.get_info(request_timeout=10)
            network = info.network
            if (
                info.template_id != config.e2b_template_id
                or not 0 < info.cpu_count <= 2
                or not 0 < info.memory_mb <= 1024
                or info.allow_internet_access is not False
                or network is None
                or network.allow_public_traffic
                or network.allow_out
                or not {"0.0.0.0/0", "::/0"}.issubset(network.deny_out)
                or info.volume_mounts
            ):
                raise SandboxUnavailable("sandbox_policy_not_attested")
            result = sandbox.run_code(
                code,
                language="python",
                envs={},
                timeout=20,
                request_timeout=25,
                on_stdout=capture,
                on_stderr=capture,
                on_result=no_rich_results,
            )
            if result.error:
                raise SandboxUnavailable("sandbox_code_failed")
            outcome = "completed"
        except Exception:
            # No provider exception text, code or output in logs/errors.
            raise SandboxUnavailable("sandbox_execution_failed") from None
        finally:
            try:
                if sandbox is not None and not sandbox.kill(request_timeout=10):
                    raise SandboxUnavailable("sandbox_cleanup_unconfirmed")
            except Exception:
                outcome = "cleanup_unconfirmed"
                raise SandboxUnavailable("sandbox_cleanup_unconfirmed") from None
            finally:
                self.audit({**metadata, "outcome": outcome})
        return "".join(output)


def provider(settings: Settings, audit: Callable[[dict[str, str]], None]) -> SandboxProvider:
    return E2BSandbox(settings, audit) if settings.sandbox_provider == "e2b" else DisabledSandbox()
