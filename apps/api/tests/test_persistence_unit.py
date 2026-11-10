import pytest

from orqentra.core.config import Settings
from orqentra.persistence.repositories import normalized_slug, validated_configuration
from orqentra.persistence.session import database_engine


def test_slug_normalization() -> None:
    assert normalized_slug("  Customer Onboarding / Team  ") == "customer-onboarding-team"


@pytest.mark.parametrize("value", ["", "!!!", "a" * 101])
def test_invalid_slug(value: str) -> None:
    with pytest.raises(ValueError):
        normalized_slug(value)


def test_configuration_snapshot_is_detached() -> None:
    original = {"nested": {"allowed": ["knowledge.search"]}}
    snapshot = validated_configuration(original)
    original["nested"]["allowed"].append("unexpected")
    assert snapshot["nested"]["allowed"] == ["knowledge.search"]


@pytest.mark.parametrize("value", [{"too_large": "x" * 65536}, {"bad_number": float("nan")}])
def test_configuration_bounds(value: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validated_configuration(value)


def test_rejects_sqlite_substitute() -> None:
    with pytest.raises(ValueError):
        database_engine("sqlite://")


def test_database_secret_redaction() -> None:
    config = Settings(database_url="postgresql+psycopg://user:private-canary@localhost/db")
    assert "private-canary" not in repr(config)
