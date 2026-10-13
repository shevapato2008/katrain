"""Package the narrow raw-display bridge onto a captured legacy runtime; no deploy."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"runtime patch anchor changed: {old[:80]}")
    return source.replace(old, new, 1)


def rules_source():
    """Copy existing pure rules verbatim, without importing the current ORM graph."""
    source = (ROOT / "katrain/web/kifu/name_candidates.py").read_text()
    tree = ast.parse(source)
    names = {
        "LANGUAGES",
        "_HASH",
        "CLASSIFICATION_RULE_VERSION",
        "CandidateError",
        "_require",
        "_text",
        "_time",
        "canonical_sha256",
        "classification_template_sha256",
        "archive_description_template_sha256",
        "_archive_source_path_matches",
        "_archive_excerpt_matches",
        "validate_archive_description_scope",
        "validate_archive_description_candidate",
        "_check_signature",
    }
    lines = source.splitlines(keepends=True)
    chunks = []
    for node in tree.body:
        keys = (
            {node.name}
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            else {t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)}
        )
        start_templates = source.index("_CLASSIFICATION_TEMPLATES =")
        end_templates = source.index("_SCRIPT =")
        offset = sum(len(line) for line in lines[: node.lineno - 1])
        if keys & names or start_templates <= offset < end_templates:
            chunks.append("".join(lines[node.lineno - 1 : node.end_lineno]))
    return (
        '"""Generated unchanged pure rules from name_candidates.py; do not edit."""\n'
        "from datetime import datetime\nfrom pathlib import Path\nfrom urllib.parse import urlparse\n"
        "import hashlib, json, re\n\n" + "\n\n".join(chunks) + "\n"
    )


def build(runtime, output):
    output.mkdir(parents=True, exist_ok=True)
    identity_path = Path("katrain/web/kifu/identity.py")
    endpoint_path = Path("katrain/web/api/v1/endpoints/kifu.py")
    identity = (runtime / identity_path).read_text()
    endpoint = (runtime / endpoint_path).read_text()
    identity = replace_once(
        identity,
        "    return players, events, {album_id: sorted(keys) for album_id, keys in sources.items()}, hints",
        "    from katrain.web.kifu.legacy_raw_events import reviewed_raw_event_hints\n\n"
        "    hints.update(reviewed_raw_event_hints(db, albums, lang))\n"
        "    return players, events, {album_id: sorted(keys) for album_id, keys in sources.items()}, hints",
    )
    endpoint = replace_once(
        endpoint,
        "        query = query.filter(needle)\n        count_query = count_query.filter(needle)",
        "        if not player_ids and not event_ids:\n"
        "            from katrain.web.kifu.legacy_raw_events import reviewed_raw_event_search_clause\n\n"
        "            raw_clause = reviewed_raw_event_search_clause(db, q)\n"
        "            if raw_clause is not None:\n"
        "                needle = raw_clause\n"
        "        query = query.filter(needle)\n        count_query = count_query.filter(needle)",
    )
    helper = (
        (ROOT / "katrain/web/kifu/legacy_raw_events.py")
        .read_text()
        .replace(
            "from katrain.web.kifu.name_candidates import (", "from katrain.web.kifu.legacy_raw_event_rules import ("
        )
    )
    payloads = {
        identity_path: identity,
        endpoint_path: endpoint,
        Path("katrain/web/kifu/legacy_raw_events.py"): helper,
        Path("katrain/web/kifu/legacy_raw_event_rules.py"): rules_source(),
        Path("katrain/web/kifu/raw_event_translation.py"):
            (ROOT / "katrain/web/kifu/raw_event_translation.py").read_text(),
    }
    hashes = {}
    for path, body in payloads.items():
        compile(body, str(path), "exec")
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body)
        hashes[str(path)] = {"after_sha256": hashlib.sha256(body.encode()).hexdigest()}
        if (runtime / path).exists():
            hashes[str(path)]["before_sha256"] = hashlib.sha256((runtime / path).read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return hashes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.runtime, args.output), indent=2))
