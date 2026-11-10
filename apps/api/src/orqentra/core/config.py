import re
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """Explicit environment only; secrets/config files are never auto-discovered."""

    model_config = SettingsConfigDict(
        env_prefix="ORQENTRA_",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
        hide_input_in_errors=True,
    )
    environment: Literal["development", "test", "staging", "production"] = "development"

    allowed_hosts: str = ""

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    max_request_bytes: int = Field(default=65536, ge=1024, le=1048576)
    tracing_endpoint: str | None = None

    @model_validator(mode="after")
    def validate_tracing(self) -> "Settings":
        if self.tracing_endpoint:
            parsed = urlsplit(self.tracing_endpoint)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path != "/v1/traces"
            ):
                raise ValueError("Tracing requires a private HTTPS collector /v1/traces endpoint.")
        return self

    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    billing_provider: Literal["disabled", "razorpay"] = "disabled"
    billing_test_actions_enabled: bool = False
    billing_test_total_cycles: int = Field(default=12, ge=1, le=120)
    razorpay_key_id: SecretStr | None = Field(default=None, validation_alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: SecretStr | None = Field(
        default=None, validation_alias="RAZORPAY_KEY_SECRET"
    )
    razorpay_webhook_secret: SecretStr | None = Field(
        default=None, validation_alias="RAZORPAY_WEBHOOK_SECRET"
    )
    razorpay_previous_webhook_secret: SecretStr | None = Field(
        default=None, validation_alias="RAZORPAY_PREVIOUS_WEBHOOK_SECRET"
    )
    razorpay_previous_webhook_secret_expires_at: datetime | None = Field(
        default=None, validation_alias="RAZORPAY_PREVIOUS_WEBHOOK_SECRET_EXPIRES_AT"
    )
    razorpay_plan_ids: dict[str, str] = Field(default_factory=dict)

    sandbox_provider: Literal["disabled", "e2b"] = "disabled"
    sandbox_execution_approved: bool = False
    sandbox_max_concurrent_per_organization: int = Field(default=1, ge=1, le=2)
    e2b_api_key: SecretStr | None = Field(default=None, validation_alias="E2B_API_KEY")
    e2b_template_id: str | None = None

    database_url: SecretStr | None = None
    migration_database_url: SecretStr | None = None

    clerk_issuer: str | None = Field(default=None, validation_alias="CLERK_ISSUER")
    clerk_jwt_key: SecretStr | None = Field(default=None, validation_alias="CLERK_JWT_KEY")
    clerk_allowed_origins: str = Field(default="", validation_alias="CLERK_ALLOWED_ORIGINS")
    clerk_audience: str | None = Field(default=None, validation_alias="CLERK_AUDIENCE")
    clerk_max_token_lifetime: int = Field(default=300, ge=30, le=3600)

    @property
    def allowed_origins(self) -> list[str]:
        return [part.strip() for part in self.clerk_allowed_origins.split(",") if part.strip()]

    @property
    def auth_configured(self) -> bool:
        return bool(self.clerk_issuer and self.clerk_jwt_key and self.allowed_origins)

    @model_validator(mode="after")
    def validate_auth(self) -> "Settings":
        if (
            any([self.clerk_issuer, self.clerk_jwt_key, self.allowed_origins])
            and not self.auth_configured
        ):
            raise ValueError(
                "Configure Clerk issuer, public signing key and allowed origins together."
            )
        if self.clerk_issuer and (
            not self.clerk_issuer.startswith("https://") or "?" in self.clerk_issuer
        ):
            raise ValueError("Clerk issuer must be an exact HTTPS origin.")
        if self.clerk_issuer:
            parsed = urlsplit(self.clerk_issuer)
            if (
                not parsed.hostname
                or parsed.username
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Clerk issuer must be an exact HTTPS origin without a path.")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("Allowed frontend origins must be exact HTTP(S) origins.")
        if self.clerk_jwt_key:
            try:
                key = load_pem_public_key(
                    self.clerk_jwt_key.get_secret_value().replace("\\n", "\n").encode()
                )
            except ValueError:
                raise ValueError("Configure a valid Clerk RSA public signing key.") from None
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError("Clerk signing key must be RSA, at least 2048 bits.")
        if self.sandbox_execution_approved and (
            self.sandbox_provider != "e2b" or not self.e2b_api_key or not self.e2b_template_id
        ):
            raise ValueError("Sandbox authorization requires an E2B key and reviewed template ID.")
        if self.razorpay_key_id and not self.razorpay_key_id.get_secret_value().startswith(
            "rzp_test_"
        ):
            raise ValueError("Only Razorpay test credentials are authorized.")
        if self.billing_provider == "razorpay" and not all(
            [self.razorpay_key_id, self.razorpay_key_secret, self.razorpay_webhook_secret]
        ):
            raise ValueError(
                "Razorpay test mode requires its key, API secret and webhook secret together."
            )
        if self.razorpay_previous_webhook_secret:
            expiry = self.razorpay_previous_webhook_secret_expires_at
            if (
                expiry is None
                or expiry.tzinfo is None
                or expiry > datetime.now(UTC) + timedelta(days=2)
            ):
                raise ValueError(
                    "Previous webhook secrets need a timezone-aware expiry within two days."
                )
        elif self.razorpay_previous_webhook_secret_expires_at is not None:
            raise ValueError("A webhook rotation expiry requires a previous secret.")
        if self.billing_test_actions_enabled and self.billing_provider != "razorpay":
            raise ValueError("Test billing actions require a configured test provider.")
        if self.billing_provider == "razorpay" and self.environment == "production":
            raise ValueError("Commercial payments remain disabled in production.")
        if self.environment in {"staging", "production"}:
            if not self.trusted_hosts or any(
                not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host)
                for host in self.trusted_hosts
            ):
                raise ValueError(
                    "Production requires explicit literal allowed hosts without wildcards."
                )
            if (
                self.environment == "production"
                and self.clerk_issuer
                and (urlsplit(self.clerk_issuer).hostname or "").endswith(".clerk.accounts.dev")
            ):
                raise ValueError("Production cannot use a Clerk development instance.")
            if self.clerk_max_token_lifetime > 300:
                raise ValueError("Production session token lifetime cannot exceed five minutes.")
            if not self.auth_configured or not self.database_url:
                raise ValueError(
                    "Production requires authentication configuration and a runtime database URL."
                )
            if self.migration_database_url:
                raise ValueError(
                    "Migration credentials must not be supplied to the production API."
                )
            if any(not origin.startswith("https://") for origin in self.allowed_origins):
                raise ValueError("Production frontend origins must use HTTPS.")
            for origin in self.allowed_origins:
                hostname = urlsplit(origin).hostname or ""
                if hostname == "localhost" or hostname.endswith(".localhost"):
                    raise ValueError("Production cannot use localhost frontend origins.")
                try:
                    address = ip_address(hostname)
                except ValueError:
                    continue
                if not address.is_global:
                    raise ValueError("Production cannot use local frontend IP addresses.")
            try:
                database = make_url(self.database_url.get_secret_value())
                if (
                    database.get_backend_name() != "postgresql"
                    or database.query.get("sslmode") != "verify-full"
                ):
                    raise ValueError
            except Exception:
                raise ValueError(
                    "Production PostgreSQL requires certificate-verified TLS (sslmode=verify-full)."
                ) from None
        return self
