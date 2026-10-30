"""Pure exact-name classification and Elasticsearch query compilation."""

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.search_documents import NAME_LANGUAGES
from katrain.web.kifu.library_search import HISTORICAL_PLAYER_ALIASES
from katrain.web.kifu.name_first_pass import VERSION as FIRST_PASS_VERSION
from katrain.web.kifu.name_raw_player_scope import PreparedRawPlayerScope


OWNER_FIELDS = ("player_ids", "event_ids", "raw_player_name_ids", "raw_event_name_ids")


def _mode(value):
    players, events, raw_players, raw_events = (value.get(key, []) for key in OWNER_FIELDS)
    if len(players) == 1 and not events and not raw_players and not raw_events:
        return "exact_player"
    if len(players) > 1 and set(players) == set(value.get("shared_player_ids", ())) and not events and not raw_events:
        return "shared_players"
    if len(players) == 1 and raw_players and not events and not raw_events:
        return "player_raw"
    if len(events) == 1 and not players and not raw_players and not raw_events:
        return "exact_event"
    if raw_events and not players and not events and not raw_players:
        return "exact_raw_event"
    return "generic"


def classify_qualified_names(player_rows, event_rows, raw_players, raw_events, *, shared_player_ids=(), strict=True):
    """Apply the original finite same-display permissions to prequalified rows."""
    players = {name.player_id for name, _ in player_rows}
    events = {name.event_id for name, _ in event_rows}
    player_raws = {raw for _, raw, _ in raw_players}
    event_raws = {raw for _, raw, _ in raw_events}
    shared = set(shared_player_ids) == players and len(players) > 1
    raw_title_group = (
        not players
        and not events
        and not player_raws
        and len(event_raws) > 1
        and all(name.decision_kind == "translated" for name, _, _ in raw_events)
    )
    linked_formal_group = (
        not players
        and len(events) == 1
        and not player_raws
        and bool(raw_events)
        and all(
            name.decision_kind == "translated"
            and isinstance(proof, dict)
            and bool(proof.get("linked_literal"))
            and all(item.get("event_id") in events for item in proof["linked_literal"])
            for name, _, proof in raw_events
        )
    )
    raw_player_group = (
        bool(player_raws)
        and (len(players) <= 1 or shared)
        and not events
        and not event_raws
        and all(
            name.generation_rule_version == FIRST_PASS_VERSION
            and isinstance(scope, PreparedRawPlayerScope)
            and bool(scope.members)
            for name, _, scope in raw_players
        )
    )
    raw_event_group = (
        bool(raw_events)
        and not players
        and len(events) <= 1
        and not player_raws
        and all(
            isinstance(proof, dict)
            and not proof.get("record_label")
            and bool(proof.get("first_pass") or proof.get("linked_literal"))
            for _, _, proof in raw_events
        )
    )
    authorized = (
        sum(map(len, (players, events, player_raws, event_raws))) == 1
        or raw_title_group
        or linked_formal_group
        or raw_player_group
        or raw_event_group
        or (shared and (not player_raws or raw_player_group))
    )
    value = {
        "strict": strict,
        "has_exact_player_name": bool(player_rows or raw_players),
        "player_ids": sorted(players) if authorized else [],
        "event_ids": sorted(events) if authorized else [],
        "raw_player_name_ids": sorted({name.id for name, _, _ in raw_players}) if authorized else [],
        "raw_event_name_ids": sorted({name.id for name, _, _ in raw_events}) if authorized else [],
    }
    value["shared_player_ids"] = sorted(players) if shared and authorized else []
    value["mode"] = _mode(value)
    return value


def merge_classifications(exact=None, alias=None):
    """Combine one exact document with the legacy alias lookup from the same mget."""
    value = dict(exact or {})
    if alias and not value.get("strict", alias.get("strict", True)):
        for key in ("player_ids", "event_ids"):
            value[key] = sorted(set(value.get(key, ())) | set(alias.get(key, ())))
        value["strict"] = False
        value["has_exact_player_name"] = value.get("has_exact_player_name", False) or bool(alias.get("player_ids"))
        value["mode"] = _mode(value)
    return value


def literal_wildcard(value):
    return "*" + value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?") + "*"


def _contains(field, value):
    return {"wildcard": {field: {"value": literal_wildcard(value)}}}


def _any(clauses):
    return {"bool": {"should": clauses, "minimum_should_match": 1}} if clauses else {"match_none": {}}


def _owners(classification):
    clauses = []
    for field in ("black_player_id", "white_player_id"):
        if classification.get("player_ids"):
            clauses.append({"terms": {field: classification["player_ids"]}})
    if classification.get("event_ids"):
        clauses.append({"terms": {"event_id": classification["event_ids"]}})
    for field in ("raw_player_name_ids", "raw_event_name_ids"):
        if classification.get(field):
            clauses.append({"terms": {field: classification[field]}})
    return clauses


def _provisional_clauses(classification, q):
    if not classification.get("include_provisional"):
        return []
    clauses = [{"term": {"provisional_player_names": q}}, {"term": {"provisional_override_names": q}}]
    if q not in classification.get("provisional_event_disabled_queries", ()):
        clauses.append({"term": {"provisional_event_names": q}})
        if len(q) >= 3:
            clauses.append(_contains("provisional_event_names", q))
    return clauses


def compile_query(classification, q, player_id):
    """Compile a deterministic album filter; scoring is only a two-level group."""
    classification = dict(classification or {})
    if q and not classification.get("strict", True):
        supplement = classification.get("legacy_player_spellings", {}).get(q, ())
        if supplement:
            classification["player_ids"] = sorted(set(classification.get("player_ids", ())) | set(supplement))
            classification["mode"] = _mode(classification)
    filters = [{"term": {"doc_kind": "album"}}, {"term": {"list_visible": True}}]
    sort = [{"date_sort": {"order": "desc", "missing": "_last"}}, {"id": "desc"}]
    priority = None
    if player_id is not None:
        predicate = (
            _any([{"term": {field: int(player_id)}} for field in ("black_player_id", "white_player_id")])
            if classification.get("public")
            else {"match_none": {}}
        )
    elif not q:
        predicate = {"match_all": {}}
    else:
        mode = classification.get("mode", "generic")
        owners = _owners(classification)
        # Selected-event documents carry only names whose current live slot has
        # the original coverage approval. No album IDs are stored in term docs.
        selected = []
        if mode != "shared_players":
            selected.append(_contains("selected_event_raw_lower", q.lower()))
            if classification.get("event_ids"):
                selected.append({"terms": {"selected_event_id": classification["event_ids"]}})
            if classification.get("raw_event_name_ids"):
                selected.append({"terms": {"selected_event_name_ids": classification["raw_event_name_ids"]}})
        if mode in {"exact_player", "player_raw", "shared_players", "exact_event", "exact_raw_event"}:
            hints = _provisional_clauses(classification, q) if mode == "exact_event" else []
            predicate = _any(owners + selected + hints)
        else:
            terms = [q.lower()]
            if not classification.get("strict", True):
                terms.extend(HISTORICAL_PLAYER_ALIASES.get(q.removeprefix("本因坊"), ()))
            priority = _any(
                [_contains(field, term) for field in ("player_black_lower", "player_white_lower") for term in terms]
            )
            generic = [_contains("search_text", q.lower()), priority, *owners, *selected]
            if not classification.get("has_exact_player_name"):
                generic.append(
                    _any(
                        [
                            {
                                "match": {
                                    f"display.{lang}.event.words": {
                                        "query": q,
                                        "operator": "and",
                                        "zero_terms_query": "none",
                                    }
                                }
                            }
                            for lang in NAME_LANGUAGES
                        ]
                    )
                )
            if not classification.get("strict", True):
                generic.extend(_contains(field, normalize_alias(q)) for field in ("player_aliases", "event_aliases"))
            generic.extend(_provisional_clauses(classification, q))
            predicate = _any(generic)
    filters.append(predicate)
    query = {"bool": {"filter": filters}}
    if priority is not None:
        query["bool"]["should"] = [{"constant_score": {"filter": priority, "boost": 1}}]
        query["bool"]["minimum_should_match"] = 0
        sort.insert(0, {"_score": "desc"})
    return {"query": query, "sort": sort}
