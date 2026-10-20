#!/usr/bin/env python3
"""Rebuild the three optional kiosk CJK faces from publisher originals.

Usage: python scripts/build-kiosk-cjk-fonts.py /path/to/Fonts_Kai.zip /path/to/AlimamaDaoLiTi-Regular.woff2
The DaoLi publisher forbids conversion or splitting; its WOFF2 is copied byte for byte.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


UI = Path(__file__).resolve().parents[1]
REPO = UI.parents[2]
ASSETS = UI / "src/kiosk-shell/fonts"
CSS = UI / "src/kiosk-shell/fonts.css"
START = "/* BEGIN generated optional kiosk CJK faces */"
END = "/* END generated optional kiosk CJK faces */"
# Chinese ideographs, radicals, and Chinese punctuation. ASCII/digits stay in
# the existing Latin-first faces even when a publisher source contains them.
UNICODES = (
    "U+2E80-2FFF,U+3000-303F,U+31C0-31EF,U+3400-4DBF,"
    "U+4E00-9FFF,U+F900-FAFF,U+FE10-FE1F,U+FE30-FE4F,"
    "U+FF01-FF0F,U+FF1A-FF20,U+FF3B-FF40,U+FF5B-FF60,"
    "U+20000-2FA1F"
)


def subset(source: Path, target: Path) -> None:
    subprocess.run(
        ["pyftsubset", str(source), f"--output-file={target}", "--flavor=woff2", f"--unicodes={UNICODES}"],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cns_archive", type=Path, help="Official https://www.cns11643.gov.tw/opendata/Fonts_Kai.zip")
    parser.add_argument("daoli_woff2", type=Path, help="Original publisher AlimamaDaoLiTi-Regular.woff2")
    args = parser.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp:
        with zipfile.ZipFile(args.cns_archive) as archive:
            matches = [name for name in archive.namelist() if Path(name).name == "TW-Kai-98_1.ttf"]
            if len(matches) != 1:
                raise RuntimeError(f"Expected one official TW-Kai-98_1.ttf; found {matches}")
            cns_source = Path(temp) / "TW-Kai-98_1.ttf"
            cns_source.write_bytes(archive.read(matches[0]))
            subset(cns_source, ASSETS / "cns-tw-kai-cjk.woff2")

    subset(REPO / "katrain/fonts/NotoSansCJKsc-Regular.otf", ASSETS / "noto-sans-cjk-sc-cjk.woff2")
    shutil.copyfile(args.daoli_woff2, ASSETS / "AlimamaDaoLiTi-Regular.woff2")

    block = f'''{START}
/* CNS11643 Full Repertoire TW-Kai; attribution and license: fonts/CJK-FONT-SOURCES.md */
@font-face{{font-family:"SmartBox CNS Kai";src:url("./fonts/cns-tw-kai-cjk.woff2") format("woff2");font-weight:400;font-style:normal;font-display:swap;unicode-range:{UNICODES}}}
/* Alibaba Design Alimama DaoLi original WOFF2, copied unchanged. */
@font-face{{font-family:"SmartBox DaoLi";src:url("./fonts/AlimamaDaoLiTi-Regular.woff2") format("woff2");font-weight:400;font-style:normal;font-display:swap;unicode-range:{UNICODES}}}
/* Noto Sans CJK SC (SIL OFL 1.1), from repository source. */
@font-face{{font-family:"SmartBox Noto Sans CJK";src:url("./fonts/noto-sans-cjk-sc-cjk.woff2") format("woff2");font-weight:400;font-style:normal;font-display:swap;unicode-range:{UNICODES}}}
{END}'''
    original = CSS.read_text(encoding="utf-8")
    if START in original:
        before, remainder = original.split(START, 1)
        _, after = remainder.split(END, 1)
        updated = before + block + after
    else:
        updated = original.rstrip() + "\n\n" + block + "\n"
    CSS.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
