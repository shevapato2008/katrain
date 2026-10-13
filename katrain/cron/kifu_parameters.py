"""Traceable professional analysis parameters, shared by web/cron/transfer.

Only stdlib and cron imports: Dockerfile.cron ships no other katrain packages.
Personal/live parse_game defaults deliberately do not establish verification.
Evidence is an operator-reviewed assertion, not an automatic source lookup. Even
an event policy must be bound by the reviewer to the exact original SGF digest.
"""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from urllib.parse import urlparse

from katrain.cron.sgf import _main_line_nodes


# Conservative exact presets already supported by the application's KataGo wire
# contract. Do not infer a preset from players, country or event names.
SUPPORTED_RULES = frozenset({"chinese", "japanese", "korean", "aga", "aga-button", "new zealand", "tromp-taylor"})
DEFAULT_RULES_BY_KOMI = {6.5: "japanese", 7.5: "chinese"}
DEFAULT_RULES_POLICY = "komi-default-v1"


class ParameterError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self):
        return {"code": self.code, "message": self.message}


def _rules(value):
    if not isinstance(value, str) or value.strip().lower() not in SUPPORTED_RULES:
        raise ParameterError("unsupported_rules", "SGF/evidence rules are not an explicitly supported KataGo preset")
    return value.strip().lower()


def _komi(value):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError()
        number = float(value)
        if not math.isfinite(number) or not -400 <= number <= 400 or not (number * 2).is_integer():
            raise ValueError()
        return 0.0 if number == 0 else number
    except (ValueError, TypeError, OverflowError):
        raise ParameterError(
            "invalid_komi", "An explicit finite komi from -400 to 400 in increments of 0.5 is required"
        ) from None


def _validate_evidence(evidence, sgf_sha256):
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        raise ParameterError("unverified_evidence", "Evidence needs an explicit reviewed assertion")
    if evidence.get("sgf_sha256") != sgf_sha256:
        raise ParameterError("evidence_mismatch", "Evidence does not identify these exact SGF bytes")
    urls = evidence.get("reference_urls")
    if (
        evidence.get("scope") not in ("exact_game", "event")
        or not all(
            isinstance(evidence.get(k), str) and evidence[k].strip()
            for k in ("scope_description", "verified_by", "verified_at")
        )
        or not isinstance(urls, list)
        or not urls
    ):
        raise ParameterError("unverified_evidence", "Record evidence scope, references, reviewer and verification time")
    try:
        if any(
            not isinstance(u, str) or urlparse(u).scheme not in {"https", "http"} or not urlparse(u).netloc
            for u in urls
        ):
            raise ValueError()
        if datetime.fromisoformat(evidence["verified_at"]).tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ParameterError(
            "unverified_evidence", "Evidence needs valid HTTP(S) references and a time with timezone"
        ) from None
    return _rules(evidence.get("rules")), _komi(evidence.get("komi"))


def _validate_corrections(evidence, raw, explicit, effective):
    """Authorize each contradiction against exact raw SGF values and reviewed targets.

    corrections maps KM/RU to {original_value: raw string, verified_value:
    numeric komi/canonical rules, reason: nonempty string}. The existing evidence
    SGF hash, references, reviewer and timestamp apply to every correction.
    """
    corrections = evidence.get("corrections", {})
    if not isinstance(corrections, dict) or set(corrections) - {"KM", "RU"}:
        raise ParameterError("invalid_correction", "Corrections must be an object containing only KM and/or RU")
    conflicts = {key for key in raw if raw[key] is not None and explicit[key] != effective[key]}
    for key, record in corrections.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"original_value", "verified_value", "reason"}
            or not isinstance(record["reason"], str)
            or not record["reason"].strip()
            or not isinstance(record["original_value"], str)
            or record["original_value"] != raw[key]
            or key not in conflicts
            or (key == "KM" and type(record["verified_value"]) not in (int, float))
            or (key == "RU" and not isinstance(record["verified_value"], str))
            or record["verified_value"] != effective[key]
        ):
            raise ParameterError(
                "invalid_correction", f"{key} correction must match exact raw/effective values and state a reason"
            )
    if conflicts - set(corrections):
        raise ParameterError("evidence_conflict", "Each conflicting SGF field requires an explicit reviewed correction")
    return bool(corrections)


def resolve_parameters(sgf: str, evidence: dict | None = None) -> dict:
    """Resolve root RU/KM, reviewed evidence, or an explicitly labelled default.

    Evidence fills absent fields. Contradictory values require field-specific
    reviewed corrections; ambiguous/unsupported SGF assertions remain rejected.
    """
    nodes = _main_line_nodes(sgf)
    root = nodes[0] if nodes else {}
    if any(len(root.get(k, [])) > 1 for k in ("RU", "KM")) or any("RU" in node or "KM" in node for node in nodes[1:]):
        raise ParameterError("conflicting_metadata", "RU/KM must be single root properties")
    raw_rules = root.get("RU", [None])[0]
    raw_komi = root.get("KM", [None])[0]
    rules = _rules(raw_rules) if raw_rules is not None else None
    komi = _komi(raw_komi) if raw_komi is not None else None
    sgf_sha256 = hashlib.sha256(sgf.encode("utf-8")).hexdigest()
    provenance = {"source": "sgf", "raw_rules": raw_rules, "raw_komi": raw_komi}
    corrected = False
    if evidence is not None:
        evidence_rules, evidence_komi = _validate_evidence(evidence, sgf_sha256)
        corrected = _validate_corrections(
            evidence,
            {"RU": raw_rules, "KM": raw_komi},
            {"RU": rules, "KM": komi},
            {"RU": evidence_rules, "KM": evidence_komi},
        )
        rules, komi = evidence_rules, evidence_komi
        provenance = {**provenance, "source": "verified_evidence", "evidence": deepcopy(evidence)}
    elif rules is None and komi in DEFAULT_RULES_BY_KOMI:
        rules = DEFAULT_RULES_BY_KOMI[komi]
        provenance = {**provenance, "source": "komi_default", "policy": DEFAULT_RULES_POLICY}
    if rules is None:
        raise ParameterError("missing_rules", "SGF RU is missing and komi has no default; exact-game/event evidence is required")
    if komi is None:
        raise ParameterError("missing_komi", "SGF KM is missing; exact-game/event evidence is required")
    body = {
        "version": 3 if provenance["source"] == "komi_default" else 2 if corrected else 1,
        "verified": provenance["source"] != "komi_default",
        "sgf_sha256": sgf_sha256,
        "rules": rules,
        "komi": komi,
        "provenance": provenance,
    }
    try:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ParameterError("unverified_evidence", "Evidence must be finite, serializable JSON") from None
    return {**body, "parameter_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}


def validate_parameters(sgf: str, stored: dict | None) -> dict:
    """Revalidate persisted provenance and identity, including labelled defaults."""
    if not isinstance(stored, dict) or not (
        stored.get("verified") is True
        or (
            stored.get("verified") is False
            and stored.get("version") == 3
            and isinstance(stored.get("provenance"), dict)
            and stored["provenance"].get("source") == "komi_default"
        )
    ):
        raise ParameterError("unverified_parameters", "Stored engine parameters are unverified; reanalysis is required")
    provenance = stored.get("provenance")
    if not isinstance(provenance, dict):
        raise ParameterError("unverified_parameters", "Stored parameter provenance is missing")
    evidence = provenance.get("evidence") if provenance.get("source") == "verified_evidence" else None
    resolved = resolve_parameters(sgf, evidence)
    if resolved != stored:
        raise ParameterError("parameter_mismatch", "Stored parameters do not match their SGF/evidence identity")
    return resolved
