"""Small, bounded Elasticsearch REST boundary shared by readers and publishers.

Credentials are role-specific. The web reader never receives mutation methods that
can succeed; writers cannot create/delete indices or change aliases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import os
import re
import ssl
from time import sleep
from urllib.parse import quote, urlsplit

import httpx

from katrain.web.kifu.search_documents import SCHEMA_VERSION

STATE_DOCUMENT_ID = "sync-state"
MAX_BULK_ACTIONS = 500
MAX_BULK_BYTES = 2 * 1024 * 1024
MAX_RESULT_WINDOW = 200000
INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "max_result_window": MAX_RESULT_WINDOW,
    "refresh_interval": "-1",
    "analysis": {
        "tokenizer": {
            "event_ko_mixed": {"type": "nori_tokenizer", "decompound_mode": "mixed"},
            "event_ko_discard": {"type": "nori_tokenizer", "decompound_mode": "discard"},
        },
        "analyzer": {
            "event_en": {"type": "standard", "stopwords": "_none_"},
            "event_ko_index": {
                "type": "custom",
                "tokenizer": "event_ko_mixed",
                "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"],
            },
            "event_ko_query": {
                "type": "custom",
                "tokenizer": "event_ko_discard",
                "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"],
            },
        },
    },
}
INDEX_MAPPING = {
    "dynamic": "strict",
    "date_detection": False,
    "properties": {
        **{
            key: {"type": "keyword"}
            for key in (
                "doc_kind",
                "date_sort",
                "player_aliases",
                "event_aliases",
                "provisional_player_names",
                "provisional_event_names",
                "provisional_override_names",
                "term",
                "schema_version",
                "status",
                "operation_type",
                "target_index",
                "operation_kind",
                "index_name",
            )
        },
        **{
            key: {"type": "long"}
            for key in (
                "id",
                "album_id",
                "black_player_id",
                "white_player_id",
                "event_id",
                "selected_event_id",
                "player_id",
                "raw_player_name_ids",
                "raw_event_name_ids",
                "selected_event_name_ids",
                "epoch",
                "album_count",
                "visible_count",
                "classification_count",
            )
        },
        **{key: {"type": "boolean"} for key in ("list_visible", "public", "strict_mode")},
        **{
            key: {"type": "wildcard"}
            for key in ("search_text", "player_black_lower", "player_white_lower", "selected_event_raw_lower")
        },
        "display": {
            "type": "object",
            "dynamic": "strict",
            "properties": {
                language: {
                    "type": "object",
                    "dynamic": "strict",
                    "properties": {
                        "player_black": {"type": "keyword", "index": False, "doc_values": False},
                        "player_white": {"type": "keyword", "index": False, "doc_values": False},
                        "event": {
                            "type": "keyword",
                            "fields": {
                                "words": {"type": "text", "analyzer": analyzer, "search_analyzer": search_analyzer}
                            },
                        },
                    },
                }
                for language, analyzer, search_analyzer in (
                    ("cn", "ik_max_word", "ik_smart"),
                    ("tw", "ik_max_word", "ik_smart"),
                    ("en", "event_en", "event_en"),
                    ("jp", "kuromoji", "kuromoji"),
                    ("ko", "event_ko_index", "event_ko_query"),
                )
            },
        },
        **{
            key: {"type": "object", "enabled": False}
            for key in ("metadata", "classification", "diagnostics", "operation_ref")
        },
    },
}
_INDEX = re.compile(r"^[a-z0-9][a-z0-9._-]{0,254}$")
_TRANSIENT = {429, 502, 503, 504}


class SearchUnavailable(RuntimeError):
    """Search cannot provide a complete, verified result (safe for API logs)."""

    def __init__(self, message, *, status_code=None, transient=False):
        super().__init__(message)
        self.status_code = status_code
        self.transient = transient or status_code in _TRANSIENT


def _index(value):
    if not isinstance(value, str) or not _INDEX.fullmatch(value):
        raise ValueError("invalid Elasticsearch index/alias")
    return quote(value, safe="")


def _id(value):
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 512:
        raise ValueError("invalid Elasticsearch document ID")
    return quote(value, safe="")


@dataclass(frozen=True)
class SearchSettings:
    url: str
    index_alias: str = "kifu-search"
    role: str = "read"
    api_key: str | None = field(default=None, repr=False)
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    ca_cert: str | None = None
    timeout_seconds: float = 3.0
    max_connections: int = 32

    def __post_init__(self):
        parsed = urlsplit(self.url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("Elasticsearch URL must contain only scheme, host and port")
        loopback = parsed.hostname == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            pass
        if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
            raise ValueError("Elasticsearch requires HTTPS (HTTP permitted only on loopback)")
        if not parsed.hostname or self.role not in {"read", "writer", "admin"}:
            raise ValueError("invalid Elasticsearch settings")
        _index(self.index_alias)
        if not 0 < self.timeout_seconds <= 60 or not 1 <= self.max_connections <= 128:
            raise ValueError("Elasticsearch limits must be finite and bounded")
        if not self.api_key and not (self.username and self.password):
            raise ValueError(f"Elasticsearch {self.role} credentials are required")
        if self.api_key and (self.username or self.password):
            raise ValueError("choose API key or username/password credentials")

    @classmethod
    def from_env(cls, *, role="read"):
        prefix = f"KIFU_ES_{role.upper()}_"
        return cls(
            url=os.environ.get("KIFU_ES_URL", ""),
            index_alias=os.environ.get("KIFU_ES_INDEX_ALIAS", "kifu-search"),
            role=role,
            api_key=os.environ.get(prefix + "API_KEY"),
            username=os.environ.get(prefix + "USERNAME"),
            password=os.environ.get(prefix + "PASSWORD"),
            ca_cert=os.environ.get("KIFU_ES_CA_CERT"),
            timeout_seconds=float(os.environ.get("KIFU_ES_TIMEOUT_SECONDS", "3")),
            max_connections=int(os.environ.get("KIFU_ES_MAX_CONNECTIONS", "32")),
        )

    def client_options(self):
        context = ssl.create_default_context(cafile=self.ca_cert) if self.ca_cert else ssl.create_default_context()
        return {
            "base_url": self.url.rstrip("/"),
            "verify": context,
            "timeout": httpx.Timeout(self.timeout_seconds),
            "limits": httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=min(16, self.max_connections),
                keepalive_expiry=30,
            ),
            "headers": {"Authorization": "ApiKey " + self.api_key} if self.api_key else {},
            "auth": httpx.BasicAuth(self.username, self.password) if self.username else None,
            "follow_redirects": False,
            "trust_env": False,
        }


def _response(response, *, missing=False):
    try:
        value = response.json()
    except (ValueError, UnicodeError) as error:
        raise SearchUnavailable("Elasticsearch returned invalid JSON") from error
    if not isinstance(value, dict):
        raise SearchUnavailable("Elasticsearch returned invalid object")
    if missing and response.status_code == 404 and value.get("found") is False:
        return value
    if response.is_error or not isinstance(value, dict) or "error" in value:
        raise SearchUnavailable(
            f"Elasticsearch request failed (HTTP {response.status_code})", status_code=response.status_code
        )
    return value


def _mget(value, ids):
    docs = value.get("docs")
    if not isinstance(docs, list) or len(docs) != len(ids):
        raise SearchUnavailable("Elasticsearch returned incomplete mget")
    for requested, doc in zip(ids, docs):
        if (
            not isinstance(doc, dict)
            or "error" in doc
            or doc.get("_id") != requested
            or type(doc.get("found")) is not bool
        ):
            raise SearchUnavailable("Elasticsearch mget item failed")
    return value


def _search(value):
    total = value.get("hits", {}).get("total", {})
    if (
        value.get("timed_out") is not False
        or value.get("_shards", {}).get("failed") != 0
        or not isinstance(total, dict)
        or total.get("relation") != "eq"
        or type(total.get("value")) is not int
        or total["value"] < 0
        or not isinstance(value.get("hits", {}).get("hits"), list)
    ):
        raise SearchUnavailable("Elasticsearch returned incomplete search results")
    return value


def encode_bulk(actions):
    lines = []
    for action in actions:
        operation = action.get("_op_type", "index")
        if operation not in {"index", "delete"}:
            raise ValueError("only index/delete bulk operations are supported")
        _id(action["_id"])
        meta = {"_id": action["_id"]}
        if "_index" in action:
            _index(action["_index"])
            meta["_index"] = action["_index"]
        lines.append(json.dumps({operation: meta}, ensure_ascii=False, separators=(",", ":")))
        if operation == "index":
            lines.append(json.dumps(action["_source"], ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""


def iter_bulk_batches(actions):
    batch, size = [], 0
    for action in actions:
        action_size = len(encode_bulk([action]))
        if action_size > MAX_BULK_BYTES:
            raise ValueError("single document exceeds 2 MiB bulk limit")
        if batch and (len(batch) == MAX_BULK_ACTIONS or size + action_size > MAX_BULK_BYTES):
            yield batch
            batch, size = [], 0
        batch.append(action)
        size += action_size
    if batch:
        yield batch


class ElasticsearchClient:
    def __init__(self, settings: SearchSettings, *, client=None):
        self.settings = settings
        self.client = client or httpx.Client(**settings.client_options())

    def _target(self, index):
        return _index(index or self.settings.index_alias)

    def request(self, method, path, *, json=None, content=None, params=None, missing=False):
        if self.settings.role == "read" and method.upper() not in {"GET", "HEAD"}:
            if not (method.upper() == "POST" and path.endswith(("/_search", "/_mget"))):
                raise SearchUnavailable("read credentials cannot mutate Elasticsearch")
        try:
            response = self.client.request(
                method,
                self.settings.url.rstrip("/") + path,
                json=json,
                content=content,
                params=params,
                timeout=self.settings.timeout_seconds,
                headers={"Content-Type": "application/x-ndjson"} if content is not None else None,
            )
        except httpx.HTTPError as error:
            raise SearchUnavailable("Elasticsearch transport unavailable", transient=True) from error
        return _response(response, missing=missing)

    def mget(self, ids, *, index=None):
        ids = list(ids)
        return _mget(self.request("POST", f"/{self._target(index)}/_mget", json={"ids": ids}), ids)

    def get_document(self, id, *, index=None):
        return self.request("GET", f"/{self._target(index)}/_doc/{_id(id)}", missing=True)

    def search(self, body, *, index=None):
        return _search(
            self.request(
                "POST",
                f"/{self._target(index)}/_search",
                json={**body, "track_total_hits": True},
                params={"allow_partial_search_results": "false"},
            )
        )

    def put_document(self, id, body, *, index=None, refresh=False):
        return self.request(
            "PUT",
            f"/{self._target(index)}/_doc/{_id(id)}",
            json=body,
            params={"refresh": "true" if refresh else "false"},
        )

    def delete_document(self, id, *, index=None):
        return self.request("DELETE", f"/{self._target(index)}/_doc/{_id(id)}")

    def bulk(self, actions, *, index=None, retry_transient=False):
        pending = list(actions)
        body = encode_bulk(pending)
        if len(pending) > MAX_BULK_ACTIONS or len(body) > MAX_BULK_BYTES:
            raise ValueError("bulk exceeds 500 operations or 2 MiB")
        if not pending:
            return {"errors": False, "items": []}
        completed = []
        for attempt in range(3 if retry_transient else 1):
            try:
                value = self.request("POST", f"/{self._target(index)}/_bulk", content=encode_bulk(pending))
            except SearchUnavailable as error:
                if retry_transient and error.transient and attempt < 2:
                    sleep(0.1 * (attempt + 1))
                    continue
                raise
            items = value.get("items")
            if not isinstance(items, list) or len(items) != len(pending):
                raise SearchUnavailable("Elasticsearch returned incomplete bulk results")
            retry = []
            for action, item in zip(pending, items):
                operation = action.get("_op_type", "index")
                if not isinstance(item, dict) or not isinstance(item.get(operation), dict):
                    raise SearchUnavailable("Elasticsearch returned malformed bulk item")
                result = item[operation]
                status = result.get("status")
                if (
                    type(status) is int
                    and "error" not in result
                    and (200 <= status < 300 or (operation == "delete" and status == 404))
                ):
                    completed.append(item)
                elif retry_transient and status in _TRANSIENT and attempt < 2:
                    retry.append(action)
                else:
                    raise SearchUnavailable("Elasticsearch bulk item failed")
            if not retry:
                return {"errors": False, "items": completed}
            pending = retry
            sleep(0.1 * (attempt + 1))
        raise SearchUnavailable("Elasticsearch bulk retry exhausted")

    def refresh(self, *, index=None):
        value = self.request("POST", f"/{self._target(index)}/_refresh")
        if value.get("_shards", {}).get("failed") != 0:
            raise SearchUnavailable("Elasticsearch refresh failed")
        return value

    def update_settings(self, settings, *, index=None):
        return self.request("PUT", f"/{self._target(index)}/_settings", json={"index": settings})

    def alias_exists(self, alias=None):
        try:
            self.request("GET", f"/_alias/{_index(alias or self.settings.index_alias)}")
        except SearchUnavailable as error:
            if error.status_code == 404:
                return False
            raise
        return True

    def resolve_index(self, alias=None):
        value = self.request("GET", f"/_alias/{_index(alias or self.settings.index_alias)}")
        if len(value) != 1:
            raise SearchUnavailable("Elasticsearch alias must name exactly one concrete index")
        result = next(iter(value))
        _index(result)
        return result

    def create_index(self, index):
        self._admin()
        value = self.request("PUT", f"/{_index(index)}", json={"settings": INDEX_SETTINGS, "mappings": INDEX_MAPPING})
        if value.get("acknowledged") is not True or value.get("shards_acknowledged") is not True:
            error = SearchUnavailable("Elasticsearch index creation was not fully acknowledged")
            error.created_index = index if value.get("acknowledged") is True else None
            raise error
        return value

    def activate(self, index):
        self._admin()
        _index(index)
        actions = []
        if self.alias_exists():
            previous = self.resolve_index()
            actions.append({"remove": {"index": previous, "alias": self.settings.index_alias, "must_exist": True}})
        actions.append({"add": {"index": index, "alias": self.settings.index_alias}})
        value = self.request("POST", "/_aliases", json={"actions": actions})
        if value.get("acknowledged") is not True or value.get("errors"):
            raise SearchUnavailable("Elasticsearch alias activation was not acknowledged")
        return value

    def delete_index(self, index):
        self._admin()
        value = self.request("GET", f"/{_index(index)}/_alias")
        if set(value) != {index} or value[index].get("aliases") or index == self.settings.index_alias:
            raise SearchUnavailable("refusing to delete an aliased/non-concrete index")
        tasks = self.request("GET", "/_tasks", params={"detailed": "true"})
        if any(
            index in json.dumps(task)
            for node in tasks.get("nodes", {}).values()
            for task in node.get("tasks", {}).values()
        ):
            raise SearchUnavailable("candidate has an active task")
        return self.request("DELETE", f"/{_index(index)}")

    def _admin(self):
        if self.settings.role != "admin":
            raise SearchUnavailable("index administration requires admin credentials")

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncElasticsearchClient:
    """One shared request-lifecycle client; no hot-path retry or index mutation."""

    def __init__(self, settings: SearchSettings, *, client=None):
        if settings.role != "read":
            raise ValueError("async search client requires read credentials")
        self.settings = settings
        self.client = client or httpx.AsyncClient(**settings.client_options())

    async def request(self, method, path, *, json=None, params=None, missing=False):
        if method.upper() not in {"GET", "HEAD"} and not (
            method.upper() == "POST" and path.endswith(("/_search", "/_mget"))
        ):
            raise SearchUnavailable("read credentials cannot mutate Elasticsearch")
        try:
            response = await self.client.request(
                method,
                self.settings.url.rstrip("/") + path,
                json=json,
                params=params,
                timeout=self.settings.timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise SearchUnavailable("Elasticsearch transport unavailable", transient=True) from error
        return _response(response, missing=missing)

    async def mget(self, ids, *, index=None):
        ids = list(ids)
        return _mget(
            await self.request("POST", f"/{_index(index or self.settings.index_alias)}/_mget", json={"ids": ids}), ids
        )

    async def get_document(self, id, *, index=None):
        return await self.request("GET", f"/{_index(index or self.settings.index_alias)}/_doc/{_id(id)}", missing=True)

    async def search(self, body, *, index=None):
        return _search(
            await self.request(
                "POST",
                f"/{_index(index or self.settings.index_alias)}/_search",
                json={**body, "track_total_hits": True},
                params={"allow_partial_search_results": "false"},
            )
        )

    async def aclose(self):
        await self.client.aclose()
