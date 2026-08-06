#!/usr/bin/env python3
"""Build deterministic, Galaxy-only Chinese webfont subsets."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from fontTools import subset
from fontTools.ttLib import TTFont


CHINESE_LOCALES = ("cn", "tw")
BRAND_TEXT = "智星盒"
ALLOWED_RANGES = (
    (0x3000, 0x303F),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF01, 0xFF60),
)
FULLWIDTH_LATIN_AND_DIGITS = (
    (0xFF10, 0xFF19),
    (0xFF21, 0xFF3A),
    (0xFF41, 0xFF5A),
)
CHUNK_SIZE = 1200
SOURCE_CACHE = Path("/private/tmp/galaxy-font-sources")
GENERATOR_COMMAND = "uv run --with fonttools --with brotli python scripts/build_galaxy_fonts.py --output $OUT"


@dataclass(frozen=True)
class FontSource:
    name: str
    url: str
    version: str
    filename: str
    sha256: str
    license: str = "SIL OFL 1.1"

    def manifest_entry(self) -> dict[str, str]:
        return {
            "name": self.name,
            "url": self.url,
            "version": self.version,
            "filename": self.filename,
            "sha256": self.sha256,
            "license": self.license,
        }


INPUTS = (
    FontSource(
        name="LXGW WenKai Regular",
        url="https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf",
        version="v1.522",
        filename="LXGWWenKai-Regular.ttf",
        sha256="39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009",
    ),
    FontSource(
        name="LXGW WenKai Medium",
        url="https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Medium.ttf",
        version="v1.522",
        filename="LXGWWenKai-Medium.ttf",
        sha256="d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6",
    ),
    FontSource(
        name="Long Cang Regular",
        url=(
            "https://raw.githubusercontent.com/google/fonts/"
            "b7b1d76caa907473438546739b2ce3a92631adc3/ofl/longcang/LongCang-Regular.ttf"
        ),
        version="b7b1d76caa907473438546739b2ce3a92631adc3",
        filename="LongCang-Regular.ttf",
        sha256="e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc",
    ),
)


def is_chinese_ui_codepoint(codepoint: int) -> bool:
    if 0x00 <= codepoint <= 0x7F:
        return False
    if any(start <= codepoint <= end for start, end in FULLWIDTH_LATIN_AND_DIGITS):
        return False
    return any(start <= codepoint <= end for start, end in ALLOWED_RANGES)


def catalog_seed_codepoints(catalogs: Mapping[str, str]) -> tuple[int, ...]:
    seen: set[int] = set()
    ordered: list[int] = []
    for locale in CHINESE_LOCALES:
        for character in catalogs.get(locale, ""):
            codepoint = ord(character)
            if is_chinese_ui_codepoint(codepoint) and codepoint not in seen:
                seen.add(codepoint)
                ordered.append(codepoint)
    return tuple(ordered)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(output_paths: Sequence[Path]) -> dict[str, object]:
    outputs = []
    for path in sorted(output_paths, key=lambda item: item.name):
        outputs.append({"filename": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return {
        "generator_command": GENERATOR_COMMAND,
        "generated_total_bytes": sum(item["bytes"] for item in outputs),
        "outputs": outputs,
        "inputs": [source.manifest_entry() for source in INPUTS],
    }


def production_output(repo_root: Path) -> Path:
    return (repo_root / "katrain/web/ui/src/galaxy/assets/fonts").resolve()


def prepare_output_directory(output: Path, repo_root: Path) -> None:
    output = output.resolve()
    expected_production = production_output(repo_root)
    if output == expected_production:
        output.mkdir(parents=True, exist_ok=True)
        for path in output.iterdir():
            if (
                (path.is_file() and path.name.startswith("wenkai-") and path.name.endswith(".woff2"))
                or path.name in {"longcang-brand.woff2", "galaxy-fonts.css", "sources.json"}
            ):
                path.unlink()
        return
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise RuntimeError(f"Non-production output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def download_and_verify(source: FontSource) -> Path:
    SOURCE_CACHE.mkdir(parents=True, exist_ok=True)
    destination = SOURCE_CACHE / source.filename
    if not destination.exists() or sha256_file(destination) != source.sha256:
        temporary = destination.with_suffix(destination.suffix + ".download")
        urllib.request.urlretrieve(source.url, temporary)
        actual = sha256_file(temporary)
        if actual != source.sha256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"SHA-256 mismatch for {source.name}: expected {source.sha256}, got {actual}")
        temporary.replace(destination)
    actual = sha256_file(destination)
    if actual != source.sha256:
        raise RuntimeError(f"SHA-256 mismatch for cached {source.name}: expected {source.sha256}, got {actual}")
    return destination


def font_codepoints(path: Path) -> set[int]:
    with TTFont(path, recalcTimestamp=False, lazy=True) as font:
        return set(font.getBestCmap() or {})


def ordered_chunks(priority: Iterable[int], available: set[int]) -> list[tuple[int, ...]]:
    priority_chunk = tuple(codepoint for codepoint in priority if codepoint in available)
    priority_set = set(priority_chunk)
    remaining = sorted(codepoint for codepoint in available if is_chinese_ui_codepoint(codepoint) and codepoint not in priority_set)
    chunks = [priority_chunk] if priority_chunk else []
    chunks.extend(tuple(remaining[index : index + CHUNK_SIZE]) for index in range(0, len(remaining), CHUNK_SIZE))
    return chunks


def subset_font(source: Path, destination: Path, codepoints: Iterable[int]) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.recalc_timestamp = False
    options.canonical_order = True
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    subset.save_font(font, str(destination), options)


def unicode_range(codepoints: Sequence[int]) -> str:
    return ", ".join(f"U+{codepoint:04X}" for codepoint in codepoints)


def css_face(family: str, filename: str, weight: str, codepoints: Sequence[int]) -> str:
    return "\n".join(
        (
            "@font-face {",
            f'  font-family: "{family}";',
            f'  src: url("./{filename}") format("woff2");',
            "  font-style: normal;",
            f"  font-weight: {weight};",
            "  font-display: swap;",
            f"  unicode-range: {unicode_range(codepoints)};",
            "}",
        )
    )


def load_catalogs(repo_root: Path) -> dict[str, str]:
    return {
        locale: (repo_root / f"katrain/i18n/locales/{locale}/LC_MESSAGES/katrain.po").read_text(encoding="utf-8")
        for locale in CHINESE_LOCALES
    }


def build_fonts(output: Path, repo_root: Path) -> None:
    prepare_output_directory(output, repo_root)
    sources = {source.name: download_and_verify(source) for source in INPUTS}
    priority = catalog_seed_codepoints(load_catalogs(repo_root))
    generated: list[Path] = []
    faces: list[str] = []

    for source_name, file_weight, css_weight in (
        ("LXGW WenKai Regular", 400, "400"),
        ("LXGW WenKai Medium", 500, "500 700"),
    ):
        source = sources[source_name]
        for index, codepoints in enumerate(ordered_chunks(priority, font_codepoints(source))):
            destination = output / f"wenkai-{file_weight}-{index:03d}.woff2"
            subset_font(source, destination, codepoints)
            generated.append(destination)
            faces.append(css_face("Galaxy WenKai", destination.name, css_weight, codepoints))

    brand_path = output / "longcang-brand.woff2"
    brand_codepoints = tuple(map(ord, BRAND_TEXT))
    subset_font(sources["Long Cang Regular"], brand_path, brand_codepoints)
    generated.append(brand_path)
    faces.append(css_face("Galaxy Long Cang", brand_path.name, "400", brand_codepoints))

    css_path = output / "galaxy-fonts.css"
    css_path.write_text("\n\n".join(faces) + "\n\n.galaxy-app {\n  font-synthesis: none;\n}\n", encoding="utf-8")
    generated.append(css_path)
    manifest = build_manifest(generated)
    (output / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    build_fonts(args.output, repo_root)


if __name__ == "__main__":
    main()
