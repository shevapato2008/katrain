"""Bounded API verification uses synthetic packages and an in-process HTTP transport."""

import asyncio
from collections import Counter
from copy import deepcopy
import json

import httpx
import pytest

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest import sync
from katrain.web.kifu.name_candidates import canonical_sha256


class Clock:
    def __init__(self):
        self.now = 100.0
        self.wall = 1_000_000.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.wall

    async def sleep(self, seconds):
        self.now += seconds


class AlbumAPI:
    def __init__(self, count=1):
        self.manifest = {"publication_key": "synthetic", "games": [], "decisions": []}
        self.receipt = {"status": "applied", "games": []}
        self.details = {}
        self.calls = []
        self.fault = None
        self.clock = None
        for index in range(count):
            album_id = index + 7
            black = f"Black{index}"
            sgf = f"(;PB[{black}]PW[White]EV[Event]DT[2026-10-22];B[aa])"
            game = {
                "source_key": "19x19",
                "source_item_id": str(index + 1),
                "sgf_sha256": sync.sha256(SGF.parse_sgf(sgf).sgf().encode()).hexdigest(),
                "metadata": {
                    "player_black": black,
                    "player_white": "White",
                    "event": "Event",
                    "date_played": "2026-10-22",
                },
            }
            self.manifest["games"].append(game)
            self.receipt["games"].append(
                {"source_key": "19x19", "source_item_id": str(index + 1), "album_id": album_id}
            )
            for kind, name in (("raw_player", black), ("raw_player", "White"), ("raw_event", "Event")):
                if not any(row["key"] == name for row in self.manifest["decisions"]):
                    self.manifest["decisions"].append(
                        {"kind": kind, "key": name, "displays": {lang: f"{name}/{lang}" for lang in sync.LANGUAGES}}
                    )
            for lang in sync.LANGUAGES:
                self.details[album_id, lang] = {
                    "id": album_id,
                    "sgf_content": sgf,
                    **{field: game["metadata"][field] for field in ("player_black", "player_white", "event")},
                    "sources": ["19x19"],
                    "display_player_black": f"{black}/{lang}",
                    "display_player_white": f"White/{lang}",
                    "display_event": f"Event/{lang}",
                }
        self.listing = {
            "items": [
                {
                    key: value
                    for key, value in self.details[row["album_id"], "cn"].items()
                    if key.startswith("display_") or key == "id"
                }
                for row in self.receipt["games"]
            ],
            "total": count,
        }

    async def handle(self, request):
        call = (request.url.path, tuple(request.url.params.multi_items()))
        self.calls.append(call)
        if self.clock:
            self.clock.now += 1
        if self.fault:
            response = await self.fault(request)
            if response is not None:
                return response
        if request.url.path.endswith("/albums"):
            return httpx.Response(200, json=deepcopy(self.listing))
        album_id = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json=deepcopy(self.details[album_id, request.url.params["lang"]]))

    def client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    async def verify(self, **kwargs):
        async with self.client() as client:
            return await sync.verify_album_api(client, "https://example", self.manifest, self.receipt, **kwargs)

    def list_calls(self):
        return [call for call in self.calls if call[0].endswith("/albums")]


@pytest.mark.asyncio
async def test_transient_list_timeout_retries_once_and_uses_finite_default():
    api = AlbumAPI()
    timeouts = []

    async def fault(request):
        timeouts.append(request.extensions["timeout"])
        if request.url.path.endswith("/albums") and len(api.list_calls()) == 1:
            raise httpx.ReadTimeout("temporary", request=request)

    api.fault = fault
    result = await api.verify(sleep=Clock().sleep)
    assert result["status"] == "verified"
    assert len(api.list_calls()) == 2
    assert all(set(timeout.values()) == {30} for timeout in timeouts)


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError])
async def test_persistent_transport_failure_is_not_verified_after_two_attempts(exception):
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums"):
            raise exception("persistent", request=request)

    api.fault = fault
    with pytest.raises(exception):
        await api.verify(sleep=Clock().sleep)
    assert len(api.list_calls()) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [429, 503, "malformed"])
async def test_non200_and_semantic_failures_are_not_retried(failure):
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums"):
            return (
                httpx.Response(200, json={"items": "bad", "total": 1})
                if failure == "malformed"
                else httpx.Response(failure)
            )

    api.fault = fault
    with pytest.raises(ValueError):
        await api.verify()
    assert len(api.list_calls()) == 1


@pytest.mark.asyncio
async def test_list_cache_reuses_exact_page_but_checks_each_albums_card():
    api = AlbumAPI(2)
    result = await api.verify()
    assert len(result["checks"]) == 10
    assert len(api.list_calls()) == 1
    api.calls.clear()
    api.listing["items"][1]["display_event"] = "wrong"
    with pytest.raises(ValueError, match="public list card"):
        await api.verify()
    assert len(api.list_calls()) == 1


@pytest.mark.asyncio
async def test_cache_does_not_cross_invocations_or_targets():
    api = AlbumAPI()
    await api.verify()
    async with api.client() as client:
        await sync.verify_album_api(client, "https://other", api.manifest, api.receipt)
    await api.verify()
    assert len(api.list_calls()) == 3


@pytest.mark.asyncio
async def test_date_query_keeps_twenty_page_cap_before_player_fallback():
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums") and request.url.params["q"] == "2026-10-22":
            return httpx.Response(200, json={"items": [], "total": 5000})

    api.fault = fault
    await api.verify()
    queries = [dict(params) for _, params in api.list_calls()]
    assert [int(query["page"]) for query in queries[:-1]] == list(range(1, 21))
    assert queries[-1] == {"q": "Black0", "lang": "cn", "page": "1", "page_size": "100"}


@pytest.mark.asyncio
async def test_list_cache_keeps_different_pages_separate():
    api = AlbumAPI(2)

    async def fault(request):
        if request.url.path.endswith("/albums") and request.url.params["page"] == "1":
            return httpx.Response(200, json={"items": [], "total": 101})

    api.fault = fault
    await api.verify()
    assert [dict(params)["page"] for _, params in api.list_calls()] == ["1", "2"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,error",
    [
        ("sgf_content", "(;PB[Wrong])", "SGF hash"),
        ("sgf_content", None, "SGF is invalid"),
        ("player_black", "other", "player_black mismatch"),
        ("player_white", "other", "player_white mismatch"),
        ("event", "other", "event mismatch"),
        ("sources", [], "source link"),
        ("display_event", "wrong", "display_event mismatch"),
        ("display_player_black", "", "display_player_black missing"),
    ],
)
async def test_last_language_still_requires_sgf_original_names_source_and_reviewed_displays(field, value, error):
    api = AlbumAPI()
    api.details[7, "en"][field] = value
    with pytest.raises(ValueError, match=error):
        await api.verify()
    assert len(api.calls) == 5


@pytest.mark.asyncio
async def test_deadline_cancels_slow_transport_and_does_not_retry():
    api = AlbumAPI()
    cancelled = []

    async def fault(request):
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    api.fault = fault
    with pytest.raises(TimeoutError):
        await api.verify(deadline=asyncio.get_running_loop().time() + 0.025)
    assert cancelled == [True]
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_per_attempt_timeout_is_a_wall_cap_without_caller_deadline():
    api = AlbumAPI()

    async def fault(request):
        await asyncio.sleep(0.2)

    api.fault = fault
    with pytest.raises(TimeoutError):
        await api.verify(timeout=0.025)
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_exhausted_deadline_never_requests_or_returns_checkpoint_success(tmp_path):
    api = AlbumAPI()
    clock = Clock()
    await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    api.calls.clear()
    with pytest.raises(TimeoutError):
        await api.verify(checkpoint_dir=tmp_path, deadline=clock.now, clock=clock.monotonic, wall_clock=clock.time)
    assert api.calls == []


@pytest.mark.asyncio
async def test_remaining_deadline_clamps_timeout_and_prevents_retry():
    api = AlbumAPI()
    clock = Clock()

    async def fault(request):
        assert set(request.extensions["timeout"].values()) == {2}
        clock.now += 2
        raise httpx.ReadTimeout("budget exhausted", request=request)

    api.fault = fault
    with pytest.raises(TimeoutError):
        await api.verify(deadline=102, clock=clock.monotonic, sleep=clock.sleep)
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_final_coverage_check_cannot_return_success_after_deadline(monkeypatch):
    api = AlbumAPI()
    clock = Clock()
    validate = sync.validate_test_verification

    def expire_after_coverage(*args):
        validate(*args)
        clock.now = 200

    monkeypatch.setattr(sync, "validate_test_verification", expire_after_coverage)
    with pytest.raises(TimeoutError):
        await api.verify(deadline=200, clock=clock.monotonic)


@pytest.mark.asyncio
async def test_complete_albums_resume_across_two_bounded_calls(tmp_path):
    api = AlbumAPI(2)
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time, "sleep": clock.sleep}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=106.5, **options)
    checkpoint = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert len(checkpoint["completed"]) == 1
    api.calls.clear()
    result = await api.verify(deadline=clock.now + 7, **options)
    assert result["status"] == "verified"
    assert len(result["checks"]) == 10
    assert Counter(check["album_id"] for check in result["checks"]) == {7: 5, 8: 5}
    assert all(not path.endswith("/7") for path, _ in api.calls)
    sync.validate_test_verification(api.manifest, "digest", {**result, "manifest_sha256": "digest"})


@pytest.mark.asyncio
async def test_half_album_has_no_checkpoint_credit(tmp_path):
    api = AlbumAPI()
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=102.5, **options)
    api.calls.clear()
    await api.verify(deadline=clock.now + 7, **options)
    assert len(api.calls) == 6


@pytest.mark.asyncio
async def test_completed_at_is_not_refreshed_when_another_album_completes(tmp_path):
    api = AlbumAPI(2)
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=106.5, **options)
    path = next(tmp_path.glob("*.json"))
    before = json.loads(path.read_text())["completed"]
    first = next(iter(before))
    clock.wall += 86_399
    await api.verify(**options)
    after = json.loads(path.read_text())["completed"]
    assert after[first]["completed_at"] == before[first]["completed_at"]
    clock.wall += 2
    api.calls.clear()
    await api.verify(**options)
    assert [path for path, _ in api.calls if not path.endswith("/albums")] == ["/api/v1/kifu/albums/7"] * 5


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["manifest", "receipt", "target", "algorithm", "languages"])
async def test_checkpoint_binding_changes_cannot_skip_verification(tmp_path, monkeypatch, changed):
    api = AlbumAPI()
    await api.verify(checkpoint_dir=tmp_path)
    api.calls.clear()
    target = "https://example"
    if changed == "manifest":
        api.manifest["publication_key"] = "different"
    elif changed == "receipt":
        api.receipt["native_receipt_extra"] = "changed"
    elif changed == "target":
        target = "https://other"
    elif changed == "algorithm":
        from katrain.kifu_ingest import verification

        monkeypatch.setattr(verification, "ALGORITHM_VERSION", "future-test-version")
    elif changed == "languages":
        monkeypatch.setattr(sync, "LANGUAGES", tuple(reversed(sync.LANGUAGES)))
    async with api.client() as client:
        await sync.verify_album_api(client, target, api.manifest, api.receipt, checkpoint_dir=tmp_path)
    assert len(api.calls) == 6
    assert len(list(tmp_path.glob("*.json"))) == 2


@pytest.mark.asyncio
async def test_normalized_target_reuses_same_bound_checkpoint(tmp_path):
    api = AlbumAPI()
    await api.verify(checkpoint_dir=tmp_path)
    api.calls.clear()
    async with api.client() as client:
        result = await sync.verify_album_api(
            client, "HTTPS://EXAMPLE:443/", api.manifest, api.receipt, checkpoint_dir=tmp_path
        )
    assert result["status"] == "verified"
    assert api.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["json", "digest", "binding", "partial", "future", "card", "details"])
async def test_corrupt_or_inconsistent_checkpoint_fails_closed(tmp_path, damage):
    api = AlbumAPI()
    clock = Clock()
    await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    path = next(tmp_path.glob("*.json"))
    record = json.loads(path.read_text())
    if damage == "json":
        path.write_text("{broken")
    else:
        album = next(iter(record["completed"].values()))
        if damage == "digest":
            record["content_sha256"] = "0" * 64
        elif damage == "binding":
            record["binding"]["target"] = "https://other"
        elif damage == "partial":
            album["details"].pop()
        elif damage == "future":
            album["completed_at"] = clock.wall + 100
        elif damage == "card":
            album["public_card"]["displays"]["display_event"] = "wrong"
        elif damage == "details":
            album["details"][0]["sgf_sha256"] = "0" * 64
        if damage != "digest":
            record["content_sha256"] = canonical_sha256(
                {key: value for key, value in record.items() if key != "content_sha256"}
            )
        path.write_text(json.dumps(record))
    api.calls.clear()
    with pytest.raises(ValueError, match="checkpoint"):
        await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    assert api.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("link", ["file", "directory", "parent"])
async def test_checkpoint_symlinks_are_rejected(tmp_path, link):
    api = AlbumAPI()
    directory = tmp_path / "checkpoints"
    await api.verify(checkpoint_dir=directory)
    if link == "file":
        path = next(directory.glob("*.json"))
        moved = tmp_path / "moved.json"
        path.rename(moved)
        path.symlink_to(moved)
    elif link == "directory":
        directory.rename(tmp_path / "real")
        directory.symlink_to(tmp_path / "real", target_is_directory=True)
    else:
        (tmp_path / "parent").symlink_to(tmp_path, target_is_directory=True)
        directory = tmp_path / "parent" / "checkpoints"
    api.calls.clear()
    with pytest.raises(ValueError, match="checkpoint"):
        await api.verify(checkpoint_dir=directory)
    assert api.calls == []


@pytest.mark.asyncio
async def test_prod_published_receipt_resumes_only_verification_and_failure_does_not_advance(tmp_path):
    from katrain.cron.jobs.kifu_ingest import resume_batch

    api = AlbumAPI()

    class Store:
        row = {"status": "prod_published", "prod_receipt": api.receipt}

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, receipt):
            assert expected_status == "prod_published"
            self.row.update(status=status, prod_verification=receipt)
            return self.row

    async def forbidden(*args):
        pytest.fail("native prod receipt must not repeat publication or translation")

    async def verify(manifest, receipt):
        return await api.verify(checkpoint_dir=tmp_path)

    store = Store()
    api.listing["items"][0]["display_event"] = "wrong"
    with pytest.raises(ValueError, match="public list card"):
        await resume_batch(
            store,
            api.manifest,
            "digest",
            test_publish=forbidden,
            test_verify=forbidden,
            sync=forbidden,
            prod_verify=verify,
        )
    assert store.row["status"] == "prod_published"
    api.listing["items"][0]["display_event"] = "Event/cn"
    await resume_batch(
        store, api.manifest, "digest", test_publish=forbidden, test_verify=forbidden, sync=forbidden, prod_verify=verify
    )
    assert store.row["status"] == "prod_synced"
    assert len(store.row["prod_verification"]["checks"]) == 5
    assert len([path for path, _ in api.calls if not path.endswith("/albums")]) == 10
