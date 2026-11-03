"""Portable historical as-of ranks, with bounded original-source DB evidence.

The caller owns transactions, the writer lock, snapshot writes and journals.
Only original album scalars/SGFs are evidence: rank profiles and other snapshots
never enter resolution. Applied replay must bind the frozen decision rather than
run the initial qualification check again.
"""

from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re

from sqlalchemy import LargeBinary, and_, cast, func, or_, select
from katrain.core.sgf_parser import ParseError, SGF
from katrain.web.core import models_db as m
from katrain.web.kifu.identity import normalize_alias, player_identity_name
from katrain.web.kifu.name_parse import parse_player
from katrain.web.kifu.source_rank_normalization import (
    normalize_source_rank,
    require,
    snapshot_digest,
    trusted_source_link,
)

SNAPSHOT_VERSION = "kifu-rank-snapshot-v3"
POLICY_VERSION = "historical-rank-as-of-v1"
DATE_POLICY = "precise-original-date-v1"
EXCLUDED_INFERENCE_DATES = frozenset({"1900-01-01", "2002-11-30"})
MAX_INCOMING_GAMES = 100
MAX_OWNERS = 200
MAX_SCALAR_ROWS = 50_000
MAX_SCALAR_BYTES = 32 * 1024 * 1024
MAX_SGF_BYTES = 256 * 1024
MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_BODY_ROWS = 500
CANDIDATE_TIMEOUT_MS = 5000
_FIELDS = set(
    "version policy_version source_ref player_ref raw_rank raw_name display_rank rank_value rank_system "
    "origin target_date basis qualification refusal_reason matched_at content_sha256".split()
)
_REF_FIELDS = {"source_key", "origin_path", "sgf_sha256", "slot"}
_OBSERVATION_FIELDS = {
    "source_ref",
    "player_ref",
    "raw_name",
    "raw_rank",
    "raw_date",
    "rank_value",
    "rank_system",
    "content_sha256",
}
_QUAL_FIELDS = {
    "player_ref",
    "target_date",
    "date_policy",
    "latest_day",
    "latest_original",
    "same_day_ranks",
    "typed_boundary",
    "professional_max",
    "grade_decrease",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SUFFIX = {"professional_dan": "p", "amateur_dan": "d", "kyu": "k", "dan_unspecified": "段"}
_SCALARS = (
    "id",
    "black_player_id",
    "white_player_id",
    "black_rank",
    "white_rank",
    "player_black",
    "player_white",
    "date_played",
    "date_sort",
    "source_path",
)
_LOCAL_FIELDS = {"album_id", "source_link_id", "source_id", "player_id"}


class _Deferred(ValueError):
    pass


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _inference_day(value):
    day = _day(value)
    return day if day not in EXCLUDED_INFERENCE_DATES else None


def _utc(value):
    require(isinstance(value, str), "rank matched_at required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "rank matched_at requires timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _display(rank):
    return str(rank["rank_value"]) + _SUFFIX[rank["rank_system"]]


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode())


@contextmanager
def _bounded_queries(conn):
    """Restore the transaction's parent timeout even after statement cancellation."""
    if conn.dialect.name != "postgresql":
        yield
        return
    previous = conn.exec_driver_sql("SHOW statement_timeout").scalar_one()
    try:
        with conn.begin_nested():
            conn.execute(select(func.set_config("statement_timeout", str(CANDIDATE_TIMEOUT_MS), True)))
            yield
    finally:
        conn.execute(select(func.set_config("statement_timeout", previous, True)))


def _body_length(conn, column):
    return func.octet_length(column) if conn.dialect.name == "postgresql" else func.length(cast(column, LargeBinary))


def _links(conn, ids, *, scalar_budget=MAX_SCALAR_BYTES):
    if not ids:
        return {}
    t, s = m.KifuAlbumSource.__table__, m.KifuSource.__table__
    query = (
        select(t.c.id, t.c.album_id, t.c.source_id, t.c.origin_path, t.c.match_method, s.c.source_key)
        .join(s, s.c.id == t.c.source_id)
        .where(t.c.album_id.in_(ids))
    )
    count = conn.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    scalar = query.subquery()
    lengths = sum(func.coalesce(func.length(scalar.c[key]), 0) for key in ("origin_path", "match_method", "source_key"))
    size = conn.execute(select(func.coalesce(func.sum(lengths), 0))).scalar_one()
    if count > MAX_SCALAR_ROWS or size * 4 + count * 128 > scalar_budget:
        raise _Deferred("source links exceed resource limit")
    result = defaultdict(list)
    used = 0
    for row in conn.execute(query).mappings():
        value = dict(row)
        used += _json_size(value)
        if used > scalar_budget:
            raise _Deferred("source links exceed resource limit")
        result[row["album_id"]].append(value)
    return result


def _owner(conn, entry):
    album, side = entry["album"], entry["side"]
    player_id = album.get(f"{side}_player_id")
    explicit = entry.get("player_ref")
    if explicit is not None:
        _validate_owner(explicit)
    if player_id is not None:
        canonical = conn.execute(
            select(m.KifuPlayer.canonical_name).where(m.KifuPlayer.id == player_id)
        ).scalar_one_or_none()
        require(canonical is not None, "rank target owner missing")
        require(explicit is None or explicit == {"canonical_name": canonical}, "rank target owner mismatch")
        return {"canonical_name": canonical}, player_id
    if explicit is None:
        return None, None
    ids = list(
        conn.execute(select(m.KifuPlayer.id).where(m.KifuPlayer.canonical_name == explicit["canonical_name"])).scalars()
    )
    require(len(ids) <= 1, "rank target canonical owner ambiguous")
    return deepcopy(explicit), ids[0] if ids else None


def _identities(conn, raw_names, owners):
    names = {player_identity_name(x) for x in raw_names if isinstance(x, str)} | {
        owner["canonical_name"] for owner in owners if owner
    }
    tokens = {normalize_alias(name) for name in names}
    index = defaultdict(set)
    for pid, name in conn.execute(
        select(m.KifuPlayer.id, m.KifuPlayer.canonical_name).where(m.KifuPlayer.canonical_name.in_(names))
    ):
        index[normalize_alias(name)].add(pid)
    for pid, token in conn.execute(
        select(m.KifuPlayerAlias.player_id, m.KifuPlayerAlias.normalized_alias).where(
            m.KifuPlayerAlias.normalized_alias.in_(tokens)
        )
    ):
        index[token].add(pid)
    return index


def _name_bound(raw, owner, player_id, index):
    parsed = parse_player(raw, None)
    if parsed.category in {"placeholder", "corrupt_pending"} or not owner:
        return False
    token = normalize_alias(player_identity_name(raw))
    found = index.get(token, set())
    if found:
        return player_id is not None and found == {player_id}
    return token == normalize_alias(owner["canonical_name"])


def _grade(raw_name, raw_rank, source_key):
    parsed = parse_player(raw_name, raw_rank)
    explicit = normalize_source_rank(raw_rank, source_key=source_key) if raw_rank else None
    embedded = normalize_source_rank(parsed.embedded_rank, source_key=source_key) if parsed.embedded_rank else None
    if explicit and embedded:
        if explicit["rank_value"] != embedded["rank_value"] or (
            explicit["rank_system"] != embedded["rank_system"] and embedded["rank_system"] != "dan_unspecified"
        ):
            return None, "root_name_rank_conflict"
    if "rank_conflict" in parsed.exceptions:
        # The older display parser does not understand pro/ama prefixes. Our
        # normalized grade comparison above is authoritative for those forms.
        if not (explicit and embedded and explicit["rank_value"] == embedded["rank_value"]):
            return None, "root_name_rank_conflict"
    if raw_rank and str(raw_rank).strip() and explicit is None:
        return None, "invalid_source_rank"
    return explicit or embedded, None


def _ref(album, side, link):
    return {
        "source_key": link["source_key"],
        "origin_path": link["origin_path"],
        "sgf_sha256": sha256(album["sgf_content"].encode()).hexdigest(),
        "slot": side,
    }


def _validate_original(album, side, links, owner, player_id, index, *, expected_ref=None):
    link = trusted_source_link(album, links)
    require(link is not None, "rank source ownership invalid")
    body = album.get("sgf_content")
    require(isinstance(body, str) and 0 < len(body.encode()) <= MAX_SGF_BYTES, "rank source SGF resource limit")
    try:
        root = SGF.parse_sgf(body)
    except ParseError as exc:
        raise ValueError("rank source SGF invalid") from exc
    # Every literal root binding is checked, including the opposite player.
    for prop, key in (
        ("PB", "player_black"),
        ("PW", "player_white"),
        ("BR", "black_rank"),
        ("WR", "white_rank"),
        ("DT", "date_played"),
    ):
        require((root.get_property(prop, "") or "") == (album.get(key) or ""), "rank source root binding mismatch")
    require(
        owner is None or _name_bound(album.get(f"player_{side}") or "", owner, player_id, index),
        "rank source owner mismatch",
    )
    source_ref = _ref(album, side, link)
    require(expected_ref is None or source_ref == expected_ref, "rank basis source SHA binding mismatch")
    grade, reason = _grade(album.get(f"player_{side}") or "", album.get(f"{side}_rank") or "", link["source_key"])
    return source_ref, grade, reason, link


def _cohort(conn, owner_dates):
    if not owner_dates:
        return [], {}, {}
    a = m.KifuAlbum.__table__
    predicates = [
        and_(or_(a.c.black_player_id == pid, a.c.white_player_id == pid), a.c.date_played <= day)
        for pid, day in owner_dates.items()
    ]
    query = select(*[a.c[k] for k in _SCALARS], _body_length(conn, a.c.sgf_content).label("sgf_bytes")).where(
        or_(*predicates)
    )
    sub = query.subquery()
    count = conn.execute(select(func.count()).select_from(sub)).scalar_one()
    if count * 2 > MAX_SCALAR_ROWS:
        raise _Deferred("rank scalar cohort resource limit")
    # Lengths/scalars precede any SGF body materialization.
    scalar_length = sum(
        func.coalesce(func.length(sub.c[k]), 0) for k in _SCALARS if k != "id" and not k.endswith("_player_id")
    )
    size = conn.execute(select(func.coalesce(func.sum(scalar_length), 0))).scalar_one()
    reserved_bytes = size * 4 + count * 128
    if reserved_bytes > MAX_SCALAR_BYTES:
        raise _Deferred("rank scalar cohort byte limit")
    albums = [dict(row) for row in conn.execute(query).mappings()]
    links = _links(conn, [row["id"] for row in albums], scalar_budget=MAX_SCALAR_BYTES - reserved_bytes)
    names = [row[f"player_{side}"] for row in albums for side in ("black", "white")]
    owners = {
        pid: {"canonical_name": name}
        for pid, name in conn.execute(
            select(m.KifuPlayer.id, m.KifuPlayer.canonical_name).where(m.KifuPlayer.id.in_(owner_dates))
        )
    }
    index = _identities(conn, names, owners.values())
    observations = []
    for album in albums:
        link = trusted_source_link(album, links.get(album["id"], []))
        if not link or not _inference_day(album["date_played"]):
            continue
        for side in ("black", "white"):
            pid = album[f"{side}_player_id"]
            if pid not in owner_dates or album["date_played"] > owner_dates[pid]:
                continue
            if not _name_bound(album[f"player_{side}"], owners.get(pid), pid, index):
                continue
            grade, reason = _grade(album[f"player_{side}"], album[f"{side}_rank"] or "", link["source_key"])
            if grade and reason is None:
                observations.append(
                    {
                        "album": album,
                        "side": side,
                        "link": link,
                        "owner": owners[pid],
                        "player_id": pid,
                        "grade": grade,
                        "day": album["date_played"],
                    }
                )
    return observations, links, index


def _tie(obs):
    # A source path is unique in each DB; no local ID participates in ties.
    return obs["link"]["source_key"], obs["link"]["origin_path"], obs["side"]


def _rank_set(observations):
    return [
        {"rank_value": value, "rank_system": system}
        for value, system in sorted({(x["grade"]["rank_value"], x["grade"]["rank_system"]) for x in observations})
    ]


def _conflict(observations):
    grades = _rank_set(observations)
    return (
        len({g["rank_value"] for g in grades}) > 1
        or len({g["rank_system"] for g in grades if g["rank_system"] != "dan_unspecified"}) > 1
    )


def _qualification(owner, day, observations, source_grade):
    typed = [x for x in observations if x["grade"]["rank_system"] != "dan_unspecified"]
    latest_day = max((x["day"] for x in typed), default=None)
    latest = [x for x in observations if x["day"] == latest_day]
    if source_grade and latest_day == day:
        latest = [*latest, {"grade": source_grade}]
    professional = [x for x in typed if x["grade"]["rank_system"] == "professional_dan"]
    pro_max = max((x["grade"]["rank_value"] for x in professional), default=None)
    candidate = min((x for x in typed if x["day"] == latest_day), key=_tie, default=None)
    boundary = (
        None
        if not candidate
        else {"date": candidate["day"], **{key: candidate["grade"][key] for key in ("rank_value", "rank_system")}}
    )
    chosen_grade = source_grade if source_grade else (candidate or {}).get("grade")
    decrease = bool(
        chosen_grade
        and pro_max
        and chosen_grade["rank_system"] in {"professional_dan", "dan_unspecified"}
        and chosen_grade["rank_value"] < pro_max
    )
    qualification = {
        "player_ref": deepcopy(owner),
        "target_date": day,
        "date_policy": DATE_POLICY,
        "latest_day": latest_day,
        "latest_original": None,
        "same_day_ranks": _rank_set(latest),
        "typed_boundary": boundary,
        "professional_max": pro_max,
        "grade_decrease": decrease,
    }
    reason = None
    if candidate is None:
        reason = "no_prior_original"
    elif _conflict(latest):
        reason = "same_day_conflict"
    elif decrease:
        reason = "professional_grade_decrease"
    elif source_grade and candidate["grade"]["rank_system"] != "professional_dan":
        reason = "typed_boundary"
    return qualification, candidate, reason


def _observation(album, side, source_ref, owner, grade):
    result = {
        "source_ref": source_ref,
        "player_ref": deepcopy(owner),
        "raw_name": album[f"player_{side}"],
        "raw_rank": album.get(f"{side}_rank") or "",
        "raw_date": album.get("date_played") or "",
        "rank_value": grade["rank_value"],
        "rank_system": grade["rank_system"],
    }
    result["content_sha256"] = snapshot_digest(result)
    return result


def prepare_rank_decisions(conn, targets, *, matched_at):
    """Return ``{decisions: [v3, ...], refusals: [{source_ref, reason}, ...]}``.

    Targets are ``{album: full scalar/body dict, side, source_links, player_ref?}``.
    Existing IDs are local bindings only. A proposed incoming album may have no
    ID; its resolved portable owner may be provided in player_ref. Only already
    stored original albums provide historical evidence in this version.
    """
    require(isinstance(targets, (list, tuple)) and len(targets) <= 200, "rank target limit exceeded")
    require(
        len({x["album"]["source_path"] for x in targets}) <= MAX_INCOMING_GAMES, "rank incoming game limit exceeded"
    )
    matched_at = _utc(matched_at)
    owners, owner_dates = [], {}
    for entry in targets:
        require(entry.get("side") in {"black", "white"}, "rank target side invalid")
        owner, pid = _owner(conn, entry)
        owners.append((owner, pid))
    require(len({owner["canonical_name"] for owner, _ in owners if owner}) <= MAX_OWNERS, "rank owner limit exceeded")
    raw_names = [entry["album"].get(f"player_{entry['side']}") or "" for entry in targets]
    index = _identities(conn, raw_names, [owner for owner, _ in owners])
    # Original ownership checks cannot be bypassed by a deferred inference.
    original = []
    body_bytes = 0
    for entry, (owner, pid) in zip(targets, owners):
        body_bytes += len(entry["album"].get("sgf_content", "").encode())
        require(body_bytes <= MAX_BODY_BYTES, "rank target SGF resource limit")
        original.append(_validate_original(entry["album"], entry["side"], entry["source_links"], owner, pid, index))
    for entry, (_, pid), (_, grade, invalid, _) in zip(targets, owners, original):
        day = _inference_day(entry["album"].get("date_played"))
        if pid and day and not invalid and (not grade or grade["rank_system"] == "dan_unspecified"):
            owner_dates[pid] = max(day, owner_dates.get(pid, day))
    deferred = False
    try:
        with _bounded_queries(conn):
            observations, links, cohort_index = _cohort(conn, owner_dates)
    except _Deferred:
        observations, links, cohort_index, deferred = [], {}, {}, True
    decisions, refusals, bodies = [], [], {}
    for entry, (owner, pid), (ref, grade, invalid, _) in zip(targets, owners, original):
        album, side = entry["album"], entry["side"]
        day = _inference_day(album.get("date_played"))
        result_grade, origin, basis, qual, reason = grade, "source" if grade else "unknown", [], None, invalid
        needs_history = not invalid and (grade is None or grade["rank_system"] == "dan_unspecified")
        if needs_history:
            if not day:
                reason = "untrusted_target_date"
            elif not owner or not pid:
                reason = "unusable_identity"
            elif deferred:
                reason = "resource_deferred"
            else:
                cohort = [
                    x
                    for x in observations
                    if x["player_id"] == pid
                    and x["day"] <= day
                    and not (x["album"]["id"] == album.get("id") and x["side"] == side)
                ]
                qual, candidate, reason = _qualification(owner, day, cohort, grade)
                if candidate and not reason:
                    chosen = candidate["album"]
                    try:
                        ident = chosen["id"]
                        if ident not in bodies:
                            if (
                                chosen["sgf_bytes"] > MAX_SGF_BYTES
                                or body_bytes + chosen["sgf_bytes"] > MAX_BODY_BYTES
                                or len(bodies) >= MAX_BODY_ROWS
                            ):
                                raise _Deferred("rank evidence SGF resource limit")
                            with _bounded_queries(conn):
                                body = conn.execute(
                                    select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == ident)
                                ).scalar_one()
                            body_bytes += len(body.encode())
                            bodies[ident] = body
                        chosen = {**chosen, "sgf_content": bodies[ident]}
                        other_ref, other_grade, other_invalid, _ = _validate_original(
                            chosen, candidate["side"], links[ident], owner, pid, cohort_index
                        )
                        require(not other_invalid and other_grade == candidate["grade"], "rank basis grade invalid")
                        proof = _observation(chosen, candidate["side"], other_ref, owner, other_grade)
                        qual["latest_original"] = deepcopy(proof)
                        basis = [proof]
                        result_grade = {
                            "rank_value": grade["rank_value"] if grade else other_grade["rank_value"],
                            "rank_system": "professional_dan" if grade else other_grade["rank_system"],
                        }
                        origin = "historical_type" if grade else "historical_prior"
                    except _Deferred:
                        reason = "resource_deferred"
                    except ValueError:
                        reason = "invalid_original_evidence"
        result = {
            "version": SNAPSHOT_VERSION,
            "policy_version": POLICY_VERSION,
            "source_ref": ref,
            "player_ref": deepcopy(owner),
            "raw_rank": album.get(f"{side}_rank") or "",
            "raw_name": album.get(f"player_{side}") or "",
            "display_rank": _display(result_grade) if result_grade else "",
            "rank_value": result_grade["rank_value"] if result_grade else None,
            "rank_system": result_grade["rank_system"] if result_grade else None,
            "origin": origin,
            "target_date": _day(album.get("date_played")),
            "basis": basis,
            "qualification": qual,
            "refusal_reason": reason,
            "matched_at": matched_at,
        }
        result["content_sha256"] = snapshot_digest(result)
        validate_rank_decision(result)
        decisions.append(result)
        if reason:
            refusals.append({"source_ref": deepcopy(ref), "reason": reason})
    # A body-budget overflow defers all attempted historical decisions, never an
    # order-dependent partial cohort. Explicit source grades still survive.
    if any(x["refusal_reason"] == "resource_deferred" for x in decisions):
        for result, (_, grade, _, _) in zip(decisions, original):
            if result["origin"] in {"historical_type", "historical_prior"}:
                result.update(
                    origin="source" if grade else "unknown",
                    basis=[],
                    refusal_reason="resource_deferred",
                    display_rank=_display(grade) if grade else "",
                    rank_value=grade["rank_value"] if grade else None,
                    rank_system=grade["rank_system"] if grade else None,
                )
                result["content_sha256"] = snapshot_digest(result)
        refusals = [
            {"source_ref": deepcopy(x["source_ref"]), "reason": x["refusal_reason"]}
            for x in decisions
            if x["refusal_reason"]
        ]
    return {"decisions": decisions, "refusals": refusals}


def _validate_owner(owner):
    require(
        owner is None
        or isinstance(owner, dict)
        and set(owner) == {"canonical_name"}
        and isinstance(owner["canonical_name"], str)
        and 0 < len(owner["canonical_name"]) <= 512,
        "rank canonical owner invalid",
    )


def _validate_ref(ref):
    require(
        isinstance(ref, dict)
        and set(ref) == _REF_FIELDS
        and isinstance(ref["slot"], str)
        and ref["slot"] in {"black", "white"}
        and isinstance(ref["source_key"], str)
        and 0 < len(ref["source_key"]) <= 64
        and isinstance(ref["origin_path"], str)
        and 0 < len(ref["origin_path"]) <= 1024
        and isinstance(ref["sgf_sha256"], str)
        and _SHA.fullmatch(ref["sgf_sha256"]),
        "rank source ref invalid",
    )


def _validate_observation(proof):
    require(isinstance(proof, dict) and set(proof) == _OBSERVATION_FIELDS, "rank basis shape invalid")
    _validate_ref(proof["source_ref"])
    _validate_owner(proof["player_ref"])
    require(
        proof["player_ref"] is not None and _inference_day(proof["raw_date"]) is not None,
        "rank basis owner/date invalid",
    )
    require(proof["content_sha256"] == snapshot_digest(proof), "rank basis hash invalid")
    require(
        isinstance(proof["raw_name"], str)
        and len(proof["raw_name"]) <= 1024
        and isinstance(proof["raw_rank"], str)
        and len(proof["raw_rank"]) <= 128,
        "rank basis raw invalid",
    )
    grade, reason = _grade(proof["raw_name"], proof["raw_rank"], proof["source_ref"]["source_key"])
    require(
        not reason
        and grade
        and grade["rank_system"] != "dan_unspecified"
        and all(proof[k] == grade[k] for k in ("rank_value", "rank_system")),
        "rank basis original grade invalid",
    )


def validate_rank_decision(decision):
    """Validate portable shape, policy, canonical display and self-contained proof."""
    require(isinstance(decision, dict) and set(decision) == _FIELDS, "rank decision shape invalid")
    require(
        decision["version"] == SNAPSHOT_VERSION and decision["policy_version"] == POLICY_VERSION,
        "rank decision policy invalid",
    )
    require(decision["content_sha256"] == snapshot_digest(decision), "rank decision hash mismatch")
    require(_json_size(decision) <= 32 * 1024, "rank decision resource limit")
    _validate_ref(decision["source_ref"])
    _validate_owner(decision["player_ref"])
    for key, limit in (("raw_rank", 128), ("raw_name", 1024), ("display_rank", 128)):
        require(isinstance(decision[key], str) and len(decision[key]) <= limit, "rank decision raw/display invalid")
    require(
        decision["target_date"] is None or _day(decision["target_date"]) == decision["target_date"],
        "rank target date invalid",
    )
    _utc(decision["matched_at"])
    require(
        isinstance(decision["origin"], str)
        and decision["origin"] in {"source", "historical_type", "historical_prior", "unknown"},
        "rank origin invalid",
    )
    require(
        decision["refusal_reason"] is None
        or isinstance(decision["refusal_reason"], str)
        and 0 < len(decision["refusal_reason"]) <= 64,
        "rank refusal invalid",
    )
    if decision["rank_value"] is None:
        require(
            decision["rank_system"] is None
            and decision["display_rank"] == ""
            and decision["origin"] == "unknown"
            and decision["refusal_reason"],
            "unknown rank decision invalid",
        )
    else:
        require(
            type(decision["rank_value"]) is int
            and isinstance(decision["rank_system"], str)
            and decision["rank_system"] in _SUFFIX
            and 1 <= decision["rank_value"] <= (30 if decision["rank_system"] == "kyu" else 9)
            and decision["display_rank"] == _display(decision),
            "rank canonical display invalid",
        )
    require(isinstance(decision["basis"], list) and len(decision["basis"]) <= 1, "rank finite basis invalid")
    for proof in decision["basis"]:
        _validate_observation(proof)
        require(
            proof["player_ref"] == decision["player_ref"] and proof["raw_date"] <= decision["target_date"],
            "rank basis owner/date mismatch",
        )
    qual = decision["qualification"]
    require(qual is None or isinstance(qual, dict) and set(qual) == _QUAL_FIELDS, "rank qualification shape invalid")
    if qual:
        require(
            qual["player_ref"] == decision["player_ref"]
            and qual["target_date"] == decision["target_date"]
            and qual["date_policy"] == DATE_POLICY
            and isinstance(qual["same_day_ranks"], list)
            and len(qual["same_day_ranks"]) <= 120,
            "rank qualification owner/date/policy invalid",
        )
        require(
            qual["latest_day"] is None
            or _inference_day(qual["latest_day"])
            and qual["latest_day"] <= decision["target_date"],
            "rank qualification latest date invalid",
        )
        require(
            type(qual["grade_decrease"]) is bool
            and (
                qual["professional_max"] is None
                or type(qual["professional_max"]) is int
                and 1 <= qual["professional_max"] <= 9
            ),
            "rank qualification professional grade guard invalid",
        )
        ranks = qual["same_day_ranks"]
        require(
            isinstance(ranks, list)
            and all(
                isinstance(rank, dict)
                and set(rank) == {"rank_value", "rank_system"}
                and type(rank["rank_value"]) is int
                and isinstance(rank["rank_system"], str)
                and rank["rank_system"] in _SUFFIX
                and 1 <= rank["rank_value"] <= (30 if rank["rank_system"] == "kyu" else 9)
                for rank in ranks
            ),
            "rank qualification grade set invalid",
        )
        require(
            ranks
            == [
                {"rank_value": number, "rank_system": system}
                for number, system in sorted({(rank["rank_value"], rank["rank_system"]) for rank in ranks})
            ],
            "rank qualification grade set order invalid",
        )
        boundary = qual["typed_boundary"]
        require(
            boundary is None
            or isinstance(boundary, dict)
            and set(boundary) == {"date", "rank_value", "rank_system"}
            and boundary["date"] == qual["latest_day"]
            and {k: boundary[k] for k in ("rank_value", "rank_system")} in ranks
            and boundary["rank_system"] != "dan_unspecified",
            "rank qualification typed boundary invalid",
        )
        proof = qual["latest_original"]
        if proof is not None:
            _validate_observation(proof)
            require(
                proof["raw_date"] == qual["latest_day"]
                and proof["player_ref"] == decision["player_ref"]
                and {k: proof[k] for k in ("rank_value", "rank_system")} in ranks
                and boundary == {"date": proof["raw_date"], **{k: proof[k] for k in ("rank_value", "rank_system")}},
                "rank qualification latest observation mismatch",
            )
    grade, invalid = _grade(decision["raw_name"], decision["raw_rank"], decision["source_ref"]["source_key"])
    if decision["origin"] in {"historical_type", "historical_prior"}:
        require(
            decision["player_ref"] is not None
            and _inference_day(decision["target_date"])
            and qual
            and decision["refusal_reason"] is None
            and len(decision["basis"]) == 1
            and qual["latest_original"] == decision["basis"][0]
            and not qual["grade_decrease"]
            and len({r["rank_value"] for r in qual["same_day_ranks"]}) == 1
            and len({r["rank_system"] for r in qual["same_day_ranks"] if r["rank_system"] != "dan_unspecified"}) == 1,
            "rank historical qualification invalid",
        )
        proof = decision["basis"][0]
        require(
            decision["rank_system"] != "professional_dan"
            or qual["professional_max"] is not None
            and proof["rank_value"] <= qual["professional_max"] <= decision["rank_value"],
            "rank historical professional grade guard invalid",
        )
        if decision["origin"] == "historical_type":
            require(
                grade
                and grade["rank_system"] == "dan_unspecified"
                and decision["rank_value"] == grade["rank_value"]
                and decision["rank_system"] == proof["rank_system"] == "professional_dan",
                "rank type refinement invalid",
            )
        else:
            require(
                not grade and not invalid and all(decision[k] == proof[k] for k in ("rank_value", "rank_system")),
                "rank historical prior invalid",
            )
    else:
        require(not decision["basis"], "rank source/unknown cannot carry inference")
        if decision["origin"] == "unknown":
            require(not grade, "unknown rank decision hides a source grade")
        if decision["origin"] == "source":
            require(
                grade and not invalid and all(decision[k] == grade[k] for k in ("rank_value", "rank_system")),
                "rank source grade mismatch",
            )
    return decision


def _live_target(conn, target):
    album = target["album"]
    if album.get("id") is None:
        return target
    a = m.KifuAlbum.__table__
    live = (
        conn.execute(
            select(*[a.c[k] for k in _SCALARS], _body_length(conn, a.c.sgf_content).label("sgf_bytes"))
            .where(a.c.id == album["id"])
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    require(live is not None, "rank target binding missing")
    require(0 < live["sgf_bytes"] <= MAX_SGF_BYTES, "rank target SGF resource limit")
    live = dict(live)
    live["sgf_content"] = conn.execute(select(a.c.sgf_content).where(a.c.id == album["id"])).scalar_one()
    return {**target, "album": live, "source_links": _links(conn, [album["id"]]).get(album["id"], [])}


def verify_initial_rank_decisions(conn, targets, decisions):
    """Under the caller's writer lock, reject changed first-apply qualification.

    Source/unknown decisions are frozen as such; newly available evidence does
    not force an upgrade. Historical decisions must match fresh complete bounded
    qualification. This function makes no business writes and never reselects.
    """
    require(len(targets) == len(decisions), "rank target decision count mismatch")
    if conn.dialect.name == "postgresql":
        require(conn.get_isolation_level() == "READ COMMITTED", "rank initial qualification requires READ COMMITTED")
        conn.exec_driver_sql(
            "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, "
            "kifu_player_aliases, kifu_player_names, kifu_album_rank_snapshots IN SHARE ROW EXCLUSIVE MODE"
        )
    live_targets = [_live_target(conn, target) for target in targets]
    for target, decision in zip(live_targets, decisions):
        validate_rank_decision(decision)
        _bind_target(conn, target, decision)
    historical = [
        (target, decision)
        for target, decision in zip(live_targets, decisions)
        if decision["origin"] in {"historical_type", "historical_prior"}
    ]
    if historical:
        # All use a single shared frozen timestamp in a normal batch; supporting
        # legacy mixed freezes does not let wall-clock time influence rank facts.
        for timestamp in sorted({decision["matched_at"] for _, decision in historical}):
            subset = [(target, decision) for target, decision in historical if decision["matched_at"] == timestamp]
            fresh = prepare_rank_decisions(conn, [target for target, _ in subset], matched_at=timestamp)["decisions"]
            for current, (_, frozen) in zip(fresh, subset):
                require(current == frozen, "rank initial qualification/cohort changed")
    return decisions


def _bind_target(conn, target, decision):
    owner, pid = _owner(conn, target)
    album, side = target["album"], target["side"]
    index = _identities(conn, [album.get(f"player_{side}") or ""], [owner])
    ref, _, _, link = _validate_original(
        album, side, target["source_links"], owner, pid, index, expected_ref=decision["source_ref"]
    )
    require(
        owner == decision["player_ref"]
        and (album.get(f"{side}_rank") or "") == decision["raw_rank"]
        and (album.get(f"player_{side}") or "") == decision["raw_name"]
        and _day(album.get("date_played")) == decision["target_date"],
        "rank target owner/raw/date binding mismatch",
    )
    return {
        "album_id": album.get("id"),
        "side": side,
        "player_id": album.get(f"{side}_player_id"),
        "source_link_id": link.get("id"),
        "source_id": link.get("source_id"),
        "source_ref": ref,
        "snapshot_sha256": decision["content_sha256"],
    }


def bind_rank_decision(conn, target, decision):
    """Resolve exact frozen portable proofs to local IDs, without as-of reselection.

    Store returned objects at applied_artifact['basis_bindings']. Target IDs must
    be populated by the caller after insertion. No IDs enter snapshot bytes.
    """
    validate_rank_decision(decision)
    target_binding = _bind_target(conn, _live_target(conn, target), decision)
    bindings = []
    used = 0
    for proof in decision["basis"]:
        ref = proof["source_ref"]
        a = m.KifuAlbum.__table__
        candidates = list(
            conn.execute(
                select(*[a.c[k] for k in _SCALARS], _body_length(conn, a.c.sgf_content).label("sgf_bytes"))
                .where(a.c.source_path == ref["origin_path"])
                .with_for_update()
            ).mappings()
        )
        require(len(candidates) == 1, "rank basis source missing/ambiguous")
        album = dict(candidates[0])
        used += album["sgf_bytes"]
        require(album["sgf_bytes"] <= MAX_SGF_BYTES and used <= MAX_BODY_BYTES, "rank basis SGF resource limit")
        album["sgf_content"] = conn.execute(select(a.c.sgf_content).where(a.c.id == album["id"])).scalar_one()
        side = ref["slot"]
        entry = {"album": album, "side": side, "player_ref": proof["player_ref"]}
        owner, pid = _owner(conn, entry)
        require(album.get(f"{side}_player_id") is not None, "rank basis owner binding missing")
        index = _identities(conn, [album[f"player_{side}"]], [owner])
        links = _links(conn, [album["id"]]).get(album["id"], [])
        actual_ref, grade, invalid, link = _validate_original(album, side, links, owner, pid, index, expected_ref=ref)
        require(
            not invalid and grade and _observation(album, side, actual_ref, owner, grade) == proof,
            "rank basis observation binding mismatch",
        )
        bindings.append(
            {
                "album_id": album["id"],
                "source_link_id": link["id"],
                "source_id": link["source_id"],
                "player_id": pid,
                "source_ref": actual_ref,
                "observation_sha256": proof["content_sha256"],
            }
        )
    result = {"target": target_binding, "basis": bindings}
    result["content_sha256"] = snapshot_digest(result)
    return result


def assert_retained_rank_basis(conn, removed_bindings, *, excluding_batch_ids=()):
    """Refuse compensation that would invalidate any applied v3 original basis.

    removed_bindings is a finite list of dictionaries containing album_id,
    source_link_id, source_id and/or player_id. Applied native and standalone
    repair journals use the same artifact top-level basis_bindings convention.
    Missing/invalid proof for a potentially dependent snapshot fails closed.
    """
    require(
        isinstance(removed_bindings, (list, tuple)) and len(removed_bindings) <= MAX_SCALAR_ROWS,
        "rank removed binding limit exceeded",
    )
    removed = {key: set() for key in _LOCAL_FIELDS}
    for entry in removed_bindings:
        require(
            isinstance(entry, dict) and set(entry).issubset(_LOCAL_FIELDS) and entry,
            "rank removed binding shape invalid",
        )
        for key, value in entry.items():
            require(type(value) is int and value > 0, "rank removed binding id invalid")
            removed[key].add(value)
    if not any(removed.values()):
        return
    t, b, j = m.KifuAlbumRankSnapshot.__table__, m.KifuNameBatch.__table__, m.KifuNameChange.__table__
    # Stream stored snapshots rather than warming original SGF bodies. JSON
    # version filtering is portable across the two supported databases.
    query = select(t).where(t.c.snapshot["version"].as_string() == SNAPSHOT_VERSION)
    for row in conn.execute(query).mappings():
        if row["native_batch_id"] in excluding_batch_ids:
            continue
        snapshot = row["snapshot"]
        require(row["snapshot_sha256"] == snapshot.get("content_sha256"), "retained rank basis row hash invalid")
        try:
            validate_rank_decision(snapshot)
        except ValueError as exc:
            raise ValueError("retained rank basis snapshot invalid") from exc
        if not snapshot["basis"]:
            continue
        batch = conn.execute(select(b).where(b.c.id == row["native_batch_id"])).mappings().one_or_none()
        require(batch is not None and batch["status"] == "applied", "retained rank basis applied artifact missing")
        changes = list(
            conn.execute(
                select(j.c.after_image).where(
                    j.c.batch_id == batch["id"], j.c.target_table == t.name, j.c.target_row_id == row["id"]
                )
            ).scalars()
        )
        require(len(changes) == 1 and changes[0] == dict(row), "retained rank basis journal invalid")
        artifact = batch["reviewed_artifact"]
        require(
            isinstance(artifact, dict) and isinstance(artifact.get("basis_bindings"), list),
            "retained rank basis artifact missing",
        )
        matching = [
            binding
            for binding in artifact["basis_bindings"]
            if isinstance(binding, dict)
            and binding.get("target", {}).get("album_id") == row["album_id"]
            and binding.get("target", {}).get("side") == row["side"]
        ]
        require(len(matching) == 1, "retained rank basis local binding missing")
        binding = matching[0]
        require(binding.get("content_sha256") == snapshot_digest(binding), "retained rank basis binding hash invalid")
        live = bind_rank_decision(conn, {"album": {"id": row["album_id"]}, "side": row["side"]}, snapshot)
        require(live == binding, "retained rank basis local binding changed")
        for basis in binding["basis"]:
            require(
                not any(basis[key] in removed[key] for key in _LOCAL_FIELDS),
                "retained rank basis dependency prevents undo",
            )
