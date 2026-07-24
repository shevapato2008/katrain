import os
import re
import subprocess
from math import isfinite
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "ucloud"
SENSITIVE = {"POSTGRES_PASSWORD", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "KATRAIN_SECRET_KEY"}
EXPECTED_ENV = {
    "POSTGRES_PASSWORD": "",
    "MINIO_ROOT_USER": "",
    "MINIO_ROOT_PASSWORD": "",
    "KATRAIN_SECRET_KEY": "",
    "KATRAIN_DB_NAME": "katrain_db",
    "KATRAIN_DB_USER": "katrain_user",
    "S3_BUCKET": "tutorial-assets",
    "WEB_IMAGE": "",
    "CRON_IMAGE": "",
    "KATAGO_IMAGE": "",
    "WG_BIND_IP": "",
    "MEDIA_PUBLIC_BASE_URL": "",
    "ALERT_EMAIL": "",
}
TEST_ENV = {
    "POSTGRES_PASSWORD": "test-only",
    "MINIO_ROOT_USER": "test-only",
    "MINIO_ROOT_PASSWORD": "test-only",
    "KATRAIN_SECRET_KEY": "test-only-not-production",
    "KATRAIN_DB_NAME": "katrain_db",
    "KATRAIN_DB_USER": "katrain_user",
    "S3_BUCKET": "tutorial-assets",
    "WEB_IMAGE": "sha256:" + "1" * 64,
    "CRON_IMAGE": "sha256:" + "2" * 64,
    "KATAGO_IMAGE": "sha256:" + "3" * 64,
    "WG_BIND_IP": "10.8.0.3",
    "MEDIA_PUBLIC_BASE_URL": "https://example.invalid/tutorial-assets",
    "ALERT_EMAIL": "nobody@example.invalid",
}

FORBIDDEN_RUNTIME_REQUIREMENTS = {
    "pytest",
    "playwright",
    "kivy",
    "kivymd",
    "ffpyplayer",
    "screeninfo",
    "cuda",
    "tensorrt",
}


def render_compose(production=False):
    command = ["docker", "compose", "-f", str(DEPLOY / "compose.yml")]
    if production:
        command += ["-f", str(DEPLOY / "compose.production.yml"), "--profile", "production"]
    command += ["config"]
    compose_env = {"PATH": os.environ["PATH"], **TEST_ENV}
    result = subprocess.run(command, env=compose_env, text=True, capture_output=True, check=True)
    return yaml.safe_load(result.stdout)


def test_env_example_names_required_secrets_but_leaves_values_empty():
    lines = [
        line
        for line in (DEPLOY / "env.example").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    entries = dict(line.split("=", 1) for line in lines)
    assert len(entries) == len(lines)
    assert entries == EXPECTED_ENV
    assert all(entries[name] == "" for name in SENSITIVE)


def test_compose_service_contract_and_bind_addresses():
    services = render_compose()["services"]
    assert set(services) == {"postgres", "minio", "minio-setup", "katrain-web", "katago-web", "katago-cron"}
    for name in ("postgres", "minio", "katrain-web", "katago-web", "katago-cron"):
        for port in services[name].get("ports", []):
            assert port.get("host_ip") in {"127.0.0.1", "10.8.0.3"}


def test_data_services_are_pinned_private_and_persistent():
    compose = render_compose()
    services = compose["services"]

    for name in ("postgres", "minio", "minio-setup"):
        assert re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", services[name]["image"])
    assert set(compose["volumes"]) >= {"postgres-data", "minio-data"}
    assert services["postgres"].get("ports", []) == []
    assert services["postgres"]["volumes"] == [
        {"type": "volume", "source": "postgres-data", "target": "/var/lib/postgresql/data", "volume": {}}
    ]
    assert services["minio"]["volumes"] == [
        {"type": "volume", "source": "minio-data", "target": "/data", "volume": {}}
    ]
    assert services["minio"]["ports"] == [
        {"mode": "ingress", "target": 9000, "published": "9000", "host_ip": "10.8.0.3", "protocol": "tcp"},
        {"mode": "ingress", "target": 9001, "published": "9001", "host_ip": "127.0.0.1", "protocol": "tcp"},
    ]


def test_data_service_credentials_urls_and_bootstrap_contract():
    services = render_compose()["services"]
    postgres = services["postgres"]
    minio = services["minio"]
    setup = services["minio-setup"]

    assert postgres["environment"] == {
        "POSTGRES_DB": "katrain_db",
        "POSTGRES_PASSWORD": "test-only",
        "POSTGRES_USER": "katrain_user",
    }
    assert minio["environment"] == {
        "MINIO_ROOT_PASSWORD": "test-only",
        "MINIO_ROOT_USER": "test-only",
    }
    assert setup["environment"]["MINIO_ENDPOINT"] == "http://minio:9000"
    assert setup["environment"]["S3_BUCKET"] == "tutorial-assets"
    assert setup["restart"] == "no"
    assert setup["depends_on"]["minio"]["condition"] == "service_healthy"
    assert setup["volumes"] == [{
        "type": "bind",
        "source": str(DEPLOY / "minio" / "bootstrap.sh"),
        "target": "/bootstrap.sh",
        "read_only": True,
        "bind": {},
    }]
    bootstrap = DEPLOY / "minio" / "bootstrap.sh"
    assert bootstrap.is_file() and os.access(bootstrap, os.X_OK)
    compose_text = (DEPLOY / "compose.yml").read_text()
    for name in ("POSTGRES_PASSWORD", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "WG_BIND_IP"):
        assert "${" + name + ":?" in compose_text

    bootstrap_text = bootstrap.read_text()
    assert "until mc alias set" in bootstrap_text
    assert "mc stat" in bootstrap_text and "mc mb" in bootstrap_text
    assert not re.search(r"anonymous|replicat|lifecycle|notify", bootstrap_text, re.IGNORECASE)


def test_production_adds_exactly_one_cron():
    preview = render_compose()["services"]
    production = render_compose(production=True)["services"]
    assert "katrain-cron" not in preview
    assert set(production) == set(preview) | {"katrain-cron"}
    assert preview["katrain-web"]["environment"]["KATRAIN_PREVIEW_MODE"] == "1"
    assert production["katrain-web"]["environment"]["KATRAIN_PREVIEW_MODE"] == "0"


def test_application_images_state_and_service_dns_contract():
    preview = render_compose()["services"]
    production = render_compose(production=True)["services"]
    immutable = re.compile(r"(?:[^\s]+@)?sha256:[0-9a-f]{64}")

    for name in ("katrain-web", "katago-web", "katago-cron"):
        assert immutable.fullmatch(preview[name]["image"])
    assert immutable.fullmatch(production["katrain-cron"]["image"])
    assert preview["katrain-web"]["user"] == "10001:10001"
    assert preview["katrain-web"]["environment"]["KATRAIN_DATABASE_URL"].endswith(
        "@postgres:5432/katrain_db"
    )
    assert preview["katrain-web"]["environment"]["LOCAL_KATAGO_URL"] == "http://katago-web:8000"
    assert production["katrain-cron"]["environment"]["KATAGO_URL"] == "http://katago-cron:8000"
    assert preview["katrain-web"]["volumes"] == [{
        "type": "volume",
        "source": "katrain-state-preview",
        "target": "/home/katrain/.katrain",
        "volume": {},
    }]
    assert production["katrain-web"]["volumes"] == [{
        "type": "volume",
        "source": "katrain-state-production",
        "target": "/home/katrain/.katrain",
        "volume": {},
    }]


def test_katago_services_preserve_proven_gpu_runtime_with_distinct_endpoints():
    services = render_compose()["services"]
    web = services["katago-web"]
    cron = services["katago-cron"]

    assert web["image"] == cron["image"]
    assert web["command"] == cron["command"] == ["python3", "-m", "realtime_api.main"]
    assert web["environment"]["KATAGO_CONFIG_FILE"] == "/app/config.yaml"
    assert cron["environment"]["KATAGO_CONFIG_FILE"] == "/app/config.yaml"
    assert {port["published"] for port in web["ports"]} == {"8000"}
    assert {port["published"] for port in cron["ports"]} == {"8002"}
    for service in (web, cron):
        reservations = service["deploy"]["resources"]["reservations"]["devices"]
        assert reservations == [{"driver": "nvidia", "count": 1, "capabilities": ["gpu"]}]


def test_long_running_services_have_health_restart_resource_and_log_limits():
    services = render_compose(production=True)["services"]
    for name in ("postgres", "minio", "katrain-web", "katrain-cron", "katago-web", "katago-cron"):
        service = services[name]
        assert service["restart"] == "unless-stopped"
        healthcheck = service["healthcheck"]
        assert healthcheck.get("disable") is not True
        healthcheck_test = healthcheck.get("test")
        assert healthcheck_test
        assert healthcheck_test[0] in {"CMD", "CMD-SHELL"}
        assert service["logging"]["options"] == {"max-size": "10m", "max-file": "5"}
        for limit in (service.get("mem_limit"), service.get("cpus")):
            assert not isinstance(limit, bool)
            normalized_limit = float(limit)
            assert isfinite(normalized_limit) and normalized_limit > 0


def test_web_dockerfile_has_exact_pinned_stages_and_pruned_copy_contract():
    dockerfile = (ROOT / "Dockerfile.web").read_text()
    from_lines = re.findall(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?$", dockerfile, re.MULTILINE | re.IGNORECASE)

    assert [stage.lower() for _, stage in from_lines] == [
        "ui-builder",
        "python-builder",
        "source-pruner",
        "runtime",
    ]
    assert all("@sha256:" in image for image, _ in from_lines)
    assert "nvcr.io" not in dockerfile.lower()
    assert "requirements-desktop" not in dockerfile
    assert not re.search(r"^COPY\s+\.\s+/app/?$", dockerfile, re.MULTILINE)
    assert re.search(r"COPY\s+--from=ui-builder\s+[^\n]*?/src/static\s+", dockerfile)
    assert "katrain.po" in dockerfile
    assert "katrain.mo" in dockerfile
    assert "polib" in dockerfile


def test_web_runtime_lock_declares_required_surface_without_desktop_or_test_packages():
    requirements = (ROOT / "requirements-web-runtime.in").read_text().lower()
    required = {
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-jose",
        "passlib",
        "bcrypt",
        "chardet",
        "polib",
        "beautifulsoup4",
        "lxml",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "sqlalchemy",
        "psycopg2-binary",
        "alembic",
        "edge-tts",
        "boto3",
        "pyserial",
        "docutils",
        "numpy",
        "opencv-python-headless",
    }

    declared = {
        re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]
        for line in requirements.splitlines()
        if line and not line.startswith("#")
    }
    assert required <= declared
    assert not (FORBIDDEN_RUNTIME_REQUIREMENTS & declared)


def test_dockerignore_excludes_runtime_build_noise_at_any_depth():
    patterns = set((ROOT / ".dockerignore").read_text().splitlines())

    assert {".venv", "node_modules", "**/node_modules", ".postgres_data", "data", "tests"} <= patterns
    assert {"screenshots", "test-results", "*.dump", "*.tar", "*.tar.gz"} <= patterns


def test_web_build_script_enforces_size_and_runtime_gates_without_shell_trace():
    script = (DEPLOY / "scripts" / "build-web.sh").read_text()

    assert "5000000000" in script
    assert "set -x" not in script
    assert "docker build" in script
    assert "httpx" in script and "cv2" in script and "numpy" in script
    assert "fastapi" in script and "sqlalchemy" in script and "boto3" in script
    assert "katrain.web.server" in script
    assert "katrain.mo" in script
    assert "HOME=/home/katrain" in script
    assert "PlatformCredentialStore" in script
    assert "RepoDigests" not in script
