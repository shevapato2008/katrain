"""Conservative, review-only reuse of existing five-language raw event text.

This module proposes display text for a raw title. It does not identify an event,
bind a title to a target scope, or approve a translation.
"""

from collections import Counter, defaultdict
import re


LANGS = ("cn", "tw", "en", "jp", "ko")
_DIGITS = re.compile(r"[0-9]+")
_EN_NUMBER = re.compile(r"([0-9]+)(st|nd|rd|th)?", re.IGNORECASE)


def _skeleton(raw):
    return _DIGITS.sub("\0", raw)


def build_event_lexicon(rows):
    """Index verified old text by exact raw value and ASCII-number skeleton."""
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("status") == "verified" and row.get("lang") in LANGS:
            grouped[row["raw_value"]][row["lang"]].append(row)

    exact = {}
    templates = defaultdict(list)
    for raw, by_lang in grouped.items():
        if not raw or set(by_lang) != set(LANGS):
            continue
        if any(
            len({r["display_name"] for r in by_lang[lang]}) != 1
            or not all(r["display_name"].strip() for r in by_lang[lang])
            for lang in LANGS
        ):
            continue
        selected = {lang: min(by_lang[lang], key=lambda r: r["evidence_id"]) for lang in LANGS}
        source = {
            "old_raw": raw,
            "old_raw_ids": sorted({r["raw_id"] for records in by_lang.values() for r in records}),
            "old_names": {lang: selected[lang]["display_name"] for lang in LANGS},
            "evidence_ids": {lang: selected[lang]["evidence_id"] for lang in LANGS},
        }
        exact[raw] = source
        if _DIGITS.search(raw):
            templates[_skeleton(raw)].append(source)
    return {"exact": exact, "templates": templates}


def _ordinal_suffix(value):
    number = int(value)
    if number % 100 in (11, 12, 13):
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _replace_display(display, mapping, old_numbers, lang):
    # Extra numbers may refer to unrelated facts. Without a positional proof,
    # replacing one of those would invent text, so require exact multiset parity.
    if Counter(_DIGITS.findall(display)) != Counter(old_numbers):
        return None
    if lang == "en":
        invalid = False

        def replace(match):
            nonlocal invalid
            old, suffix = match.groups()
            new = mapping[old]
            if suffix:
                if suffix.lower() != _ordinal_suffix(old):
                    invalid = True
                    return match.group()
                new_suffix = _ordinal_suffix(new)
                if suffix.isupper():
                    new_suffix = new_suffix.upper()
                elif suffix[0].isupper():
                    new_suffix = new_suffix.capitalize()
                return new + new_suffix
            return new

        result = _EN_NUMBER.sub(replace, display)
        return None if invalid else result
    return _DIGITS.sub(lambda m: mapping[m.group()], display)


def _template_proposal(raw, source):
    old_raw = source["old_raw"]
    old_numbers = _DIGITS.findall(old_raw)
    new_numbers = _DIGITS.findall(raw)
    if len(old_numbers) != len(new_numbers) or _skeleton(old_raw) != _skeleton(raw):
        return None
    mapping = {}
    for old, new in zip(old_numbers, new_numbers):
        if old in mapping and mapping[old] != new:
            return None
        mapping[old] = new
    names = {}
    for lang in LANGS:
        changed = _replace_display(source["old_names"][lang], mapping, old_numbers, lang)
        if changed is None:
            return None
        names[lang] = changed
    return names, mapping


def propose_event_reuse(raw, lexicon):
    """Return a generated five-language candidate, or None when proof is insufficient."""
    if not raw:
        return None
    source = lexicon["exact"].get(raw)
    if source:
        return {
            "raw_value": raw,
            "method": "reuse",
            "rule": "exact_raw_v1",
            "names5": source["old_names"],
            "sources": [source],
            "digit_mapping": {},
            "review_status": "generated_candidate",
        }
    if not _DIGITS.search(raw):
        return None
    proposals = []
    for source in lexicon["templates"].get(_skeleton(raw), []):
        result = _template_proposal(raw, source)
        if result:
            names, mapping = result
            proposals.append((names, mapping, source))
    if not proposals:
        return None
    first_names = proposals[0][0]
    if any(names != first_names for names, _, _ in proposals[1:]):
        return None
    return {
        "raw_value": raw,
        "method": "translation",
        "rule": "ascii_digit_template_v1",
        "names5": first_names,
        "sources": [source for _, _, source in proposals],
        "digit_mapping": proposals[0][1],
        "review_status": "generated_candidate",
    }
