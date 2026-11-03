"""The complete membership copy must survive the real PO → MO → gettext path."""

import collections
import gettext
import io
import json
from pathlib import Path
import re

import polib
import pytest


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def feature_keys():
    # Includes semantic error keys referenced outside t(), not only direct calls.
    keys = set()
    for source in (ROOT / "katrain/web/ui/src").rglob("*.ts*"):
        if ".test." not in source.name:
            keys.update(re.findall(r"['\"](membership:[a-zA-Z0-9_]+)['\"]", source.read_text()))
    return keys - {"membership:changed"}  # Browser invalidation event, not copy.


def catalog(lang):
    return polib.pofile(str(ROOT / f"katrain/i18n/locales/{lang}/LC_MESSAGES/katrain.po"))


@pytest.mark.parametrize("lang", LOCALES)
def test_membership_copy_is_translated_and_compiles(lang):
    po = catalog(lang)
    entries = {entry.msgid: entry for entry in po if not entry.obsolete}
    keys = feature_keys()
    assert keys, "The feature-copy inventory must not be empty"
    missing = sorted(key for key in keys if key not in entries or not entries[key].translated())
    assert not missing, f"{lang}: untranslated/fuzzy membership messages: {missing}"
    duplicates = [key for key, count in collections.Counter(e.msgid for e in po if not e.obsolete).items()
                  if key in keys and count > 1]
    assert not duplicates, f"{lang}: duplicate messages: {duplicates}"
    english = {entry.msgid: entry.msgstr for entry in catalog("en")}
    compiled = gettext.GNUTranslations(io.BytesIO(po.to_binary()))
    for key in keys:
        expected = entries[key].msgstr
        assert set(re.findall(r"\{\w+\}", expected)) == set(re.findall(r"\{\w+\}", english[key])), (lang, key)
        assert compiled.gettext(key) == expected, (lang, key)


def test_membership_batch_data_agrees_with_catalogs():
    path = ROOT / "scripts/membership_translations.json"
    assert path.exists(), "Membership translations must be part of the batch workflow"
    data = json.loads(path.read_text())
    assert feature_keys() <= data.keys()
    for lang in LOCALES:
        entries = {entry.msgid: entry.msgstr for entry in catalog(lang)}
        for key, translations in data.items():
            assert translations.get(lang), (key, lang)
            assert entries.get(key) == translations[lang], (key, lang)
