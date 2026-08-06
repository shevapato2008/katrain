import hashlib
import json
import os
import re
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

import scripts.build_galaxy_fonts as fonts

from scripts.build_galaxy_fonts import (
    BRAND_TEXT,
    CHINESE_LOCALES,
    INPUTS,
    build_manifest,
    catalog_seed_codepoints,
    is_chinese_ui_codepoint,
    prepare_output_directory,
    unicode_range,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_ASSETS = REPO_ROOT / "katrain/web/ui/src/galaxy/assets/fonts"


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
    assert set(first) == {"generator_command", "generated_total_bytes", "outputs", "inputs", "toolchain"}
    assert first["generator_command"] == (
        "uv run --with fonttools==4.61.1 --with brotli==1.2.0 python scripts/build_galaxy_fonts.py "
        "--regular /private/tmp/galaxy-font-sources/LXGWWenKai-Regular.ttf "
        "--medium /private/tmp/galaxy-font-sources/LXGWWenKai-Medium.ttf "
        "--longcang /private/tmp/galaxy-font-sources/LongCang-Regular.ttf --out $OUT"
    )
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
    assert first["toolchain"] == {"fonttools": "4.61.1", "brotli": "1.2.0"}


def test_cli_requires_local_input_files_and_out(tmp_path):
    paths = [tmp_path / name for name in ("regular.ttf", "medium.ttf", "longcang.ttf")]
    args = fonts.parse_args(
        [
            "--regular",
            str(paths[0]),
            "--medium",
            str(paths[1]),
            "--longcang",
            str(paths[2]),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert (args.regular, args.medium, args.longcang, args.out) == (*paths, tmp_path / "out")


def test_local_input_hash_mismatch_is_rejected_before_output_changes(tmp_path):
    inputs = [tmp_path / name for name in ("regular.ttf", "medium.ttf", "longcang.ttf")]
    for path in inputs:
        path.write_bytes(b"not an approved font")
    output = tmp_path / "out"

    with pytest.raises(RuntimeError, match="SHA-256 mismatch.*LXGW WenKai Regular"):
        fonts.build_fonts(output, tmp_path, regular=inputs[0], medium=inputs[1], longcang=inputs[2])
    assert not output.exists()


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


def test_production_output_directory_symlink_is_rejected_without_deleting_external_files(tmp_path):
    repo_root = tmp_path / "repo"
    parent = repo_root / "katrain/web/ui/src/galaxy/assets"
    parent.mkdir(parents=True)
    external = tmp_path / "external-fonts"
    external.mkdir()
    victim = external / "wenkai-400-000.woff2"
    victim.write_bytes(b"external data")
    (parent / "fonts").symlink_to(external, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        prepare_output_directory(parent / "fonts", repo_root)
    assert victim.read_bytes() == b"external data"


def test_production_output_rejects_symlink_in_existing_path_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    external = tmp_path / "external-katrain"
    output = external / "web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    victim = output / "wenkai-400-000.woff2"
    victim.write_bytes(b"external data")
    (repo_root / "katrain").symlink_to(external, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        prepare_output_directory(repo_root / "katrain/web/ui/src/galaxy/assets/fonts", repo_root)
    assert victim.read_bytes() == b"external data"


def test_production_output_rejects_generated_name_symlink(tmp_path):
    repo_root = tmp_path / "repo"
    output = repo_root / "katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    external = tmp_path / "font.woff2"
    external.write_bytes(b"external data")
    generated_link = output / "wenkai-400-000.woff2"
    generated_link.symlink_to(external)

    with pytest.raises(RuntimeError, match="symlink"):
        prepare_output_directory(output, repo_root)
    assert generated_link.is_symlink()
    assert external.read_bytes() == b"external data"


def test_unicode_range_compacts_adjacent_codepoints_without_expanding_gaps():
    assert unicode_range((0x3000, 0x3001, 0x3003, 0x4E00, 0x4E01, 0x4E02)) == (
        "U+3000-3001, U+3003, U+4E00-4E02"
    )


def test_committed_woff2_cmaps_have_no_ascii_and_brand_is_exact():
    font_paths = sorted(FONT_ASSETS.glob("*.woff2"))
    assert font_paths
    cmaps = {path.name: set(TTFont(path, recalcTimestamp=False).getBestCmap() or {}) for path in font_paths}

    forbidden = set(map(ord, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"))
    assert all(not (codepoints & forbidden) for codepoints in cmaps.values())
    assert cmaps["longcang-brand.woff2"] == set(map(ord, BRAND_TEXT))


def test_committed_css_references_manifested_outputs_with_matching_hashes_and_bytes():
    css_path = FONT_ASSETS / "galaxy-fonts.css"
    css = css_path.read_text(encoding="utf-8")
    manifest = json.loads((FONT_ASSETS / "sources.json").read_text(encoding="utf-8"))
    outputs = {item["filename"]: item for item in manifest["outputs"]}
    references = set(re.findall(r'url\("\./([^"/]+\.woff2)"\)', css))

    assert references
    assert references == {name for name in outputs if name.endswith(".woff2")}
    assert set(outputs) == references | {"galaxy-fonts.css"}
    for filename, metadata in outputs.items():
        path = FONT_ASSETS / filename
        assert path.is_file()
        assert path.stat().st_size == metadata["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]


def test_committed_wenkai_chunks_are_disjoint_and_remaining_chunks_are_ordered():
    for weight in (400, 500):
        chunks = []
        for path in sorted(FONT_ASSETS.glob(f"wenkai-{weight}-*.woff2")):
            chunks.append(set(TTFont(path, recalcTimestamp=False).getBestCmap() or {}))
        assert chunks
        seen: set[int] = set()
        for chunk in chunks:
            assert not (seen & chunk)
            seen.update(chunk)
        remaining = [codepoint for chunk in chunks[1:] for codepoint in sorted(chunk)]
        assert remaining == sorted(remaining)


def test_committed_css_uses_compact_ranges_with_exact_cmap_coverage():
    css = (FONT_ASSETS / "galaxy-fonts.css").read_text(encoding="utf-8")
    assert len(css.encode("utf-8")) < 60_000
    faces = re.findall(r'url\("\./([^"/]+\.woff2)"\).*?unicode-range: ([^;]+);', css, re.DOTALL)
    assert faces
    for filename, encoded_ranges in faces:
        decoded: set[int] = set()
        for item in encoded_ranges.split(", "):
            bounds = item.removeprefix("U+").split("-")
            start = int(bounds[0], 16)
            end = int(bounds[-1], 16)
            decoded.update(range(start, end + 1))
        cmap = set(TTFont(FONT_ASSETS / filename, recalcTimestamp=False).getBestCmap() or {})
        assert decoded == cmap
        assert all(is_chinese_ui_codepoint(codepoint) for codepoint in decoded)


def test_subset_failure_leaves_existing_production_generated_files_unchanged(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    output = repo_root / "katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    catalogs = repo_root / "katrain/i18n/locales"
    for locale in CHINESE_LOCALES:
        catalog = catalogs / locale / "LC_MESSAGES/katrain.po"
        catalog.parent.mkdir(parents=True)
        catalog.write_text('msgstr "棋"\n', encoding="utf-8")
    existing = {
        "wenkai-400-000.woff2": b"old regular",
        "longcang-brand.woff2": b"old brand",
        "galaxy-fonts.css": b"old css",
        "sources.json": b"old manifest",
    }
    for filename, content in existing.items():
        (output / filename).write_bytes(content)
    fake_inputs = [tmp_path / name for name in ("regular.ttf", "medium.ttf", "longcang.ttf")]
    for path in fake_inputs:
        path.write_bytes(b"fake")
    monkeypatch.setattr(
        fonts,
        "snapshot_input_files",
        lambda regular, medium, longcang, staging: {
            source.name: path for source, path in zip(INPUTS, fake_inputs, strict=True)
        },
    )
    monkeypatch.setattr(fonts, "font_codepoints", lambda path: {ord("棋")})
    monkeypatch.setattr(fonts, "subset_font", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        fonts.build_fonts(
            output,
            repo_root,
            regular=fake_inputs[0],
            medium=fake_inputs[1],
            longcang=fake_inputs[2],
        )

    assert {filename: (output / filename).read_bytes() for filename in existing} == existing


def test_committed_upstream_license_files_are_unmodified_and_documented():
    expected = {
        "OFL-LXGW-WenKai.txt": "c38b1994a5e48ac30ac7d1da7d0409fd8fd8127dfe28a13d6e787d5b1ef34a5e",
        "OFL-Long-Cang.txt": "603546b7219a94bb59bf8294458194a5010119486354092b66a09a3fd61aeacc",
    }
    readme = (FONT_ASSETS / "README.md").read_text(encoding="utf-8")
    for filename, sha256 in expected.items():
        path = FONT_ASSETS / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256
        assert filename in readme


def test_publish_failure_restores_all_old_production_files_without_mixing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    output = repo_root / "katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    preserved = {
        "README.md": b"docs",
        "OFL-LXGW-WenKai.txt": b"lxgw license",
        "OFL-Long-Cang.txt": b"long cang license",
    }
    old_generated = {
        "wenkai-400-000.woff2": b"old regular",
        "wenkai-500-000.woff2": b"old medium",
        "longcang-brand.woff2": b"old brand",
        "galaxy-fonts.css": b"old css",
        "sources.json": b'{"old": true}\n',
    }
    for filename, content in (preserved | old_generated).items():
        (output / filename).write_bytes(content)

    staging = output.parent / ".galaxy-fonts-staging-test"
    staging.mkdir()
    new_generated = {
        "wenkai-400-000.woff2": b"new regular",
        "wenkai-500-000.woff2": b"new medium",
        "longcang-brand.woff2": b"new brand",
        "galaxy-fonts.css": b"new css",
        "sources.json": b'{"new": true}\n',
    }
    for filename, content in new_generated.items():
        (staging / filename).write_bytes(content)

    original_replace = Path.replace

    def fail_during_new_publish(path, target):
        if path.parent == staging and path.name == "wenkai-500-000.woff2":
            raise OSError("injected publish failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_during_new_publish)

    with pytest.raises(OSError, match="injected publish failure"):
        fonts.publish_staging(staging, output, repo_root)

    assert {name: (output / name).read_bytes() for name in old_generated} == old_generated
    assert {name: (output / name).read_bytes() for name in preserved} == preserved
    assert {path.name for path in output.iterdir()} == set(old_generated) | set(preserved)
    assert not list(output.parent.glob(".galaxy-fonts-backup-*"))


def test_build_uses_private_input_snapshot_after_hash_validation(tmp_path, monkeypatch):
    input_bytes = (b"approved regular", b"approved medium", b"approved longcang")
    input_paths = tuple(tmp_path / source.filename for source in INPUTS)
    for path, content in zip(input_paths, input_bytes, strict=True):
        path.write_bytes(content)
    approved_inputs = tuple(
        replace(source, sha256=hashlib.sha256(content).hexdigest())
        for source, content in zip(INPUTS, input_bytes, strict=True)
    )
    monkeypatch.setattr(fonts, "INPUTS", approved_inputs)
    observed = {}

    def observe_private_sources(staging, repo_root, sources):
        replacement = tmp_path / "replacement.ttf"
        replacement.write_bytes(b"changed after validation")
        replacement.replace(input_paths[0])
        snapshot = sources["LXGW WenKai Regular"]
        observed["path"] = snapshot
        observed["bytes"] = snapshot.read_bytes()
        raise RuntimeError("stop after observing snapshot")

    monkeypatch.setattr(fonts, "generate_fonts", observe_private_sources)

    with pytest.raises(RuntimeError, match="stop after observing snapshot"):
        fonts.build_fonts(
            tmp_path / "out",
            tmp_path / "repo",
            regular=input_paths[0],
            medium=input_paths[1],
            longcang=input_paths[2],
        )

    assert observed["bytes"] == input_bytes[0]
    assert observed["path"] != input_paths[0]
    assert not list(tmp_path.glob(".galaxy-fonts-staging-*"))


@pytest.mark.parametrize("operation", ["validate", "build", "publish"])
@pytest.mark.parametrize("entry_kind", ["directory", "fifo"])
def test_generated_name_non_regular_file_is_rejected_and_preserved(tmp_path, operation, entry_kind):
    if entry_kind == "fifo" and not hasattr(os, "mkfifo"):
        pytest.skip("FIFO is not supported on this platform")
    repo_root = tmp_path / "repo"
    output = repo_root / "katrain/web/ui/src/galaxy/assets/fonts"
    output.mkdir(parents=True)
    generated_entry = output / "wenkai-notes.woff2"
    if entry_kind == "directory":
        generated_entry.mkdir()
        (generated_entry / "keep.txt").write_bytes(b"preserve me")
    else:
        os.mkfifo(generated_entry)

    if operation == "validate":
        invoke = lambda: fonts.validate_output_directory(output, repo_root)
    elif operation == "build":
        invoke = lambda: fonts.build_fonts(
            output,
            repo_root,
            regular=tmp_path / "regular.ttf",
            medium=tmp_path / "medium.ttf",
            longcang=tmp_path / "longcang.ttf",
        )
    else:
        staging = output.parent / ".galaxy-fonts-staging-test"
        staging.mkdir()
        invoke = lambda: fonts.publish_staging(staging, output, repo_root)

    with pytest.raises(RuntimeError, match="regular file"):
        invoke()

    if entry_kind == "directory":
        assert (generated_entry / "keep.txt").read_bytes() == b"preserve me"
    else:
        assert stat.S_ISFIFO(generated_entry.lstat().st_mode)
    assert not list(output.parent.glob(".galaxy-fonts-backup-*"))
