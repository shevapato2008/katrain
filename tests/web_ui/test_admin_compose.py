"""Admin service identity stays scoped; default legacy launch is preserved."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def compose(**values):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI unavailable")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KATRAIN_", "COMPOSE_"))}
    env.update(KATRAIN_SECRET_KEY="compose-test-player-key-" + "x" * 40, **values)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "--profile",
            "admin",
            "-f",
            str(ROOT / "docker-compose.yml"),
            "config",
            "--format",
            "json",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"]


def test_legacy_compose_admin_defaults_are_preserved():
    services = compose()
    admin = services["katrain-admin"]
    assert admin["image"] == "katrain-web:local"
    assert admin["command"] == ["python3", "-m", "katrain.web.admin"]
    assert admin["environment"]["KATRAIN_ADMIN_SERVICE_SECRET"] == ""
    assert admin["environment"]["KATRAIN_ADMIN_PROVIDER_ONLY"] == "0"
    assert admin["ports"][0]["host_ip"] == "127.0.0.1"
    assert admin["ports"][0]["published"] == "8010"
    assert admin["ports"][0]["target"] == 8010


def test_provider_credentials_only_reach_admin_and_host_port_can_move():
    key = "compose-test-service-key-" + "s" * 40
    services = compose(
        KATRAIN_ADMIN_SERVICE_SECRET=key, KATRAIN_ADMIN_PROVIDER_ONLY="1", KATRAIN_ADMIN_HOST_PORT="18010"
    )
    admin = services["katrain-admin"]
    assert admin["environment"]["KATRAIN_ADMIN_SERVICE_SECRET"] == key
    assert admin["environment"]["KATRAIN_ADMIN_PROVIDER_ONLY"] == "1"
    assert admin["ports"][0]["published"] == "18010"
    assert admin["ports"][0]["target"] == 8010
    assert admin["ports"][0]["host_ip"] == "127.0.0.1"
    for name, service in services.items():
        if name != "katrain-admin":
            assert not any(k.startswith("KATRAIN_ADMIN_") for k in service.get("environment", {})), name
