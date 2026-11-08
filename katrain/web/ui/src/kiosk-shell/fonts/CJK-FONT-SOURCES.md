# Optional kiosk Chinese fonts

- **楷体:** `cns-tw-kai-*.woff2` contains Chinese-only shards of `TW-Kai-98_1.ttf` from the [CNS11643 Full Repertoire official Kai archive](https://www.cns11643.gov.tw/opendata/Fonts_Kai.zip). The former single 13 MB `cns-tw-kai-cjk.woff2` remains as a source artifact; RK3562 Chromium 120 rejects that face, so the UI loads smaller shards and falls back to WenKai for rare characters outside the basic CJK range. Source attribution: Ministry of Digital Affairs, CNS11643 Chinese Standard Interchange Code Full Repertoire, https://www.cns11643.gov.tw. The [official authorization](https://www.cns11643.gov.tw/pageView.jsp?ID=59&la=1) permits modification, embedding, and redistribution with attribution (Open Government Data License v1.0 / OFL 1.1).
- **隶书:** `AlimamaDaoLiTi-Regular.woff2` is the unchanged publisher file from https://fonts.alibabadesign.com/AlimamaDaoLiTi/AlimamaDaoLiTi-Regular/AlimamaDaoLiTi-Regular.woff2. Alibaba Design's [DaoLi license statement](https://www.yuque.com/alimama_ai-font/vfse9w/ynqpf9pt8wops4sl) permits embedding and prohibits conversion/splitting; the CSS `unicode-range` only controls routing and does not alter the font bytes. Attribution: Alimama / Alibaba Design, 阿里妈妈刀隶体.
- **黑体:** `noto-sans-cjk-sc-cjk.woff2` is a Chinese-only subset of the repository's `katrain/fonts/NotoSansCJKsc-Regular.otf`, under its SIL Open Font License 1.1 in `katrain/fonts/OFL.txt`. Attribution: Google Noto Fonts / Adobe, Noto Sans CJK SC.
- **文楷:** The existing `wenkai/` subsets and `wenkai/OFL-LXGWWenKai.txt` remain the default. Attribution: LXGW WenKai authors.

Rebuild the optional assets and CSS declarations with `python scripts/build-kiosk-cjk-fonts.py /path/to/Fonts_Kai.zip /path/to/AlimamaDaoLiTi-Regular.woff2` from `katrain/web/ui`. Download the two publisher sources at the URLs above; the Alimama host requires `Referer: https://fonts.alibabadesign.com/` for direct download.

The asset build requires Python `fonttools` with Brotli support. The bundled DaoLi file has SHA-256 `85a8afa1a7503418575793effe55bd13d99b3d0f5a82fdb7e83ec1c4910a2efb`, matching the publisher download byte for byte.

## Japanese and Korean script support

`noto-sans-cjk-jp-kr-scripts.woff2` is a kana/Hangul-only derivative of the same complete licensed source, `katrain/fonts/NotoSansCJKsc-Regular.otf` in this repository (source SHA-256 `1652500938055a232cfbfa321de6ebaadfc5635dd9f75e369bc991d14a6512dd`, version 1.004). Attribution: Google Noto Fonts / Adobe. It retains source copyright and license metadata; the SIL OFL 1.1 is already bundled as `OFL-NotoSansCJK.txt`. Its internal derivative family is named **SmartBox CJK Scripts**.

The subset covers the source's hiragana, katakana, halfwidth kana, Hangul syllables, modern/extended jamo, compatibility and halfwidth Hangul. It includes every modern Hangul syllable (`U+AC00–D7A3`), with no Latin, digits or Han. As with the source, recently added rare kana outside its Unicode coverage are not supplied. This is a script fallback, not an editorial text subset.

`fonts.css` and `KioskTypographyContext.tsx` routes Japanese/Korean body Han to the existing Noto CJK face. That face retains its `JAN`/`KOR` `locl` substitutions, selected by the root's actual `lang` attribute; applications must set `lang="ja"`/`lang="ko"` rather than a CSS-only language flag. Kana/Hangul then use the script face. Brand marks, ordinary Latin, numeric runs, coordinates and explicitly owned piece glyphs keep their existing fonts. Chinese font choices remain effective in Chinese UI.

Reproduce the script subset from the workspace root with FontTools and Brotli:

```sh
python -m fontTools.subset katrain/fonts/NotoSansCJKsc-Regular.otf --unicodes=U+1100-11FF,U+3040-30FF,U+3130-318F,U+31F0-31FF,U+A960-A97F,U+AC00-D7AF,U+D7B0-D7FF,U+FF61-FFDC,U+1B000-1B16F --layout-features='*' --layout-scripts='*' --name-IDs='*' --name-languages='*' --flavor=woff2 --output-file=katrain/web/ui/src/kiosk-shell/fonts/noto-sans-cjk-jp-kr-scripts.woff2
```

Then rename name-table IDs 1/4/6/16/17 to `SmartBox CJK Scripts`, `SmartBox CJK Scripts Regular`, `SmartBoxCJK-Scripts-Regular`, `SmartBox CJK Scripts`, `Regular` respectively, and the CFF font name/FamilyName/FullName likewise. Preserve copyright/license records and source timestamps. The final asset digest is recorded in the adjacent kiosk-shell `MANIFEST.sha256`. This owned copy makes standalone Go builds independent of the parent repository.
