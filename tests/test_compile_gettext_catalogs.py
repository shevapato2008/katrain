"""Release compilation includes all supported languages without rewriting PO sources."""

import gettext
import importlib.util
from pathlib import Path

import polib
import pytest


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def compiler():
    path = ROOT / "scripts/compile_gettext_catalogs.py"
    spec = importlib.util.spec_from_file_location("compile_gettext_catalogs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compile_catalogs


def test_all_eleven_catalogs_compile_without_changing_source(tmp_path):
    before = {}
    for lang in LANGUAGES:
        path = tmp_path / lang / "LC_MESSAGES/katrain.po"
        path.parent.mkdir(parents=True)
        po = polib.POFile()
        po.metadata = {"Content-Type": "text/plain; charset=UTF-8"}
        po.append(polib.POEntry(msgid="membership:wechat_pay", msgstr=f"WeChat {lang}"))
        po.save(path)
        before[path] = path.read_bytes()
    assert compiler()(tmp_path) == len(LANGUAGES)
    for path, original in before.items():
        assert path.read_bytes() == original
        with path.with_suffix(".mo").open("rb") as stream:
            assert gettext.GNUTranslations(stream).gettext("membership:wechat_pay") == f"WeChat {path.parents[1].name}"


def test_missing_supported_catalog_fails_instead_of_shipping_incomplete_release(tmp_path):
    with pytest.raises(FileNotFoundError):
        compiler()(tmp_path)
