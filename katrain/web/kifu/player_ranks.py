"""Bounded, read-only rank discovery and transaction-owned rank observations.

Facts are portable JSON. Their digest covers the exact grade and identity
captures, not database IDs, retry timestamps, or the mutable current projection.
No function creates tables, performs HTTP, or commits its caller's transaction.
"""

from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re
import unicodedata
from urllib.parse import parse_qs, urlparse

from sqlalchemy import LargeBinary, and_, cast, func, literal, select, union_all

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumRankSnapshot,
    KifuNameResearchEvidence,
    KifuPlayer,
    KifuPlayerName,
    KifuPlayerRankHistory,
)
from katrain.web.kifu.name_parse import parse_player

FACT_VERSION = "kifu-rank-fact-v1"
IDENTITY_VERSION = "official-rank-identity-v1"
MAX_PLAYERS = 200
MAX_SGF_BYTES = 256 * 1024
MAX_CAPTURE_CHARS = 16 * 1024
MAX_FACT_BYTES = 320 * 1024
MAX_TOTAL_SGF_BYTES = 8 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DIGITS = "一二三四五六七八九"
_FACT_FIELDS = {
    "version",
    "player_ref",
    "rank_value",
    "rank_system",
    "source_as_of",
    "valid_from",
    "source_kind",
    "source_ref",
    "evidence",
    "observed_at",
    "content_sha256",
}
# Deliberately finite first-slice subjects; no name search or broad profile scraper.
_SUBJECTS = {
    "ki000489": "上野梨紗",
    "ki000434_5": "藤沢里菜",
    "CWA000149": "唐奕",
    "CWA000548": "高星",
    "20000805": "高星",
    "20001261": "周泓余",
    "20000627": "王爽",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _name(value):
    return "".join(unicodedata.normalize("NFC", str(value)).replace("\\u3000", " ").split())


def _day(value):
    if value is None:
        return None
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "invalid rank basis date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid rank basis date") from exc


def _utc(value=None):
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        parsed = value
    else:
        _require(isinstance(value, str), "invalid observation time")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "observation time must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def normalize_rank(raw_rank, *, professional_identity=False):
    """Parse grade and system; a boolean here is parsing context, never authority.

    Bare 段 stays dan_unspecified unless a separately verified same-person
    professional identity is supplied. Explicit d remains amateur even then.
    """
    if not isinstance(raw_rank, str):
        return None
    raw = "".join(unicodedata.normalize("NFKC", raw_rank).split()).casefold()
    match = re.fullmatch(r"([1-9]\d?)(p|pro|d|dan|k|kyu)", raw)
    if match:
        number, suffix = match.groups()
        system = "professional_dan" if suffix in {"p", "pro"} else "kyu" if suffix in {"k", "kyu"} else "amateur_dan"
        value = int(number)
    else:
        match = re.fullmatch(r"(职业|職業|业余|業餘)?([一二三四五六七八九初]|[1-9]\d?)(段|级|級)", raw)
        if not match:
            return None
        prefix, number, suffix = match.groups()
        value = 1 if number == "初" else _DIGITS.index(number) + 1 if number in _DIGITS else int(number)
        system = (
            "kyu"
            if suffix in {"级", "級"}
            else (
                "professional_dan"
                if prefix in {"职业", "職業"}
                else "amateur_dan" if prefix in {"业余", "業餘"} else "dan_unspecified"
            )
        )
        if system == "dan_unspecified" and professional_identity:
            system = "professional_dan"
    if not 1 <= value <= (30 if system == "kyu" else 9):
        return None
    return {"rank_value": value, "rank_system": system}


def rank_fact_sha256(fact):
    """Digest immutable portable content; first observation time is retained separately."""
    immutable = {key: fact[key] for key in sorted(_FACT_FIELDS - {"observed_at", "content_sha256"})}
    return _digest(immutable)


def _sgf_grade(sgf_content, slot):
    _require(slot in {"black", "white"}, "invalid rank slot")
    _require(
        isinstance(sgf_content, str) and 0 < len(sgf_content.encode("utf-8")) <= MAX_SGF_BYTES,
        "rank SGF exceeds evidence limit",
    )
    root = SGF.parse_sgf(sgf_content)
    prefix = "B" if slot == "black" else "W"
    raw_name = root.get_property("P" + prefix, "")
    raw_rank = root.get_property(prefix + "R", "")
    parsed = parse_player(raw_name, raw_rank)
    _require("rank_conflict" not in parsed.exceptions, "SGF rank/name conflict")
    # Invalid BR/WR never permits silently substituting a different embedded grade.
    if raw_rank and str(raw_rank).strip():
        rank = str(raw_rank).strip() if normalize_rank(raw_rank) else None
    else:
        rank = parsed.embedded_rank
    raw_date = root.get_property("DT", "")
    try:
        basis = _day(raw_date).isoformat() if raw_date else None
    except ValueError:
        basis = None  # Partial/multiple/raw dates are not precise basis dates.
    return rank, raw_name, basis, raw_date


def _official_subject(capture, original_name):
    """Read only the exact official subject field, never a first/max dan mention."""
    _require(isinstance(capture, dict), "official capture missing")
    body = capture.get("body_excerpt")
    body_hash = capture.get("body_sha256")
    _require(
        isinstance(body, str)
        and 0 < len(body) <= MAX_CAPTURE_CHARS
        and isinstance(body_hash, str)
        and _SHA.fullmatch(body_hash),
        "official capture body/hash missing",
    )
    _require(capture.get("http_status") == 200, "official capture HTTP status invalid")
    url = capture.get("resolved_url") or capture.get("url")
    _require(isinstance(url, str), "official capture URL missing")
    parsed = urlparse(url)
    _require(
        parsed.scheme == "https" and not parsed.username and not parsed.password and not parsed.fragment,
        "official capture URL invalid",
    )
    compact = " ".join(body.split())
    subject_key = None
    subject_name = None
    grade_field = None
    if parsed.netloc == "www.nihonkiin.or.jp":
        path = re.fullmatch(r"/player/htm/(ki000489|ki000434_5)\.html", parsed.path)
        _require(path and not parsed.query, "unsupported official subject")
        subject_key = path.group(1)
        subject_name = _SUBJECTS[subject_key]
        _require(_name(subject_name) == _name(original_name), "official subject differs from reviewed owner")
        # The profile heading must precede its specific 棋士段位 label.
        heading = re.search(
            re.escape(subject_name[0:2])
            + r"\s*"
            + re.escape(subject_name[2:])
            + r".{0,160}?棋士段位\s*([一二三四五六七八九])段",
            compact,
        )
        _require(heading, "official subject rank label missing")
        grade_field = {"field": "棋士段位", "value": heading.group(1) + "段"}
    elif parsed.netloc == "wqapi.cwql.org.cn" and parsed.path == "/playerInfo/professional/list" and not parsed.query:
        # A captured roster may begin/end mid-response. Decode only complete records.
        targets = []
        for match in re.finditer(r'\{[^{}]*"playerNo"\s*:[^{}]*\}', body):
            try:
                record = json.loads(match.group())
            except ValueError:
                continue
            if _name(record.get("playerName", "")) == _name(original_name):
                targets.append(record)
        _require(len(targets) == 1, "official roster owner is not unique")
        record = targets[0]
        subject_key, subject_name = record.get("playerNo"), record.get("playerName")
        _require(
            subject_key in {"CWA000149", "CWA000548"} and _SUBJECTS[subject_key] == subject_name,
            "official roster subject mismatch",
        )
        grade_field = {
            "field": "professional_roster_membership",
            "value": subject_key,
            "playerName": subject_name,
            "playerGrade": record.get("playerGrade"),
        }
    elif parsed.netloc in {"www.baduk.or.kr", "m.baduk.or.kr"}:
        query = parse_qs(parsed.query)
        if parsed.netloc == "m.baduk.or.kr" and parsed.path == "/record/gisa_info.asp":
            _require(set(query) == {"PRPL_CODE"} and len(query["PRPL_CODE"]) == 1, "official subject key invalid")
            subject_key = query["PRPL_CODE"][0]
            _require(subject_key == "20000805", "unsupported official subject")
            subject_name = _SUBJECTS[subject_key]
            match = re.search(r"기사정보\s+([1-9])단\s+가오싱\s*\(\s*高星\s*\)", compact)
        else:
            _require(
                parsed.netloc == "www.baduk.or.kr"
                and parsed.path == "/record/player_view.asp"
                and set(query) == {"pkey"}
                and len(query["pkey"]) == 1,
                "unsupported official subject",
            )
            subject_key = query["pkey"][0]
            _require(subject_key in {"20001261", "20000627"}, "unsupported official subject")
            subject_name = _SUBJECTS[subject_key]
            korean = "저우훙위" if subject_key == "20001261" else "왕솽"
            match = re.search(r"기사정보 상세\s+" + korean + r"\s*\(\s*" + subject_name + r"\s*\)\s*([1-9])단", compact)
        _require(match and _name(subject_name) == _name(original_name), "official subject/heading differs from owner")
        grade_field = {"field": "기사정보 subject heading", "value": match.group(1) + "단"}
    else:
        raise ValueError("unsupported official rank source")
    return {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "identity_field": grade_field,
        "url": url,
        "body_sha256": body_hash,
        "body_excerpt": body,
    }


def _identity_proof(canonical_name, approved_name, original_name, capture, capture_path):
    proof = {
        "version": IDENTITY_VERSION,
        "owner_ref": {"canonical_name": canonical_name},
        "approved_name": approved_name,
        "original_name": original_name,
        "capture_path": capture_path,
        **_official_subject(capture, original_name),
    }
    proof["capture_sha256"] = _digest(proof)
    return proof


def _validate_identity(proof, canonical_name):
    _require(
        isinstance(proof, dict)
        and proof.get("version") == IDENTITY_VERSION
        and proof.get("owner_ref") == {"canonical_name": canonical_name},
        "professional identity owner invalid",
    )
    _require(
        set(proof)
        == {
            "version",
            "owner_ref",
            "approved_name",
            "original_name",
            "capture_path",
            "subject_key",
            "subject_name",
            "identity_field",
            "url",
            "body_sha256",
            "body_excerpt",
            "capture_sha256",
        },
        "professional identity shape invalid",
    )
    original = deepcopy(proof)
    expected_hash = original.pop("capture_sha256", None)
    _require(expected_hash == _digest(original), "professional capture digest mismatch")
    parsed = _official_subject(
        {
            "url": proof["url"],
            "body_sha256": proof["body_sha256"],
            "body_excerpt": proof["body_excerpt"],
            "http_status": 200,
        },
        proof["original_name"],
    )
    _require(all(proof.get(key) == value for key, value in parsed.items()), "professional subject evidence mismatch")
    return proof


def build_source_rank_fact(
    *,
    canonical_name,
    raw_rank,
    sgf_content,
    slot,
    source_ref,
    source_as_of=None,
    identity_evidence=None,
    observed_at=None,
    valid_from=None,
):
    """Freeze a verifiable explicit SGF grade; metadata-only grades return None.

    ``identity_evidence`` must be the proof returned by library lookup (and is
    checked against the target database again by the native transaction helper).
    An ordinary game date can never establish a promotion's valid_from date.
    """
    _require(isinstance(canonical_name, str) and 0 < len(canonical_name) <= 512, "canonical owner missing")
    _require(valid_from is None, "source SGF cannot establish valid_from")
    actual_rank, raw_name, basis, raw_date = _sgf_grade(sgf_content, slot)
    if actual_rank is None:
        return None
    _require(actual_rank == raw_rank, "raw rank differs from exact source slot")
    if identity_evidence is not None:
        _validate_identity(identity_evidence, canonical_name)
    parsed = normalize_rank(raw_rank, professional_identity=identity_evidence is not None)
    if parsed is None:
        return None
    date_kind = "sgf_dt" if basis is not None else "unknown"
    if source_as_of is not None:
        provided_day = _day(source_as_of).isoformat()
        if raw_date:
            _require(provided_day == basis, "rank basis differs from exact SGF date")
        else:
            basis, date_kind = provided_day, "album_date_sort"
    _require(
        isinstance(source_ref, dict)
        and set(source_ref) <= {"source_key", "source_item_id", "sgf_sha256", "slot", "kind"}
        and isinstance(source_ref.get("source_key"), str)
        and re.fullmatch(r"[a-z0-9_-]{1,64}", source_ref["source_key"])
        and isinstance(source_ref.get("source_item_id"), str)
        and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", source_ref["source_item_id"]),
        "source reference invalid",
    )
    ref = {
        "kind": "explicit_album_rank",
        "source_key": source_ref["source_key"],
        "source_item_id": source_ref["source_item_id"],
        "sgf_sha256": sha256(sgf_content.encode("utf-8")).hexdigest(),
        "slot": slot,
    }
    _require(all(source_ref.get(key, value) == value for key, value in ref.items()), "source reference/hash mismatch")
    fact = {
        "version": FACT_VERSION,
        "player_ref": {"canonical_name": canonical_name},
        **parsed,
        "source_as_of": basis,
        "valid_from": None,
        "source_kind": "explicit_album_rank",
        "source_ref": ref,
        "evidence": {
            "grade": {
                "raw_rank": raw_rank,
                "raw_name": raw_name,
                "sgf_content": sgf_content,
                "date_basis": {"kind": date_kind, "value": basis},
            },
            "professional_identity": deepcopy(identity_evidence),
        },
        "observed_at": _utc(observed_at),
    }
    fact["content_sha256"] = rank_fact_sha256(fact)
    _require(len(_json(fact).encode("utf-8")) <= MAX_FACT_BYTES, "rank fact exceeds evidence limit")
    return fact


def validate_rank_fact(fact, *, canonical_name=None):
    """Recompute portable content and exact grade fields; this alone is not DB authority."""
    _require(
        isinstance(fact, dict) and set(fact) == _FACT_FIELDS and fact.get("version") == FACT_VERSION,
        "rank fact shape/version invalid",
    )
    _require(len(_json(fact).encode("utf-8")) <= MAX_FACT_BYTES, "rank fact exceeds evidence limit")
    _require(type(fact["rank_value"]) is int, "rank value must be an integer")
    owner = fact.get("player_ref")
    _require(isinstance(owner, dict) and set(owner) == {"canonical_name"}, "rank fact owner invalid")
    if canonical_name is not None:
        _require(owner["canonical_name"] == canonical_name, "rank fact canonical owner mismatch")
    _require(
        fact["source_kind"] == "explicit_album_rank"
        and isinstance(fact["source_ref"], dict)
        and set(fact["source_ref"]) == {"kind", "source_key", "source_item_id", "sgf_sha256", "slot"},
        "rank fact source invalid",
    )
    evidence = fact.get("evidence")
    _require(
        isinstance(evidence, dict)
        and set(evidence) == {"grade", "professional_identity"}
        and isinstance(evidence["grade"], dict)
        and set(evidence["grade"]) == {"raw_rank", "raw_name", "sgf_content", "date_basis"},
        "rank grade evidence invalid",
    )
    grade = evidence["grade"]
    rebuilt = build_source_rank_fact(
        canonical_name=owner["canonical_name"],
        raw_rank=grade["raw_rank"],
        sgf_content=grade["sgf_content"],
        slot=fact["source_ref"]["slot"],
        source_ref=fact["source_ref"],
        source_as_of=fact["source_as_of"],
        valid_from=fact["valid_from"],
        observed_at=fact["observed_at"],
        identity_evidence=evidence["professional_identity"],
    )
    _require(rebuilt is not None and rebuilt == fact, "rank fact content/hash mismatch")
    return fact


def _approved_context(conn, player_ids):
    """Batch owner/name binding; i18n is consulted only after IDs are supplied."""
    n, e = KifuPlayerName.__table__, KifuNameResearchEvidence.__table__
    rows = (
        conn.execute(
            select(n, e.c.research_payload)
            .join(
                e,
                and_(
                    n.c.evidence_id == e.c.id,
                    n.c.player_id == e.c.player_id,
                    n.c.lang == e.c.lang,
                    n.c.revision == e.c.revision,
                    n.c.display_name == e.c.candidate_name,
                    n.c.decision_kind == e.c.decision_kind,
                    n.c.generation_rule_version == e.c.generation_rule_version,
                ),
            )
            .where(
                n.c.player_id.in_(player_ids),
                n.c.status == "verified",
                e.c.review_status == "approved",
                e.c.reviewer_id.is_not(None),
                e.c.reviewer_id != e.c.producer_id,
                e.c.reviewed_at.is_not(None),
                e.c.producer_model.is_not(None),
                e.c.reviewer_model.is_not(None),
            )
        )
        .mappings()
        .all()
    )
    names, proofs = {}, {}
    canonical = dict(
        conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.id.in_(player_ids))).all()
    )
    for row in rows:
        player_id = row["player_id"]
        names.setdefault(player_id, set()).add(row["display_name"])
        payload = row["research_payload"]
        if not isinstance(payload, dict):
            continue
        research, candidate = payload.get("research"), payload.get("candidate")
        owner = {"kind": "player", "id": player_id}
        if (
            not isinstance(research, dict)
            or not isinstance(candidate, dict)
            or research.get("owner") != owner
            or candidate.get("owner") != owner
        ):
            continue
        if (
            research.get("candidate_name") != row["display_name"]
            or candidate.get("display_name") != row["display_name"]
        ):
            continue
        original_name = research.get("original_name")
        if not isinstance(original_name, str):
            continue

        # Only real source captures under source_checks are eligible. Comments,
        # identity_basis and inventory excerpts cannot establish a profession.
        def visit(value, path):
            if isinstance(value, dict):
                if "url" in value and "body_excerpt" in value:
                    try:
                        proof = _identity_proof(canonical[player_id], row["display_name"], original_name, value, path)
                    except (ValueError, TypeError):
                        pass
                    else:
                        proofs.setdefault(player_id, []).append(proof)
                for key, child in value.items():
                    if key in {"identity_basis", "review_conclusion"}:
                        continue
                    visit(child, path + "." + key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{path}[{index}]")

        visit(research.get("source_checks", []), "research.source_checks")
    return names, proofs


def lookup_professional_identity_evidence(conn, player_ids):
    """Read approved finite official identities for already-bound local players."""
    _require(
        isinstance(player_ids, (list, tuple, set))
        and len(player_ids) <= MAX_PLAYERS
        and all(type(value) is int and value > 0 for value in player_ids),
        "player identity limit invalid",
    )
    if not player_ids:
        return {}
    _names, proofs = _approved_context(conn, player_ids)
    return {player_id: min(values, key=lambda value: value["capture_sha256"]) for player_id, values in proofs.items()}


def _source_path(ref):
    return f"data/kifu-album/{ref['source_key']}/{ref['source_item_id']}.sgf"


def verify_rank_fact_for_player(conn, player_id, fact, *, source_games=()):
    """Verify fixed evidence against this target's exact owner and captured sources.

    source_games may anchor exact manifest games that have not been inserted yet.
    Library facts otherwise require the existing album's side FK, raw rank,
    source path and whole SGF hash. This never rediscovers today's grade.
    """
    canonical = conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == player_id))
    _require(canonical is not None, "rank player owner missing")
    validate_rank_fact(fact, canonical_name=canonical)
    names, proofs = _approved_context(conn, [player_id])
    proof = fact["evidence"]["professional_identity"]
    if proof is not None:
        _require(proof in proofs.get(player_id, []), "professional capture differs from approved owner evidence")
    grade, ref = fact["evidence"]["grade"], fact["source_ref"]
    allowed_names = {canonical} | names.get(player_id, set())
    _require(
        _name(parse_player(grade["raw_name"], grade["raw_rank"]).name) in {_name(name) for name in allowed_names},
        "source name differs from bound owner",
    )
    anchored = False
    _require(isinstance(source_games, (list, tuple)) and len(source_games) <= 100, "source games bound exceeded")
    for game in source_games:
        if (game.get("source_key"), game.get("source_item_id")) != (ref["source_key"], ref["source_item_id"]):
            continue
        _require(game.get("sgf_content") == grade["sgf_content"], "manifest source SGF differs from rank fact")
        if "sgf_sha256" in game:
            _require(game["sgf_sha256"] == ref["sgf_sha256"], "manifest source SGF hash differs")
        if game.get("metadata", {}).get("date_sort") is not None and fact["source_as_of"] is not None:
            _require(game["metadata"]["date_sort"] == fact["source_as_of"], "manifest source date conflict")
        if grade["date_basis"]["kind"] == "album_date_sort":
            from katrain.kifu_ingest.preparation import derive_metadata

            derived = derive_metadata(game["sgf_content"], game.get("source_metadata"), game["source_key"])
            _require(
                derived.get("date_sort") == fact["source_as_of"]
                and game.get("metadata", {}).get("date_sort") == fact["source_as_of"],
                "manifest source date differs from rank basis",
            )
        anchored = True
    if not anchored:
        a = KifuAlbum.__table__
        rows = conn.execute(select(a).where(a.c.source_path == _source_path(ref))).mappings().all()
        for album in rows:
            side = ref["slot"]
            if album[f"{side}_player_id"] != player_id:
                continue
            raw_rank = album[f"{side}_rank"]
            if not raw_rank or not raw_rank.strip():
                continue  # Never consume fallback snapshot/display overlays.
            if album["sgf_content"] == grade["sgf_content"] and raw_rank.strip() == grade["raw_rank"]:
                if fact["source_as_of"] is not None and album["date_sort"] != fact["source_as_of"]:
                    continue
                anchored = True
    _require(anchored, "rank source is not bound to local album or exact manifest game")
    return fact


def _row_fact(row, canonical_name):
    fact = {
        "version": FACT_VERSION,
        "player_ref": {"canonical_name": canonical_name},
        **{
            key: row[key]
            for key in ("rank_value", "rank_system", "source_kind", "source_ref", "evidence", "content_sha256")
        },
        "source_as_of": row["source_as_of"].isoformat() if row["source_as_of"] else None,
        "valid_from": row["valid_from"].isoformat() if row["valid_from"] else None,
        "observed_at": _utc(
            row["observed_at"].replace(tzinfo=timezone.utc) if row["observed_at"].tzinfo is None else row["observed_at"]
        ),
    }
    return validate_rank_fact(fact)


def apply_rank_fact(conn, player_id, fact, *, source_games=()):
    """Append/deduplicate within the native publisher's existing write transaction.

    The existing player row is locked even when no current observation exists.
    Conflict is sticky pending explicit review; older uploads cannot roll back a
    dated projection. The caller owns commit, journal and undo dependencies.
    """
    _require(conn.in_transaction(), "rank apply requires caller transaction")
    owner = conn.scalar(select(KifuPlayer.id).where(KifuPlayer.id == player_id).with_for_update())
    _require(owner is not None, "rank player owner missing")
    verify_rank_fact_for_player(conn, player_id, fact, source_games=source_games)
    h = KifuPlayerRankHistory.__table__
    duplicate = (
        conn.execute(select(h).where(h.c.player_id == player_id, h.c.content_sha256 == fact["content_sha256"]))
        .mappings()
        .first()
    )
    if duplicate:
        _require(
            _row_fact(duplicate, fact["player_ref"]["canonical_name"])["content_sha256"] == fact["content_sha256"],
            "stored rank fact differs",
        )
        return {
            "rank_fact_id": duplicate["id"],
            "status": duplicate["status"],
            "is_current": duplicate["is_current"],
            "inserted": False,
        }
    current = conn.execute(select(h).where(h.c.player_id == player_id, h.c.is_current)).mappings().first()
    basis = _day(fact["source_as_of"])
    active = (
        current is None
        or (basis is not None and (current["source_as_of"] is None or basis >= current["source_as_of"]))
        or (basis is None and current["source_as_of"] is None)
    )
    status = "qualified"
    if active and current is not None:
        different = (current["rank_value"], current["rank_system"]) != (fact["rank_value"], fact["rank_system"])
        if (
            current["status"] == "conflict"
            or current["rank_system"] != fact["rank_system"]
            or (basis == current["source_as_of"] and different)
            or (fact["rank_system"] == "professional_dan" and fact["rank_value"] < current["rank_value"])
        ):
            status = "conflict"
    if active and current is not None:
        conn.execute(h.update().where(h.c.id == current["id"]).values(is_current=False))
    inserted = conn.execute(
        h.insert().values(
            player_id=player_id,
            rank_value=fact["rank_value"],
            rank_system=fact["rank_system"],
            source_as_of=basis,
            valid_from=_day(fact["valid_from"]),
            observed_at=datetime.fromisoformat(fact["observed_at"]),
            source_kind=fact["source_kind"],
            source_ref=deepcopy(fact["source_ref"]),
            evidence=deepcopy(fact["evidence"]),
            content_sha256=fact["content_sha256"],
            status=status,
            is_current=active,
        )
    )
    return {"rank_fact_id": inserted.inserted_primary_key[0], "status": status, "is_current": active, "inserted": True}


def lookup_library_rank_facts(engine, resolved_players, *, observed_at=None):
    """Read <=200 already-resolved owners, their current rows or <=3 raw candidates.

    No identity search is performed. Same highest-day differing raw ranks fail
    closed even when the differing row falls outside the three returned SGFs.
    Raw candidates are reached through the existing black/white owner indexes;
    their SGF bodies are fetched only after the bounded candidate selection.
    """
    _require(
        isinstance(resolved_players, (list, tuple)) and len(resolved_players) <= MAX_PLAYERS,
        "resolved player limit exceeded",
    )
    requested, result = {}, {}
    for player in resolved_players:
        if not isinstance(player, dict) or type(player.get("id")) is not int:
            continue
        player_id = player["id"]
        if player.get("status") not in {"qualified", "missing_qualified_five_languages"} or not isinstance(
            player.get("canonical_name"), str
        ):
            result[player_id] = {"status": "unknown_identity", "reason": "identity_not_unique"}
            continue
        _require(
            player_id not in requested or requested[player_id] == player["canonical_name"],
            "conflicting resolved player owner",
        )
        requested[player_id] = player["canonical_name"]
    if not requested:
        return result
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        actual = dict(
            conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.id.in_(requested))).all()
        )
        ids = []
        for player_id, canonical in requested.items():
            if actual.get(player_id) != canonical:
                result[player_id] = {"status": "unknown_identity", "reason": "local_owner_mismatch"}
            else:
                ids.append(player_id)
        if not ids:
            return result
        h = KifuPlayerRankHistory.__table__
        for row in conn.execute(select(h).where(h.c.player_id.in_(ids), h.c.is_current)).mappings():
            player_id = row["player_id"]
            if row["status"] == "conflict":
                result[player_id] = {"status": "conflict", "reason": "current_conflict"}
            elif row["rank_system"] == "dan_unspecified":
                result[player_id] = {"status": "unknown_system", "reason": "current_system_unspecified"}
            else:
                try:
                    result[player_id] = {"status": "qualified", "fact": _row_fact(row, requested[player_id])}
                except ValueError:
                    result[player_id] = {"status": "conflict", "reason": "stored_fact_invalid"}
        missing = [player_id for player_id in ids if player_id not in result]
        if not missing:
            return result
        names, proofs = _approved_context(conn, missing)
        a = KifuAlbum.__table__
        parts = []
        for side in ("black", "white"):
            parts.append(
                select(
                    a.c.id,
                    a.c[f"{side}_player_id"].label("player_id"),
                    literal(side).label("side"),
                    a.c[f"{side}_rank"].label("raw_rank"),
                    a.c[f"player_{side}"].label("raw_name"),
                    a.c.date_sort,
                    a.c.date_played,
                    a.c.source_path,
                ).where(
                    a.c[f"{side}_player_id"].in_(missing),
                    a.c.duplicate_of_id.is_(None),
                    a.c[f"{side}_rank"].is_not(None),
                    func.trim(a.c[f"{side}_rank"]) != "",
                )
            )
        slots = union_all(*parts).subquery()
        ordered = select(
            slots,
            func.row_number()
            .over(
                partition_by=slots.c.player_id,
                order_by=(slots.c.date_sort.desc().nulls_last(), slots.c.id.desc(), slots.c.side),
            )
            .label("n"),
        ).subquery()
        candidates = conn.execute(select(ordered).where(ordered.c.n <= 3)).mappings().all()
        # This aggregate also sees the fourth/later same-day raw grade. It reads
        # scalar indexed-owner rows only, never a whole-library SGF scan.
        latest = (
            select(slots.c.player_id, func.max(slots.c.date_sort).label("day")).group_by(slots.c.player_id).subquery()
        )
        conflicts = set(
            conn.scalars(
                select(slots.c.player_id)
                .join(latest, and_(slots.c.player_id == latest.c.player_id, slots.c.date_sort == latest.c.day))
                .group_by(slots.c.player_id)
                .having(func.count(func.distinct(func.trim(slots.c.raw_rank))) > 1)
            )
        )
        candidate_ids = {row["id"] for row in candidates}
        # Read small length metadata first, then fetch at most 8 MiB of exact
        # candidate bodies. An oversized fact leaves only that owner unknown.
        length = (
            func.octet_length(a.c.sgf_content)
            if conn.dialect.name == "postgresql"
            else func.length(cast(a.c.sgf_content, LargeBinary))
        )
        selected_ids, remaining = [], MAX_TOTAL_SGF_BYTES
        if candidate_ids:
            for album_id, size in conn.execute(
                select(a.c.id, length).where(a.c.id.in_(candidate_ids)).order_by(a.c.id)
            ):
                if 0 < size <= min(MAX_SGF_BYTES, remaining):
                    selected_ids.append(album_id)
                    remaining -= size
        bodies = (
            dict(conn.execute(select(a.c.id, a.c.sgf_content).where(a.c.id.in_(selected_ids))).all())
            if selected_ids
            else {}
        )
        by_player = {}
        for row in candidates:
            by_player.setdefault(row["player_id"], []).append(row)
        for player_id in missing:
            if player_id in conflicts:
                result[player_id] = {"status": "conflict", "reason": "same_day_raw_rank_conflict"}
                continue
            rows = by_player.get(player_id, [])
            result[player_id] = {"status": "unknown_system", "reason": "no_verifiable_raw_rank"}
            facts = []
            allowed_names = {_name(requested[player_id])} | {_name(name) for name in names.get(player_id, set())}
            proof = min(proofs[player_id], key=lambda value: value["capture_sha256"]) if proofs.get(player_id) else None
            for row in rows:
                path = re.fullmatch(
                    r"data/kifu-album/([a-z0-9_-]{1,64})/([a-zA-Z0-9_-]{1,64})\.sgf", row["source_path"]
                )
                if not path or row["id"] not in bodies:
                    continue
                try:
                    fact = build_source_rank_fact(
                        canonical_name=requested[player_id],
                        raw_rank=row["raw_rank"].strip(),
                        sgf_content=bodies[row["id"]],
                        slot=row["side"],
                        source_ref={"source_key": path.group(1), "source_item_id": path.group(2)},
                        identity_evidence=proof,
                        source_as_of=row["date_sort"],
                        observed_at=observed_at,
                    )
                    if fact is None or fact["source_as_of"] != row["date_sort"]:
                        continue
                    # These album rows and source bodies were fetched together
                    # under their exact indexed side FK. Reuse the batch owner
                    # context instead of a per-person query/verification loop.
                    grade = fact["evidence"]["grade"]
                    if _name(parse_player(grade["raw_name"], grade["raw_rank"]).name) not in allowed_names or _name(
                        parse_player(grade["raw_name"], grade["raw_rank"]).name
                    ) != _name(parse_player(row["raw_name"], row["raw_rank"]).name):
                        continue
                except (ValueError, TypeError):
                    continue
                facts.append(fact)
            latest_facts = [fact for fact in facts if fact["source_as_of"] == rows[0]["date_sort"]] if rows else []
            if not latest_facts:
                continue
            fact = latest_facts[0]
            if fact["rank_system"] == "dan_unspecified":
                result[player_id] = {"status": "unknown_system", "reason": "professional_identity_unverified"}
            elif any(
                other["rank_system"] != fact["rank_system"]
                or (fact["rank_system"] == "professional_dan" and other["rank_value"] > fact["rank_value"])
                for other in facts
            ):
                result[player_id] = {"status": "conflict", "reason": "recent_raw_rank_conflict"}
            else:
                result[player_id] = {"status": "qualified", "fact": fact}

    return result


def lookup_album_rank_snapshots(conn, album_ids):
    """Read frozen overlays for one bounded API page in a single query."""
    _require(isinstance(album_ids, (list, tuple, set)) and len(album_ids) <= 200, "album snapshot limit exceeded")
    if not album_ids:
        return {}
    t = KifuAlbumRankSnapshot.__table__
    return {
        (row["album_id"], row["side"]): dict(row)
        for row in conn.execute(select(t).where(t.c.album_id.in_(album_ids))).mappings()
    }
