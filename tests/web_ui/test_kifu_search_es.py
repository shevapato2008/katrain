"""Focused REST boundary tests; real isolated ES is an explicit opt-in."""

import asyncio
import json

import httpx
import pytest

from katrain.web.kifu.search_es import (
    AsyncElasticsearchClient,
    ElasticsearchClient,
    INDEX_MAPPING,
    INDEX_SETTINGS,
    SearchSettings,
    SearchUnavailable,
    encode_bulk,
    iter_bulk_batches,
)


def settings(role="read"):
    return SearchSettings(url="http://127.0.0.1:9200", index_alias="kifu-search", role=role, api_key="private")


def client(handler, role="read"):
    return ElasticsearchClient(settings(role), client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_settings_refuses_unverified_remote_http_and_separates_credentials(monkeypatch):
    monkeypatch.setenv("KIFU_ES_URL", "http://remote:9200")
    monkeypatch.setenv("KIFU_ES_READ_API_KEY", "read-key")
    monkeypatch.setenv("KIFU_ES_WRITER_API_KEY", "write-key")
    with pytest.raises(ValueError, match="HTTPS"):
        SearchSettings.from_env()
    monkeypatch.setenv("KIFU_ES_URL", "https://es.internal:9200")
    assert SearchSettings.from_env().api_key == "read-key"
    assert SearchSettings.from_env(role="writer").api_key == "write-key"
    monkeypatch.delenv("KIFU_ES_WRITER_API_KEY")
    with pytest.raises(ValueError, match="credentials"):
        SearchSettings.from_env(role="writer")


def test_mget_preserves_missing_and_concrete_index_but_rejects_item_error():
    response = {
        "docs": [
            {"_index": "kifu-v1", "_id": "sync-state", "found": True, "_source": {"status": "ready"}},
            {"_index": "kifu-v1", "_id": "term:a", "found": False},
        ]
    }
    es = client(lambda req: httpx.Response(200, json=response))
    assert es.mget(["sync-state", "term:a"]) == response
    response["docs"][1] = {"_id": "term:a", "error": {"type": "unavailable_shards_exception"}}
    with pytest.raises(SearchUnavailable):
        es.mget(["sync-state", "term:a"])


@pytest.mark.parametrize(
    "extra",
    [
        {"timed_out": True},
        {"_shards": {"failed": 1}},
        {"hits": {"total": {"value": 10000, "relation": "gte"}, "hits": []}},
    ],
)
def test_search_rejects_partial_response(extra):
    payload = {
        "timed_out": False,
        "_shards": {"failed": 0},
        "hits": {"total": {"value": 0, "relation": "eq"}, "hits": []},
    }
    payload.update(extra)
    es = client(lambda req: httpx.Response(200, json=payload))
    with pytest.raises(SearchUnavailable):
        es.search({"query": {"match_all": {}}}, index="kifu-v1")


def test_search_sets_exact_total_and_disallows_partial_without_retry():
    requests = []

    def handler(req):
        requests.append(req)
        assert req.url.params["allow_partial_search_results"] == "false"
        assert json.loads(req.content)["track_total_hits"] is True
        return httpx.Response(503, json={"error": "private detail"})

    es = client(handler)
    with pytest.raises(SearchUnavailable) as error:
        es.search({}, index="kifu-v1")
    assert "private detail" not in str(error.value)
    assert len(requests) == 1


def test_bulk_retries_only_transient_failed_items_and_checks_every_item():
    calls = []

    def handler(req):
        calls.append(req.content)
        statuses = [201, 429] if len(calls) == 1 else [201]
        return httpx.Response(
            200, json={"errors": len(calls) == 1, "items": [{"index": {"status": status}} for status in statuses]}
        )

    actions = [{"_id": "album:1", "_source": {"id": 1}}, {"_id": "album:2", "_source": {"id": 2}}]
    es = client(handler, "writer")
    es.bulk(actions, retry_transient=True)
    assert len(calls) == 2
    assert b"album:1" not in calls[1]
    assert b"album:2" in calls[1]
    bad = client(
        lambda req: httpx.Response(200, json={"errors": True, "items": [{"index": {"status": 400}}]}), "writer"
    )
    with pytest.raises(SearchUnavailable):
        bad.bulk(actions[:1], retry_transient=True)


def test_read_credentials_cannot_mutate_and_bulk_has_byte_and_count_bounds():
    es = client(lambda req: pytest.fail("read client sent a mutation"))
    with pytest.raises(SearchUnavailable):
        es.put_document("sync-state", {})
    with pytest.raises(SearchUnavailable):
        es.delete_document("album:1")
    actions = [{"_id": f"album:{i}", "_source": {"id": i}} for i in range(501)]
    batches = list(iter_bulk_batches(actions))
    assert [len(batch) for batch in batches] == [500, 1]
    assert encode_bulk(batches[0]).endswith(b"\n")
    with pytest.raises(ValueError, match="2 MiB"):
        list(iter_bulk_batches([{"_id": "large", "_source": {"value": "x" * (2 * 1024 * 1024)}}]))


def test_mapping_is_explicit_and_opaque_payloads_are_not_indexed():
    assert INDEX_SETTINGS["number_of_shards"] == 1
    assert INDEX_SETTINGS["number_of_replicas"] == 0
    assert INDEX_SETTINGS["max_result_window"] == 200000
    assert INDEX_MAPPING["dynamic"] == "strict"
    assert INDEX_MAPPING["date_detection"] is False
    fields = INDEX_MAPPING["properties"]
    assert fields["date_sort"]["type"] == "keyword"
    assert fields["search_text"]["type"] == "wildcard"
    for field in ("metadata", "classification", "diagnostics"):
        assert fields[field] == {"type": "object", "enabled": False}


def test_async_client_preserves_same_transport_checks_and_shared_lifecycle():
    requests = []

    async def run():
        transport = httpx.MockTransport(
            lambda req: requests.append(req)
            or httpx.Response(
                200,
                json={
                    "docs": [{"_id": "sync-state", "_index": "kifu-v1", "found": True, "_source": {"status": "ready"}}]
                },
            )
        )
        shared = httpx.AsyncClient(transport=transport)
        es = AsyncElasticsearchClient(settings(), client=shared)
        await es.mget(["sync-state"])
        await es.mget(["sync-state"])
        await es.aclose()
        assert shared.is_closed

    asyncio.run(run())
    assert len(requests) == 2


def test_five_language_event_text_is_single_source_multi_field_and_names_are_unindexed():
    fields = INDEX_MAPPING["properties"]
    assert "displays" not in fields
    for language, analyzer, search_analyzer in (
        ("cn", "ik_max_word", "ik_smart"),
        ("tw", "ik_max_word", "ik_smart"),
        ("en", "event_en", "event_en"),
        ("jp", "kuromoji", "kuromoji"),
        ("ko", "event_ko_index", "event_ko_query"),
    ):
        properties = fields["display"]["properties"][language]["properties"]
        assert properties["player_black"] == {"type": "keyword", "index": False, "doc_values": False}
        assert properties["player_white"] == properties["player_black"]
        assert properties["event"]["type"] == "keyword"
        assert properties["event"]["fields"]["words"] == {
            "type": "text",
            "analyzer": analyzer,
            "search_analyzer": search_analyzer,
        }
    analysis = INDEX_SETTINGS["analysis"]
    assert analysis["analyzer"]["event_en"] == {"type": "standard", "stopwords": "_none_"}
    assert analysis["tokenizer"]["event_ko_mixed"]["decompound_mode"] == "mixed"
    assert analysis["tokenizer"]["event_ko_discard"]["decompound_mode"] == "discard"


def test_non_object_json_is_service_failure():
    es = client(lambda req: httpx.Response(404, json=[]))
    with pytest.raises(SearchUnavailable):
        es.get_document("sync-state")


def index_cli():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "kifu_search_index_test", Path(__file__).parents[2] / "scripts/kifu_search_index.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_guard_requires_quiescence_and_real_window(monkeypatch):
    cli = index_cli()
    monkeypatch.setenv("KIFU_SEARCH_BACKEND", "legacy")
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "bootstrap")
    monkeypatch.delenv("KIFU_SEARCH_BOOTSTRAP_QUIESCENT", raising=False)
    with pytest.raises(ValueError, match="quiescent"):
        cli.require_bootstrap(cli.time() + 3600)
    monkeypatch.setenv("KIFU_SEARCH_BOOTSTRAP_QUIESCENT", "1")
    with pytest.raises(ValueError, match="30 minutes"):
        cli.require_bootstrap(cli.time() + 100)
    cli.require_bootstrap(cli.time() + 3600)


def test_sample_ids_covers_all_small_sets_and_24_spread_points():
    cli = index_cli()
    assert cli._sample_ids([1, 2, 3]) == {1, 2, 3}
    sampled = cli._sample_ids(list(range(1, 1001)))
    assert len(sampled) == 24 and 1 in sampled and 1000 in sampled


def test_language_probe_uses_same_index_and_removes_every_probe_document_on_failure():
    cli = index_cli()

    class Fake:
        def __init__(self):
            self.indexes = []
            self.deleted = []

        def request(self, method, path, **kwargs):
            return {"tokens": [{"token": "a"}]}

        def bulk(self, actions, *, index, **kwargs):
            self.indexes.append(index)
            self.deleted.extend(a["_id"] for a in actions if a.get("_op_type") == "delete")

        def refresh(self, *, index):
            self.indexes.append(index)

        def search(self, body, *, index):
            self.indexes.append(index)
            return {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

    fake = Fake()
    with pytest.raises(RuntimeError, match="language"):
        cli.verify_language_probe(fake, "kifu-candidate")
    assert set(fake.indexes) == {"kifu-candidate"}
    assert set(fake.deleted) == {f"language-probe:{lang}" for lang in ("cn", "tw", "jp", "ko", "en")}


def test_bulk_can_retry_transient_http_failure_without_retrying_reads():
    calls = []

    def handler(req):
        calls.append(req)
        return (
            httpx.Response(503, json={"error": "temporarily unavailable"})
            if len(calls) == 1
            else httpx.Response(200, json={"errors": False, "items": [{"index": {"status": 201}}]})
        )

    es = client(handler, "writer")
    es.bulk([{"_id": "album:1", "_source": {"id": 1}}], retry_transient=True)
    assert len(calls) == 2


def test_alias_exists_distinguishes_missing_from_transport_failure():
    es = client(lambda req: httpx.Response(404, json={"error": "alias [kifu-search] missing", "status": 404}), "writer")
    assert es.alias_exists() is False
    es = client(lambda req: httpx.Response(503, json={"error": "unavailable"}), "writer")
    with pytest.raises(SearchUnavailable):
        es.alias_exists()


def test_bulk_malformed_item_is_service_failure():
    es = client(lambda req: httpx.Response(200, json={"errors": False, "items": [None]}), "writer")
    with pytest.raises(SearchUnavailable):
        es.bulk([{"_id": "album:1", "_source": {"id": 1}}])


def test_plugin_verifier_checks_plugin_own_patch_as_well_as_es_patch(tmp_path):
    import hashlib
    import importlib.util
    import zipfile
    from pathlib import Path

    path = Path(__file__).parents[2] / "deploy/elasticsearch/prepare_plugins.py"
    spec = importlib.util.spec_from_file_location("plugin_verifier_test", path)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(
            "plugin-descriptor.properties", "name=analysis-ik\nversion=9.5.4\nelasticsearch.version=9.5.5\n"
        )
    plugin = {"name": "analysis-ik", "sha512": hashlib.sha512(archive.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="patch"):
        verifier.verify_plugin(archive, plugin, "9.5.5")


def test_bulk_error_field_cannot_be_reported_success_even_with_success_status():
    es = client(
        lambda req: httpx.Response(
            200, json={"errors": True, "items": [{"index": {"status": 201, "error": {"type": "failure"}}}]}
        ),
        "writer",
    )
    with pytest.raises(SearchUnavailable):
        es.bulk([{"_id": "album:1", "_source": {"id": 1}}])


def test_initial_activate_never_uses_all_indices_wildcard():
    sent = []

    def handler(req):
        if req.method == "GET":
            return httpx.Response(404, json={"error": "alias missing"})
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={"acknowledged": True})

    es = client(handler, "admin")
    es.activate("kifu-search-candidate")
    assert sent == [{"actions": [{"add": {"index": "kifu-search-candidate", "alias": "kifu-search"}}]}]


def test_create_index_requires_acknowledged_shards():
    es = client(lambda req: httpx.Response(200, json={"acknowledged": True, "shards_acknowledged": False}), "admin")
    with pytest.raises(SearchUnavailable):
        es.create_index("kifu-search-candidate")


def test_incomplete_index_stats_cannot_hide_storage_budget():
    cli = index_cli()

    class Fake:
        def request(self, *args, **kwargs):
            return {}

    with pytest.raises(RuntimeError, match="stats"):
        cli.index_stats(Fake(), "candidate")
