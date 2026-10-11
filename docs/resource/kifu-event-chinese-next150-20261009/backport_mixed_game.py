"""Backport only Chinese-mixed `game` validation into the exact native r5 module.

This is a source transform. It never edits the input file or deploys anything.
"""

import argparse
import hashlib
from pathlib import Path


NATIVE_SHA256 = "d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499"
REPLACEMENTS = (
    (
        '_MIXED_EDITION = re.compile(r"第?[一二三四五六七八九十百千万0-9０-９]+(?:届|屆|期)\\Z")\n',
        '_MIXED_EDITION = re.compile(r"第?[一二三四五六七八九十百千万0-9０-９]+(?:届|屆|期)\\Z")\n'
        '_POSITIVE_NUMBER = (\n'
        '    r"(?:[1-9][0-9]{0,2}|0[1-9][0-9]?|00[1-9]|[一二三四五六七八九]"\n'
        '    r"|十[一二三四五六七八九]?|[一二三四五六七八九]十[一二三四五六七八九]?)"\n'
        ')\n'
        '_MIXED_GAME = re.compile(rf"第?{_POSITIVE_NUMBER}局\\Z")\n',
    ),
    (
        'or not _text(part["text"]) or part["kind"] not in {"core", "year", "edition", "round"}\n',
        'or not _text(part["text"]) or (part["kind"] not in {"core", "year", "edition", "round"}\n'
        '                   and not (mixed and part["kind"] == "game"))\n',
    ),
    (
        'or part["kind"] == "round" and not _ORDINAL.fullmatch(part["text"])\n'
        '                   or part["kind"] == "year" and not _YEAR.fullmatch(part["text"]) for part in parts)',
        'or part["kind"] == "round" and not _ORDINAL.fullmatch(part["text"])\n'
        '                   or part["kind"] == "game" and not (mixed and _MIXED_GAME.fullmatch(part["text"]))\n'
        '                   or part["kind"] == "year" and not _YEAR.fullmatch(part["text"]) for part in parts)',
    ),
    (
        'if not english_sgf and any(part["kind"] not in {"core", "year", "edition", "round", "geographic_qualifier"}\n',
        'if not english_sgf and any(part["kind"] not in {"core", "year", "edition", "round", "geographic_qualifier"}\n'
        '           and not (mixed_sgf and part["kind"] == "game")\n',
    ),
    (
        'or part["kind"] == "round" and not _ORDINAL.fullmatch(part["text"])\n'
        '           or part["kind"] == "year" and not _YEAR.fullmatch(part["text"])\n',
        'or part["kind"] == "round" and not _ORDINAL.fullmatch(part["text"])\n'
        '           or part["kind"] == "game" and not (mixed_sgf and _MIXED_GAME.fullmatch(part["text"]))\n'
        '           or part["kind"] == "year" and not _YEAR.fullmatch(part["text"])\n',
    ),
)


def backport(native: bytes) -> bytes:
    actual = hashlib.sha256(native).hexdigest()
    if actual != NATIVE_SHA256:
        raise ValueError(f"unexpected native r5 module SHA-256: {actual}")
    content = native.decode("utf-8")
    for old, new in REPLACEMENTS:
        if content.count(old) != 1:
            raise ValueError(f"unexpected native layout at replacement {old[:65]!r}")
        content = content.replace(old, new, 1)
    return content.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path, help="exact fetched native r5 raw_event_translation.py")
    parser.add_argument("output", type=Path, help="new source file; must not exist")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = backport(args.native.read_bytes())
    args.output.write_bytes(result)
    print(f"{hashlib.sha256(result).hexdigest()}  {args.output}")


if __name__ == "__main__":
    main()
