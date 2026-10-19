import asyncio
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, update


def test_daily_token_ledger_reservations_survive_restart_and_settle(tmp_path):
    from katrain.cron.jobs.kifu_ingest import DailyTokenLedger
    from katrain.kifu_ingest.staging import Stage

    path = tmp_path / "qwen-usage-20261019.json"
    first = DailyTokenLedger(path, 5000, Stage._atomic)
    reservation = first.reserve(4000)
    restarted = DailyTokenLedger(path, 5000, Stage._atomic)
    assert restarted.spent() == 4000
    from katrain.kifu_ingest.names import NameServiceError

    with pytest.raises(NameServiceError, match="token budget"):
        restarted.reserve(1001)
    assert restarted.settle(reservation, 500) == 500
    assert DailyTokenLedger(path, 5000, Stage._atomic).spent() == 500
    abandoned = restarted.reserve(3000)
    assert abandoned != reservation
    assert DailyTokenLedger(path, 5000, Stage._atomic).spent() == 3500
    assert path.with_suffix(".lock").exists()


def test_daily_budget_routes_midnight_reservation_to_correct_day(tmp_path):
    from katrain.cron.jobs.kifu_ingest import DailyTokenBudget, DailyTokenLedger
    from katrain.kifu_ingest.staging import Stage

    now = [datetime(2026, 10, 19, 23, 59, tzinfo=timezone.utc)]
    budget = DailyTokenBudget(tmp_path, 5000, Stage._atomic, clock=lambda: now[0])
    yesterday = budget.reserve(4000)
    now[0] = datetime(2026, 10, 20, 0, 1, tzinfo=timezone.utc)
    today = budget.reserve(4000)
    assert yesterday != today
    assert budget.settle(yesterday, 500) == 4000
    assert DailyTokenLedger(tmp_path / "qwen-usage-20261019.json", 5000, Stage._atomic).spent() == 500
    assert budget.spent() == 4000


def test_incremental_job_defaults_to_disabled_and_hourly(monkeypatch):
    import importlib
    from katrain.cron import config

    monkeypatch.delenv("CRON_KIFU_INGEST_ENABLED", raising=False)
    monkeypatch.delenv("CRON_KIFU_INGEST_LLM_ENABLED", raising=False)
    monkeypatch.delenv("CRON_KIFU_INGEST_MAX_TOKENS", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.KIFU_INGEST_ENABLED is False
    assert reloaded.KIFU_INGEST_LLM_ENABLED is False
    assert reloaded.KIFU_INGEST_MAX_TOKENS == 0
    assert reloaded.KIFU_INGEST_INTERVAL == 3600


def test_staged_grouping_only_batches_when_review_budget_is_enabled():
    from katrain.cron.jobs.kifu_ingest import group_staged_items

    items = [{"external_id": str(i)} for i in range(3)]
    assert group_staged_items(items, review_enabled=True) == [items]
    assert group_staged_items(items, review_enabled=False) == [[item] for item in items]


def test_review_batch_selects_at_most_budgeted_distinct_names_before_paid_calls():
    from katrain.cron.jobs.kifu_ingest import select_review_items

    records = []
    for source_id, black in (("1", "Alice"), ("2", "Alice"), ("3", "Bob"), ("4", "Carol")):
        records.append(
            (
                {"external_id": source_id},
                {"metadata": {"player_black": black, "player_white": "White", "event": "Match"}},
            )
        )
    resolved = {
        "player": {name: {"status": "unresolved"} for name in ("Alice", "Bob", "Carol")}
        | {"White": {"status": "qualified", "canonical_name": "White"}},
        "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
    }
    chosen, deferred = select_review_items(records, resolved, reusable_events=set(), max_new_names=2)
    assert [item["external_id"] for item in chosen] == ["1", "2", "3"]
    assert [item["external_id"] for item in deferred] == ["4"]


def test_review_batch_isolates_ambiguous_identity_before_name_budget():
    from katrain.cron.jobs.kifu_ingest import select_review_items

    records = [
        ({"external_id": "1"}, {"metadata": {"player_black": "Ambiguous", "player_white": "White", "event": "Match"}}),
        ({"external_id": "2"}, {"metadata": {"player_black": "Alice", "player_white": "White", "event": "Match"}}),
    ]
    resolved = {
        "player": {
            "Ambiguous": {"status": "ambiguous"},
            "Alice": {"status": "unresolved"},
            "White": {"status": "qualified", "canonical_name": "White"},
        },
        "event": {"Match": {"status": "qualified", "canonical_name": "Match"}},
    }
    isolated = []
    chosen, deferred = select_review_items(
        records,
        resolved,
        reusable_events=set(),
        max_new_names=1,
        isolated=isolated,
    )
    assert [item["external_id"] for item in chosen] == ["2"]
    assert deferred == []
    assert isolated == [("1", "ambiguous player identity requires review")]


def test_sync_refuses_unverified_package(monkeypatch):
    from katrain.kifu_ingest.sync import send_verified_manifest

    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("SSH should not run"))
    with pytest.raises(ValueError, match="test verification"):
        send_verified_manifest({}, "0" * 64, {}, host="prod", key_path="/key", known_hosts="/hosts")


def test_sync_uses_fixed_ssh_command_and_stdin(monkeypatch):
    from katrain.kifu_ingest.sync import send_verified_manifest

    manifest = {
        "format": "kifu-incremental-manifest-v1",
        "publication_key": "batch-1",
        "games": [{"source_key": "19x19", "source_item_id": "1"}],
    }
    from katrain.web.kifu.name_candidates import canonical_sha256

    digest = canonical_sha256(manifest)
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(args=args, **kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "applied", "manifest_sha256": digest, "receipt": {"games": []}}),
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    result = send_verified_manifest(
        manifest,
        digest,
        {
            "status": "verified",
            "manifest_sha256": digest,
            "games": 1,
            "checks": [{"album_id": 7, "lang": lang} for lang in ("cn", "tw", "jp", "ko", "en")],
        },
        host="prod.example",
        key_path="/run/secrets/key",
        known_hosts="/run/secrets/hosts",
    )
    assert result["status"] == "applied"
    assert captured["args"] == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "UserKnownHostsFile=/run/secrets/hosts",
        "-i",
        "/run/secrets/key",
        "--",
        "prod.example",
        "kifu-incremental-receive",
    ]
    assert json.loads(captured["input"])["manifest"] == manifest


@pytest.mark.asyncio
async def test_verifier_checks_real_sgf_and_all_five_display_fields():
    from katrain.kifu_ingest.sync import verify_album_api

    sgf = "(;PB[B]PW[W]EV[E];B[aa])"
    album = {
        "id": 7,
        "sgf_content": sgf,
        "player_black": "B",
        "player_white": "W",
        "event": "E",
        "display_player_black": "Black",
        "display_player_white": "White",
        "display_event": "Event",
        "sources": ["19x19"],
    }

    class Client:
        async def get(self, url, *, params, timeout):
            if url.endswith("/albums"):
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {
                        "items": [
                            {
                                "id": 7,
                                "display_player_black": "Black",
                                "display_player_white": "White",
                                "display_event": "Event",
                            }
                        ],
                        "total": 1,
                    },
                )
            return SimpleNamespace(status_code=200, json=lambda: album)

    game = {
        "source_key": "19x19",
        "source_item_id": "1",
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "metadata": {"player_black": "B", "player_white": "W", "event": "E"},
    }
    receipt = {"games": [{"source_key": "19x19", "source_item_id": "1", "album_id": 7}]}
    result = await verify_album_api(Client(), "https://example", [game], receipt)
    assert result["status"] == "verified"

    album["display_event"] = ""
    with pytest.raises(ValueError, match="display_event"):
        await verify_album_api(Client(), "https://example", [game], receipt)

    album["display_event"] = "Different"
    with pytest.raises(ValueError, match="public list card"):
        await verify_album_api(Client(), "https://example", [game], receipt)


@pytest.mark.asyncio
async def test_verifier_requires_album_in_public_list():
    from katrain.kifu_ingest.sync import verify_album_api

    sgf = "(;PB[Alice]PW[Bob]EV[Event]DT[2026-03-01];B[aa])"
    album = {
        "id": 7,
        "sgf_content": sgf,
        "player_black": "Alice",
        "player_white": "Bob",
        "event": "Event",
        "display_player_black": "Alice",
        "display_player_white": "Bob",
        "display_event": "Event",
        "sources": ["19x19"],
    }

    class Client:
        async def get(self, url, *, params, timeout):
            if url.endswith("/albums"):
                return SimpleNamespace(
                    status_code=200, json=lambda: {"items": [], "total": 0, "page": 1, "page_size": 100}
                )
            return SimpleNamespace(status_code=200, json=lambda: album)

    game = {
        "source_key": "19x19",
        "source_item_id": "1",
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "metadata": {"player_black": "Alice", "player_white": "Bob", "event": "Event", "date_played": "2026-03-01"},
    }
    receipt = {"games": [{"source_key": "19x19", "source_item_id": "1", "album_id": 7}]}
    with pytest.raises(ValueError, match="public list"):
        await verify_album_api(Client(), "https://example", [game], receipt)


@pytest.mark.asyncio
async def test_verifier_compares_reviewed_display_values_not_just_presence():
    from katrain.kifu_ingest.sync import verify_album_api

    sgf = "(;PB[Alice]PW[Bob]EV[Match];B[aa])"
    album = {
        "id": 7,
        "sgf_content": sgf,
        "player_black": "Alice",
        "player_white": "Bob",
        "event": "Match",
        "display_player_black": "Wrong",
        "display_player_white": "Bob",
        "display_event": "Match",
        "sources": ["19x19"],
    }

    class Client:
        async def get(self, url, *, params, timeout):
            if url.endswith("/albums"):
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {
                        "items": [
                            {
                                "id": 7,
                                "display_player_black": "Alice",
                                "display_player_white": "Bob",
                                "display_event": "Match",
                            }
                        ],
                        "total": 1,
                    },
                )
            return SimpleNamespace(status_code=200, json=lambda: album)

    game = {
        "source_key": "19x19",
        "source_item_id": "1",
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "metadata": {"player_black": "Alice", "player_white": "Bob", "event": "Match"},
        "identities": {"black": None, "white": None, "event": None},
    }
    manifest = {
        "games": [game],
        "decisions": [
            {
                "kind": "raw_player",
                "key": "Alice",
                "displays": {lang: "Alice" for lang in ("cn", "tw", "jp", "ko", "en")},
            }
        ],
    }
    receipt = {"games": [{"source_key": "19x19", "source_item_id": "1", "album_id": 7}]}
    with pytest.raises(ValueError, match="display_player_black mismatch"):
        await verify_album_api(Client(), "https://example", manifest, receipt)


@pytest.mark.asyncio
async def test_resume_verifies_test_before_sync_and_retries_verification_only():
    from katrain.cron.jobs.kifu_ingest import resume_batch

    manifest = {"publication_key": "batch-1", "games": [{"source_key": "19x19", "source_item_id": "1"}]}
    digest = "a" * 64
    receipt = {"games": [{"source_key": "19x19", "source_item_id": "1", "album_id": 3}]}

    class Store:
        row = {"status": "test_published", "test_receipt": receipt}

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, receipt):
            assert self.row["status"] == expected_status
            self.row["status"] = status
            self.row[
                {
                    "test_verified": "test_verification",
                    "prod_published": "prod_receipt",
                    "prod_synced": "prod_verification",
                }[status]
            ] = receipt
            return self.row

    store = Store()
    calls = []

    async def test_verify(*args):
        calls.append("test_verify")
        raise TimeoutError("API timeout")

    async def prod_verify(*args):
        calls.append("prod_verify")

    async def sync(*args):
        calls.append("sync")

    with pytest.raises(TimeoutError):
        await resume_batch(store, manifest, digest, test_verify=test_verify, sync=sync, prod_verify=prod_verify)
    assert store.row["status"] == "test_published"
    assert calls == ["test_verify"]

    async def test_verified(*args):
        calls.append("test_verify")
        return {"status": "verified", "manifest_sha256": digest}

    async def synced(*args):
        calls.append("sync")
        return {
            "status": "applied",
            "manifest_sha256": digest,
            "receipt": {"games": [{"source_key": "19x19", "source_item_id": "1", "album_id": 99}]},
        }

    async def prod_verified(*args):
        calls.append("prod_verify")
        return {"status": "verified", "manifest_sha256": digest}

    await resume_batch(store, manifest, digest, test_verify=test_verified, sync=synced, prod_verify=prod_verified)
    assert calls == ["test_verify", "test_verify", "sync", "prod_verify"]
    assert store.row["status"] == "prod_synced"


def test_frozen_manifest_registration_advances_only_validated_package():
    from katrain.cron.jobs.kifu_ingest import register_frozen_batch

    class Store:
        def __init__(self):
            self.row = {"status": "discovered", "manifest_sha256": "a" * 64}
            self.steps = []

        def register_batch(self, key, digest):
            self.steps.append("register")
            return self.row

        def advance_batch(self, key, status, *, expected_status):
            assert expected_status == self.row["status"]
            self.steps.append(status)
            self.row["status"] = status
            return self.row

    store = Store()
    register_frozen_batch(store, "batch-1", "a" * 64)
    assert store.steps == ["register", "downloaded", "parsed", "names_ready"]
    store.steps.clear()
    register_frozen_batch(store, "batch-1", "a" * 64)
    assert store.steps == ["register"]
    store.row["status"] = "parsed"
    store.steps.clear()
    register_frozen_batch(store, "batch-1", "a" * 64)
    assert store.steps == ["register", "names_ready"]


@pytest.mark.asyncio
async def test_failed_package_records_phase_and_continues_to_next_package():
    from katrain.cron.jobs.kifu_ingest import process_package_queue

    class Store:
        def __init__(self):
            self.rows = {
                "one": {"status": "test_published", "attempts": 0},
                "two": {"status": "names_ready", "attempts": 0},
            }
            self.failures = []

        def get_batch(self, key):
            return self.rows[key]

        def advance_batch(self, key, status, *, expected_status, error=None, next_retry_at=None):
            assert self.rows[key]["status"] == expected_status
            self.rows[key].update(status=status, resume_phase=expected_status, error=error, next_retry_at=next_retry_at)
            self.failures.append((key, status, error))
            return self.rows[key]

    store = Store()
    processed = []

    async def process(manifest):
        processed.append(manifest["publication_key"])
        if manifest["publication_key"] == "one":
            raise TimeoutError("TEST API timed out")

    failures = await process_package_queue(
        store,
        [{"publication_key": "one"}, {"publication_key": "two"}],
        process,
        now=datetime(2026, 10, 19, tzinfo=timezone.utc),
    )
    assert processed == ["one", "two"]
    assert failures == 1
    assert store.failures == [("one", "retry_wait", "TEST API timed out")]
    assert store.rows["one"]["next_retry_at"] > datetime(2026, 10, 19, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_package_retry_wait_resumes_from_saved_phase_only_when_due():
    from katrain.cron.jobs.kifu_ingest import process_package_queue

    now = datetime(2026, 10, 19, tzinfo=timezone.utc)

    class Store:
        row = {
            "status": "retry_wait",
            "resume_phase": "prod_published",
            "prod_receipt": {"batch": 1},
            "next_retry_at": now + timedelta(minutes=5),
        }

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, receipt):
            assert expected_status == "retry_wait" and status == "prod_published"
            assert receipt == {"batch": 1}
            self.row = {"status": status}
            return self.row

    store = Store()
    called = []
    process = lambda manifest: called.append(manifest)
    assert await process_package_queue(store, [{"publication_key": "one"}], process, now=now) == 0
    assert called == []
    assert (
        await process_package_queue(store, [{"publication_key": "one"}], process, now=now + timedelta(minutes=6)) == 0
    )
    assert called == [{"publication_key": "one"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("resume_phase", ["test_published", "test_verified", "prod_published"])
async def test_real_journal_retry_restores_persisted_receipt(tmp_path, resume_phase):
    from katrain.cron.jobs.kifu_ingest import process_package_queue
    from katrain.kifu_ingest.state import StateStore, metadata

    database = create_engine(f"sqlite:///{tmp_path / 'journal.sqlite'}")
    metadata.create_all(database)
    store = StateStore(database)
    key = f"retry-{resume_phase}"
    store.register_batch(key, "a" * 64)
    previous = "discovered"
    for phase in ("downloaded", "parsed", "names_ready", "test_published", "test_verified", "prod_published"):
        if phase in ("test_published", "test_verified", "prod_published"):
            row = store.advance_batch(key, phase, expected_status=previous, receipt={"phase": phase})
        else:
            row = store.advance_batch(key, phase, expected_status=previous)
        previous = phase
        if phase == resume_phase:
            break
    store.advance_batch(key, "retry_wait", expected_status=resume_phase, error="temporary API error")
    seen = []

    async def process(manifest):
        with database.connect() as connection:
            from katrain.kifu_ingest.state import batches

            row = connection.execute(batches.select().where(batches.c.publication_key == key)).mappings().one()
        seen.append(row["status"])

    failures = await process_package_queue(store, [{"publication_key": key}], process)
    assert failures == 0
    assert seen == [resume_phase]
    with database.connect() as connection:
        from katrain.kifu_ingest.state import batches

        restored = connection.execute(batches.select().where(batches.c.publication_key == key)).mappings().one()
    assert restored[
        {"test_published": "test_receipt", "test_verified": "test_verification", "prod_published": "prod_receipt"}[
            resume_phase
        ]
    ] == {"phase": resume_phase}


@pytest.mark.asyncio
async def test_real_journal_bad_retry_does_not_block_next_package(tmp_path):
    from katrain.cron.jobs.kifu_ingest import process_package_queue
    from katrain.kifu_ingest.state import StateStore, batches, metadata

    database = create_engine(f"sqlite:///{tmp_path / 'journal.sqlite'}")
    metadata.create_all(database)
    store = StateStore(database)
    for key in ("bad", "good"):
        store.register_batch(key, "a" * 64)
        previous = "discovered"
        for phase in ("downloaded", "parsed", "names_ready"):
            store.advance_batch(key, phase, expected_status=previous)
            previous = phase
    store.advance_batch("bad", "test_published", expected_status="names_ready", receipt={"phase": "test_published"})
    store.advance_batch("bad", "retry_wait", expected_status="test_published", error="API timeout")
    with database.begin() as connection:
        connection.execute(update(batches).where(batches.c.publication_key == "bad").values(test_receipt=None))
    seen = []

    async def process(manifest):
        seen.append(manifest["publication_key"])

    assert await process_package_queue(store, [{"publication_key": "bad"}, {"publication_key": "good"}], process) == 1
    assert seen == ["good"]


@pytest.mark.asyncio
async def test_package_timeout_is_bounded_and_recorded_for_retry():
    from katrain.cron.jobs.kifu_ingest import process_package_queue

    class Store:
        row = {"status": "test_published"}

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, error, next_retry_at):
            assert expected_status == "test_published"
            self.row = {
                "status": status,
                "error": error,
                "next_retry_at": next_retry_at,
                "resume_phase": expected_status,
            }
            return self.row

    async def never_returns(manifest):
        await asyncio.sleep(10)

    store = Store()
    failures = await process_package_queue(
        store,
        [{"publication_key": "one"}],
        never_returns,
        now=datetime(2026, 10, 19, tzinfo=timezone.utc),
        timeout_seconds=0.01,
    )
    assert failures == 1
    assert store.row["status"] == "retry_wait"
    assert store.row["resume_phase"] == "test_published"


def test_discovered_download_is_recorded_with_raw_hash():
    from katrain.cron.jobs.kifu_ingest import record_staged_item

    class Store:
        def remember_item(self, *args, **kwargs):
            return {"status": "discovered"}

        def advance_item(self, source, item_id, status, **kwargs):
            assert (source, item_id, status) == ("19x19", "12", "downloaded")
            assert kwargs["expected_status"] == "discovered"
            assert kwargs["raw_sha256"] == "a" * 64
            return {"status": status}

    result = record_staged_item(
        Store(),
        {
            "external_id": "12",
            "status": "downloaded",
            "raw_sha256": "a" * 64,
            "raw_sgf_path": "/stage/12.sgf",
            "metadata": {"id": "12"},
        },
    )
    assert result["status"] == "downloaded"


def test_missing_credentials_is_durable_pending_and_can_resume():
    from katrain.cron.jobs.kifu_ingest import mark_needs_credentials, resume_credential_item

    class Store:
        row = {"status": "downloaded", "error": None, "resume_phase": None}

        def get_item(self, source, source_id):
            return self.row

        def advance_item(self, source, source_id, status, *, expected_status, error=None):
            assert self.row["status"] == expected_status
            self.row = {
                "status": status,
                "error": error,
                "resume_phase": expected_status if status == "retry_wait" else None,
            }
            return self.row

    store = Store()
    mark_needs_credentials(store, "42")
    assert store.row["status"] == "retry_wait"
    assert store.row["error"] == "needs_credentials"
    mark_needs_credentials(store, "42")
    resume_credential_item(store, "42")
    assert store.row["status"] == "downloaded"


def test_rejected_name_is_quarantined_in_stage_and_journal():
    from katrain.cron.jobs.kifu_ingest import quarantine_staged_item

    class Stage:
        def fail(self, source_id, error):
            assert source_id == "12"
            assert error.retryable is False

    class Store:
        def advance_item(self, source, source_id, status, **kwargs):
            assert (source, source_id, status) == ("19x19", "12", "quarantined")
            assert kwargs["expected_status"] == "downloaded"

    quarantine_staged_item(Stage(), Store(), "12", "name review rejected")


def test_frozen_game_journal_reaches_names_ready_without_writing_album_db():
    from katrain.cron.jobs.kifu_ingest import register_frozen_items

    class Store:
        def __init__(self):
            self.status = "downloaded"
            self.steps = []

        def remember_item(self, source, source_id, **kwargs):
            assert (source, source_id) == ("19x19", "12")
            return {"status": self.status}

        def advance_item(self, source, source_id, status, **kwargs):
            self.steps.append(status)
            self.status = status
            return {"status": status}

    store = Store()
    register_frozen_items(
        store,
        {
            "publication_key": "batch-12",
            "games": [{"source_key": "19x19", "source_item_id": "12", "raw_sha256": "a" * 64, "sgf_sha256": "b" * 64}],
        },
    )
    assert store.steps == ["parsed", "names_ready"]


def test_item_journal_recovers_from_published_batch_receipt():
    from katrain.cron.jobs.kifu_ingest import reconcile_items

    class Store:
        def __init__(self):
            self.row = {"status": "names_ready"}
            self.steps = []

        def get_item(self, source, source_id):
            return self.row

        def advance_item(self, source, source_id, status, **kwargs):
            self.steps.append((status, kwargs))
            self.row["status"] = status
            return self.row

    store = Store()
    manifest = {"games": [{"source_key": "19x19", "source_item_id": "12"}]}
    receipt = {"games": [{"source_key": "19x19", "source_item_id": "12", "album_id": 321}]}
    reconcile_items(store, manifest, {"status": "test_published", "test_receipt": receipt})
    assert store.steps[0][0] == "test_published"
    assert store.steps[0][1]["test_album_id"] == 321
    prod_receipt = {"games": [{"source_key": "19x19", "source_item_id": "12", "album_id": 999}]}
    reconcile_items(
        store,
        manifest,
        {
            "status": "prod_synced",
            "test_receipt": receipt,
            "test_verification": {"status": "verified"},
            "prod_receipt": prod_receipt,
            "prod_verification": {"status": "verified"},
        },
    )
    assert [step[0] for step in store.steps] == ["test_published", "test_verified", "prod_published", "prod_synced"]
    assert store.steps[2][1]["prod_album_id"] == 999
