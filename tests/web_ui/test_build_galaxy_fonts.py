import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_galaxy_fonts import (
    BRAND_TEXT,
    CHINESE_LOCALES,
    INPUTS,
    build_manifest,
    catalog_seed_codepoints,
    is_chinese_ui_codepoint,
    prepare_output_directory,
)


def test_chinese_ui_codepoint_accepts_cjk_and_chinese_punctuation_only():
    for character in "棋。、《》（）！":
        assert is_chinese_ui_codepoint(ord(character)), character

    for character in "Az09あア한ＡＺ０９":
        assert not is_chinese_ui_codepoint(ord(character)), character


def test_catalog_seed_uses_cn_then_tw_and_filters_english():
    catalogs = {
        "en": 'msgstr "English棋"',
        "tw": 'msgstr "後手，Beta"',
        "cn": 'msgstr "棋手。Alpha"',
        "jp": 'msgstr "日本語"',
    }

    assert CHINESE_LOCALES == ("cn", "tw")
    assert catalog_seed_codepoints(catalogs) == tuple(map(ord, "棋手。後，"))
    assert all(not chr(codepoint).isascii() for codepoint in catalog_seed_codepoints(catalogs))


def test_brand_font_text_is_exact():
    assert BRAND_TEXT == "智星盒"


def test_manifest_is_deterministic_and_records_provenance(tmp_path):
    output = tmp_path / "wenkai-400-000.woff2"
    output.write_bytes(b"font bytes")

    first = build_manifest([output])
    second = build_manifest([output])

    assert first == second
    assert first["generator_command"].endswith("--output $OUT")
    assert str(tmp_path) not in json.dumps(first, ensure_ascii=False)
    assert first["generated_total_bytes"] == len(b"font bytes")
    assert first["outputs"] == [
        {
            "filename": output.name,
            "sha256": hashlib.sha256(b"font bytes").hexdigest(),
            "bytes": len(b"font bytes"),
        }
    ]
    assert len(first["inputs"]) == 3
    for item in first["inputs"]:
        assert set(item) == {"name", "url", "version", "filename", "sha256", "license"}
        assert item["license"] == "SIL OFL 1.1"
        assert item["url"].startswith("https://")
        assert len(item["sha256"]) == 64
    assert first["inputs"] == [source.manifest_entry() for source in INPUTS]


def test_nonproduction_output_must_be_absent_or_empty(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    output = tmp_path / "preview"

    prepare_output_directory(output, repo_root)
    assert output.is_dir()

    (output / "unexpected.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        prepare_output_directory(output, repo_root)
    assert (output / "unexpected.txt").read_text(encoding="utf-8") == "keep"


def test_production_output_cleans_only_generated_names(tmp_path):
    repo_root = tmp_path / "repo"
    output = repo_root / "katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    preserved = output / "README.md"
    preserved.write_text("documentation", encoding="utf-8")
    generated = [
        output / "wenkai-400-000.woff2",
        output / "wenkai-500-003.woff2",
        output / "longcang-brand.woff2",
        output / "galaxy-fonts.css",
        output / "sources.json",
    ]
    for path in generated:
        path.write_bytes(b"stale")

    prepare_output_directory(output, repo_root)

    assert preserved.read_text(encoding="utf-8") == "documentation"
    assert not any(path.exists() for path in generated)


def test_similar_but_not_exact_production_path_fails_closed(tmp_path):
    repo_root = tmp_path / "repo"
    output = repo_root / "copy/katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    stale = output / "wenkai-400-000.woff2"
    stale.write_bytes(b"must not be deleted")

    with pytest.raises(RuntimeError, match="empty"):
        prepare_output_directory(output, repo_root)
    assert stale.read_bytes() == b"must not be deleted"
