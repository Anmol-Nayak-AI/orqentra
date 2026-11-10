"""Provisioning boundary tests use only a synthetic control-plane transport."""

import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest
import yaml

spec = importlib.util.spec_from_file_location(
    "free_preview", Path(__file__).resolve().parents[3] / "scripts/deploy_free_preview.py"
)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def setup_job(tmp_path, monkeypatch, *, paid=False):
    config = yaml.safe_load(
        (
            Path(__file__).resolve().parents[3] / "infrastructure/render/free-preview.yaml"
        ).read_text()
    )
    if paid:
        config["services"][0]["plan"] = "0.5c-512mb"
    target = tmp_path / "infrastructure/render"
    target.mkdir(parents=True)
    (target / "free-preview.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setattr(preview, "ROOT", tmp_path)
    monkeypatch.setattr(preview, "STATE", tmp_path / ".local/attempt.json")
    monkeypatch.setenv("RENDER_API_KEY", "synthetic-only")
    monkeypatch.setattr(
        "sys.argv", ["deploy_free_preview.py", "deploy", "--owner", "tea_synthetic"]
    )


def test_free_preview_refuses_paid_plan_before_contacting_provider(tmp_path, monkeypatch):
    setup_job(tmp_path, monkeypatch, paid=True)

    class NoNetwork:
        def open(self, *args, **kwargs):
            pytest.fail("A paid plan must be rejected before network access")

    monkeypatch.setattr(preview.urllib.request, "build_opener", lambda *_: NoNetwork())
    with pytest.raises(preview.PreviewError, match="paid"):
        preview.main()


def test_uncertain_creation_is_durable_and_is_never_automatically_reissued(tmp_path, monkeypatch):
    setup_job(tmp_path, monkeypatch)
    posts = []

    class SyntheticControlPlane:
        def open(self, request, **kwargs):
            if request.method == "POST":
                posts.append(json.loads(request.data))
                raise urllib.error.URLError("synthetic ambiguous timeout")
            data = [{"owner": {"id": "tea_synthetic"}}] if "owners?" in request.full_url else []
            return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(preview.urllib.request, "build_opener", lambda *_: SyntheticControlPlane())
    with pytest.raises(urllib.error.URLError):
        preview.main()
    assert json.loads(preview.STATE.read_text())["status"] == "CREATING"
    with pytest.raises(preview.PreviewError, match="creation attempt"):
        preview.main()
    assert len(posts) == 1
    assert posts[0]["type"] == "static_site"
    assert posts[0]["autoDeployTrigger"] == "off"
    assert "synthetic-only" not in str(posts[0])
