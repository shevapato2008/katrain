"""Compile every supported locale, including Spanish, without editing PO sources."""

import argparse
from pathlib import Path

import polib


LANGUAGES = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def compile_catalogs(locale_root: Path) -> int:
    sources = [locale_root / lang / "LC_MESSAGES/katrain.po" for lang in LANGUAGES]
    # Validate the full input set before writing any output.
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(source)
    catalogs = [(source, polib.pofile(str(source))) for source in sources]
    for source, catalog in catalogs:
        catalog.save_as_mofile(str(source.with_suffix(".mo")))
    return len(catalogs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locale-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "katrain/i18n/locales",
    )
    args = parser.parse_args()
    print(f"Compiled {compile_catalogs(args.locale_root)} gettext catalogs")
