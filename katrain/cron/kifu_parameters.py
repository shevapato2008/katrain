"""Fail-closed professional analysis parameters, shared by web/cron/transfer.

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
# contract. Never infer a preset from players, country, event name or komi.
SUPPORTED_RULES = frozenset({"chinese", "japanese", "korean", "aga", "aga-button", "new zealand", "tromp-taylor"})


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
        if not math.isfinite(number):
            raise ValueError()
        return 0.0 if number == 0 else number
    except (ValueError, TypeError, OverflowError):
        raise ParameterError("invalid_komi", "An explicit finite komi is required") from None


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


def resolve_parameters(sgf: str, evidence: dict | None = None) -> dict:
    """Resolve explicit root RU/KM or exact reviewed evidence, without rewriting SGF.

    Ambiguous/unsupported SGF assertions and conflicting evidence are rejected.
    Evidence fills absent fields; it cannot silently overrule contradictory data.
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
    if evidence is not None:
        evidence_rules, evidence_komi = _validate_evidence(evidence, sgf_sha256)
        if (rules is not None and rules != evidence_rules) or (komi is not None and komi != evidence_komi):
            raise ParameterError("evidence_conflict", "Reviewed evidence and explicit SGF parameters conflict")
        rules, komi = evidence_rules, evidence_komi
        provenance = {**provenance, "source": "verified_evidence", "evidence": deepcopy(evidence)}
    if rules is None:
        raise ParameterError("missing_rules", "SGF RU is missing; exact-game/event evidence is required")
    if komi is None:
        raise ParameterError("missing_komi", "SGF KM is missing; exact-game/event evidence is required")
    body = {
        "version": 1,
        "verified": True,
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
    """Revalidate persisted provenance and identity; never bless legacy results."""
    if not isinstance(stored, dict) or stored.get("verified") is not True:
        raise ParameterError("unverified_parameters", "Stored engine parameters are unverified; reanalysis is required")
    provenance = stored.get("provenance")
    if not isinstance(provenance, dict):
        raise ParameterError("unverified_parameters", "Stored parameter provenance is missing")
    evidence = provenance.get("evidence") if provenance.get("source") == "verified_evidence" else None
    resolved = resolve_parameters(sgf, evidence)
    if resolved != stored:
        raise ParameterError("parameter_mismatch", "Stored parameters do not match their SGF/evidence identity")
    return resolved
