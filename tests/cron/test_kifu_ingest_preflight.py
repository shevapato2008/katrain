"""Enabled hourly admission rejects incomplete publishing configuration first."""

import asyncio

import pytest

from katrain.cron.jobs import kifu_ingest as job


@pytest.fixture
def configured(tmp_path, monkeypatch):
    key, hosts = tmp_path / "key", tmp_path / "known_hosts"
    key.write_text("fixture")
    hosts.write_text("fixture")
    for name, value in {
        "KIFU_INGEST_ENABLED": True,
        "KIFU_INGEST_LLM_ENABLED": False,
        "KIFU_INGEST_SSH_HOST": "fixture@example.invalid",
        "KIFU_INGEST_SSH_KEY": str(key),
        "KIFU_INGEST_KNOWN_HOSTS": str(hosts),
        "KIFU_INGEST_TEST_API_URL": "http://test.example.invalid",
        "KIFU_INGEST_PROD_API_URL": "https://prod.example.invalid",
    }.items():
        monkeypatch.setattr(job.config, name, value)
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "enabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "elasticsearch")
    monkeypatch.setenv("KIFU_ES_URL", "https://es.example.invalid")
    monkeypatch.setenv("KIFU_ES_WRITER_API_KEY", "private-fixture-key")
    monkeypatch.delenv("KIFU_ES_CA_CERT", raising=False)
    monkeypatch.delenv("KIFU_ES_WRITER_USERNAME", raising=False)
    monkeypatch.delenv("KIFU_ES_WRITER_PASSWORD", raising=False)


@pytest.mark.parametrize("entry", ["_run_lock", "_run_locked"])
@pytest.mark.parametrize(
    "fault", ["sync", "writer", "host", "relative_key", "missing_key", "known_hosts", "test_url", "prod_url"]
)
def test_enabled_job_rejects_missing_config_before_any_work(configured, monkeypatch, entry, fault):
    if fault == "sync":
        monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
        monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    elif fault == "writer":
        monkeypatch.delenv("KIFU_ES_WRITER_API_KEY")
    elif fault == "host":
        monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_HOST", "")
    elif fault == "relative_key":
        monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_KEY", "relative.key")
    elif fault == "missing_key":
        monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_KEY", job.config.KIFU_INGEST_SSH_KEY + ".missing")
    elif fault == "known_hosts":
        monkeypatch.setattr(job.config, "KIFU_INGEST_KNOWN_HOSTS", job.config.KIFU_INGEST_KNOWN_HOSTS + ".missing")
    elif fault == "test_url":
        monkeypatch.setattr(job.config, "KIFU_INGEST_TEST_API_URL", "")
    else:
        monkeypatch.setattr(job.config, "KIFU_INGEST_PROD_API_URL", "ftp://private-fixture-key@invalid")

    def forbidden(*args, **kwargs):
        pytest.fail("configuration admission reached state, network, paid calls or writers")

    for name in ("_session_lock", "Stage", "StateStore", "discover_recent", "QwenNameService", "publish_manifest"):
        monkeypatch.setattr(job, name, forbidden)
    instance = job.KifuIngestJob()
    with pytest.raises(ValueError, match="kifu_ingest_preflight") as error:
        if entry == "_run_lock":
            instance._run_lock()
        else:
            asyncio.run(instance._run_locked())
    assert "private-fixture-key" not in str(error.value)
    assert "example.invalid" not in str(error.value)


def test_complete_config_allows_free_name_path_without_mutating_flags(configured):
    job._publication_preflight()
    assert job.config.KIFU_INGEST_ENABLED is True
    assert job.config.KIFU_INGEST_LLM_ENABLED is False


def test_disabled_configuration_preserves_legacy_admission(configured, monkeypatch):
    monkeypatch.setattr(job.config, "KIFU_INGEST_ENABLED", False)
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_HOST", "")
    job._publication_preflight()
