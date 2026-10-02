"""Finite, offline Honinbo edition composition. Rules are reviewed data, not templates."""

from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urlparse

HONINBO_RAWS = tuple(
    f"{n}{'th' if n % 100 in (11, 12, 13) else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')} Honinbo"
    for n in range(1, 35)
)
HONINBO_EDITION = {raw: n for n, raw in enumerate(HONINBO_RAWS, 1)}
LANGUAGE_TAGS = {
    "en": "en",
    "cn": "zh-Hans",
    "tw": "zh-Hant",
    "jp": "ja",
    "ko": "ko",
    "de": "de",
    "es": "es",
    "fr": "fr",
    "ru": "ru",
    "tr": "tr",
    "ua": "uk",
}
RENDERER_VERSION = "honinbo-edition-v1"
COMPOSITION_VERSION = "honinbo-composition-v1"
_HASH = re.compile(r"^[0-9a-f]{64}$")


class CompositionError(ValueError):
    """A composition rule, scope, or candidate lacks its exact review binding."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CompositionError(message)


def _hash(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def base_candidate_sha256(base: dict) -> str:
    """Hash the source-approved decision before later database preimage binding."""
    return _hash({key: value for key, value in base.items() if key not in {"name_preimage_sha256", "preimage_binding"}})


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def render_edition(rule: dict, base: str, edition: int) -> str:
    """Render one of eleven fixed operations; rule data cannot inject expressions."""
    _require(
        isinstance(rule, dict) and rule.get("renderer_version") == RENDERER_VERSION, "unknown composition renderer"
    )
    lang = rule.get("lang")
    _require(
        isinstance(lang, str) and lang in LANGUAGE_TAGS and rule.get("style") == lang,
        "unsupported locale composition style",
    )
    _require(
        type(edition) is int and 1 <= edition <= 34 and isinstance(base, str) and bool(base.strip()),
        "invalid Honinbo edition or base",
    )
    if lang == "en":
        suffix = "th" if edition % 100 in (11, 12, 13) else {1: "st", 2: "nd", 3: "rd"}.get(edition % 10, "th")
        return f"{edition}{suffix} {base}"
    if lang in {"cn", "tw", "jp"}:
        return f"第{edition}期{base}"
    if lang == "ko":
        return f"제{edition}기 {base}"
    if lang in {"de", "tr"}:
        return f"{edition}. {base}"
    if lang == "es":
        return f"{edition}.ª edición del {base}"
    if lang == "fr":
        return f"{edition}{'re' if edition == 1 else 'e'} édition du {base}"
    if lang in {"ru", "ua"}:
        _require(
            base.startswith("Турнир ") if lang == "ru" else base.startswith("Турнір "),
            "Slavic base must contain reviewed leading noun",
        )
        return f"{edition}-й {base[0].lower()}{base[1:]}"
    raise CompositionError("unsupported locale composition style")


def _reviewed_record(record: object, *, captures: list[str] = ()) -> dict:
    _require(
        isinstance(record, dict) and set(record) == {"content", "approval"}, "reviewed composition record shape invalid"
    )
    content, approval = record["content"], record["approval"]
    _require(isinstance(content, dict) and isinstance(approval, dict), "composition content and approval required")
    _require(
        approval.get("status") == "approved" and approval.get("content_sha256") == _hash(content),
        "composition content lacks exact approval",
    )
    producer, reviewer = approval.get("producer_id"), approval.get("reviewer_id")
    produced, reviewed = _time(approval.get("produced_at")), _time(approval.get("reviewed_at"))
    _require(
        isinstance(producer, str)
        and bool(producer.strip())
        and isinstance(reviewer, str)
        and bool(reviewer.strip())
        and reviewer != producer
        and isinstance(approval.get("producer_model"), str)
        and bool(approval["producer_model"].strip())
        and isinstance(approval.get("reviewer_model"), str)
        and bool(approval["reviewer_model"].strip())
        and isinstance(approval.get("conclusion"), str)
        and bool(approval["conclusion"].strip())
        and produced is not None
        and reviewed is not None
        and reviewed >= produced,
        "composition needs chronological independent approval",
    )
    _require(
        all(_time(capture) is not None and _time(capture) <= produced for capture in captures),
        "composition approval predates source capture",
    )
    return content


def _source_captures(sources: object, body_lang: str) -> list[str]:
    _require(isinstance(sources, list) and bool(sources), "composition needs source evidence")
    captures = []
    for source in sources:
        url = source.get("url") if isinstance(source, dict) else None
        try:
            parsed = urlparse(url) if isinstance(url, str) else None
        except ValueError:
            parsed = None
        _require(
            isinstance(source, dict)
            and {"url", "body_lang", "captured_at", "body_sha256", "excerpt", "basis"} <= set(source)
            and set(source) <= {"url", "body_lang", "captured_at", "body_sha256", "excerpt", "basis", "revision"}
            and parsed is not None
            and parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and source.get("body_lang") == body_lang
            and bool(_HASH.fullmatch(str(source.get("body_sha256", ""))))
            and isinstance(source.get("excerpt"), str)
            and bool(source["excerpt"].strip())
            and isinstance(source.get("basis"), str)
            and bool(source["basis"].strip()),
            "composition source provenance or body language invalid",
        )
        captures.append(source["captured_at"])
    return captures


def validate_composition(
    composition: object, bundle: dict, inventory: dict, raw_games: dict, raw_slots: dict
) -> tuple[dict, dict, dict]:
    """Validate the whole finite scope and rule set before any composed decision."""
    _require(bundle.get("bundle_format") in {2, 3, 4}, "composition requires bundle format 2 or newer")
    _require(
        isinstance(composition, dict)
        and composition.get("version") == COMPOSITION_VERSION
        and set(composition) == {"version", "scope", "rules"},
        "composition section/version invalid",
    )
    scope_record = composition["scope"]
    _require(
        isinstance(scope_record, dict) and isinstance(scope_record.get("content"), dict), "composition scope missing"
    )
    scope_content = scope_record["content"]
    _require(
        set(scope_content) == {"series_owner", "inventory_sha256", "catalog_sha256", "raws", "sources"},
        "composition scope fields incomplete",
    )
    scope = _reviewed_record(scope_record, captures=_source_captures(scope_content["sources"], "en"))
    series = scope.get("series_owner")
    _require(
        isinstance(series, dict)
        and series.get("kind") == "event"
        and (
            set(series) == {"kind", "id"}
            and type(series["id"]) is int
            and series["id"] > 0
            or set(series) == {"kind", "ref"}
            and isinstance(series["ref"], str)
            and bool(series["ref"])
        ),
        "composition requires one event series owner",
    )
    _require(scope.get("inventory_sha256") == inventory.get("sha256"), "composition inventory mismatch")
    _require(scope.get("catalog_sha256") == bundle.get("catalog_sha256"), "composition catalog mismatch")
    raws = scope.get("raws")
    _require(isinstance(raws, list) and len(raws) == 34, "composition requires all 34 exact raw values")
    columns = inventory["association_columns"]
    associations = {row[columns.index("id")]: dict(zip(columns, row)) for row in inventory["album_associations"]}
    linked = {
        (link.get("album_id"), link.get("slot"), json.dumps(link.get("target"), sort_keys=True))
        for link in bundle.get("album_links", [])
    }
    by_raw = {}
    owners = set()
    for entry in raws:
        _require(
            isinstance(entry, dict)
            and set(entry)
            == {"owner", "raw_value", "edition", "occurrence_album_ids", "occurrence_sha256", "raw_scope_sha256"},
            "composition raw scope shape invalid",
        )
        raw, edition, owner = entry["raw_value"], entry["edition"], entry["owner"]
        _require(
            isinstance(raw, str)
            and raw in HONINBO_EDITION
            and type(edition) is int
            and edition == HONINBO_EDITION[raw]
            and raw not in by_raw
            and isinstance(owner, dict)
            and owner.get("kind") == "raw_event"
            and json.dumps(owner, sort_keys=True) not in owners,
            "unlisted, duplicate, or mismatched Honinbo raw edition",
        )
        ids = raw_games.get(raw, [])
        slots = raw_slots.get(raw, [])
        _require(
            ids
            and entry["occurrence_album_ids"] == ids
            and entry["occurrence_sha256"] == _hash(ids)
            and entry["raw_scope_sha256"] == _hash(slots),
            "composition occurrence or raw scope differs from inventory",
        )
        for album_id, slot in slots:
            if (
                slot == "event"
                and type(series.get("id")) is int
                and associations[album_id].get("event_id") == series["id"]
            ):
                continue
            _require(
                (album_id, slot, json.dumps(series, sort_keys=True)) in linked,
                "composition raw occurrence lacks matching reviewed series link",
            )
        by_raw[raw] = entry
        owners.add(json.dumps(owner, sort_keys=True))
    _require(set(by_raw) == set(HONINBO_RAWS), "composition raw set differs from frozen cohort")
    rules = composition.get("rules")
    _require(isinstance(rules, list) and len(rules) == len(LANGUAGE_TAGS), "composition requires eleven locale rules")
    by_lang = {}
    for record in rules:
        _require(isinstance(record, dict) and isinstance(record.get("content"), dict), "locale rule missing")
        content = record["content"]
        _require(
            set(content) == {"series_owner", "lang", "base_candidate_sha256", "renderer_version", "style", "sources"},
            "locale rule fields invalid",
        )
        lang = content.get("lang")
        _require(
            isinstance(lang, str)
            and lang in LANGUAGE_TAGS
            and lang not in by_lang
            and content.get("series_owner") == series
            and content.get("renderer_version") == RENDERER_VERSION
            and content.get("style") == lang
            and bool(_HASH.fullmatch(str(content.get("base_candidate_sha256", "")))),
            "locale rule series, language, renderer or base binding invalid",
        )
        _reviewed_record(record, captures=_source_captures(content["sources"], LANGUAGE_TAGS[lang]))
        by_lang[lang] = record
    _require(set(by_lang) == set(LANGUAGE_TAGS), "composition locale rule set incomplete")
    return by_raw, by_lang, scope_record


def validate_composed_candidate(row: dict, raw: dict, rule: dict, base: dict, scope: dict) -> None:
    """Bind a reviewed stored name to its exact approved dependencies and bytes."""
    content = rule["content"]
    _require(
        row.get("owner") == raw["owner"]
        and row.get("raw_value") == raw["raw_value"]
        and row.get("lang") == content["lang"]
        and row.get("series_owner") == content["series_owner"]
        and row.get("base_candidate_sha256") == base_candidate_sha256(base)
        and content["base_candidate_sha256"] == base_candidate_sha256(base)
        and row.get("composition_rule_sha256") == _hash(rule)
        and type(row.get("edition")) is int
        and row["edition"] == raw["edition"]
        and row.get("raw_scope_sha256") == raw["raw_scope_sha256"]
        and row.get("generation_rule_version") == RENDERER_VERSION
        and row.get("research_sha256") == "",
        "composed candidate dependency mismatch",
    )
    _require(
        base.get("owner") == content["series_owner"]
        and base.get("lang") == row["lang"]
        and base.get("review_status") == "approved"
        and base.get("decision_kind") in {"conventional", "generated"},
        "composed candidate lacks approved same-language series base",
    )
    _require(
        _time(base.get("reviewed_at")) <= _time(rule["approval"]["reviewed_at"]) <= _time(row.get("produced_at"))
        and _time(scope["approval"]["reviewed_at"]) <= _time(row["produced_at"]),
        "composed candidate predates approved base, rule or scope",
    )
    _require(
        row.get("display_name") == render_edition(content, base["display_name"], row["edition"]),
        "composed display differs from byte-for-byte rendering",
    )
    signed = {
        key: value
        for key, value in row.items()
        if key
        not in {
            "reviewer_id",
            "reviewer_model",
            "reviewed_at",
            "review_conclusion",
            "composition_review_sha256",
            "name_preimage_sha256",
            "preimage_binding",
        }
    }
    if row.get("review_status") == "approved":
        _require(
            row.get("composition_review_sha256") == _hash(signed)
            and _time(row.get("reviewed_at")) is not None
            and _time(row["reviewed_at"]) >= _time(rule["approval"]["reviewed_at"]),
            "composed candidate signature stale or predates rule approval",
        )
