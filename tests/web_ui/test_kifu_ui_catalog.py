"""The native kifu list/replay/report journey has five complete UI catalogs."""

import json
import re
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ("cn", "tw", "en", "jp", "ko")


def test_kifu_visible_fallback_labels_have_five_language_translations():
    fallback = json.loads((ROOT / "katrain/web/ui/src/kiosk/appearance/kifuMessages.json").read_text())
    catalogs = {
        language: {
            item.msgid: item.msgstr
            for item in polib.pofile(str(ROOT / f"katrain/i18n/locales/{language}/LC_MESSAGES/katrain.po"))
            if item.msgstr
        }
        for language in LOCALES
    }
    calls = {}
    sources = list((ROOT / "katrain/web/ui/src/kiosk/pages").glob("Kifu*Page.tsx"))
    sources.append(ROOT / "katrain/web/ui/src/components/CompactPagination.tsx")
    for path in sources:
        for key, default in re.findall(r"\bt\(\s*'([^']+)'\s*,\s*'([^']*)'", path.read_text()):
            if re.search(r"[\u3400-\u9fff]", default):
                calls[key] = default
    assert "kifu:selected_game" in calls
    assert "kifu:jump" in calls
    for key in calls:
        for language in LOCALES:
            value = catalogs[language].get(key) or fallback.get(key, {}).get(language)
            assert value and value.strip(), (key, language)
    for key, variants in fallback.items():
        assert set(variants) == set(LOCALES), key
        for language in ("en", "jp", "ko"):
            assert variants[language] != variants["cn"], (key, language)
