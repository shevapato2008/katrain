#!/usr/bin/env python3
"""霞鹜文楷正文方案的字节账——`design.md` §3.2 那张表就是这个脚本跑出来的。

结论先写在这里，省得每次重跑：
  · 「按界面用字做一次性子集」是最差解：单字重 808 KB，**而且照样在用户名上出豆腐块**
  · 分片必须**按频次**切。按码位切，中文页 40 片全命中、拉 1.9 MB，分片等于白做
  · 按频次切，中文页只命中 8/40 片、拉 340 KB，离 319 KB 的理论地板差 7%

语料取的是**编译后的 .mo**（不是 .po），因为 `i18n.py:19` 的 INACTIVE_LANGS 让 es 不参与编译,
运行时能拿到的就是这 10 个语种。

用法（仓库根目录，需要 LXGWWenKai-Regular.ttf）：
    uv run --with fonttools --with brotli python \
        superpowers/tracks/galaxy-ui-redesign/measure_font_budget.py path/to/LXGWWenKai-Regular.ttf
"""

import gettext
import io
import pathlib
import sys

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parents[3]
ACTIVE = ["en", "cn", "tw", "jp", "ko", "de", "fr", "ru", "tr", "ua"]  # es 不编译


def locale_codepoints(lang: str) -> set[int]:
    mo = ROOT / f"katrain/i18n/locales/{lang}/LC_MESSAGES/katrain.mo"
    catalog = gettext.GNUTranslations(mo.open("rb"))._catalog
    text = "".join(str(k) + str(v) for k, v in catalog.items() if k)
    return {ord(c) for c in text if c.isprintable() and not c.isspace()}


def woff2_size(src: str, codepoints) -> int:
    font = TTFont(src)
    opts = Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.layout_features = ["*"]
    opts.name_IDs = [1, 2, 3, 4, 6]
    opts.notdef_outline = False
    sub = Subsetter(options=opts)
    sub.populate(unicodes=sorted(codepoints))
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf, reorderTables=False)
    return len(buf.getvalue())


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "LXGWWenKai-Regular.ttf"
    if not pathlib.Path(src).exists():
        print(f"找不到字体：{src}\n从 https://github.com/lxgw/LxgwWenKai 下载 Regular 字重后重跑。")
        return 2

    cmap = set(TTFont(src).getBestCmap())
    cjk = sorted(c for c in cmap if 0x4E00 <= c <= 0x9FFF)
    cn = locale_codepoints("cn") & cmap
    allui = set().union(*(locale_codepoints(x) for x in ACTIVE)) & cmap

    def row(label, cps):
        print(f"  {label:34} {len(cps):6} 码位  {woff2_size(src, cps)/1024:9.1f} KB")

    print(f"字体自带 {len(cmap)} 码位，其中 CJK 基本区 {len(cjk)}\n")
    row("中文界面实际用到的字", cn)
    row("10 个启用语种合计", allui)
    row("上面 + CJK 前 3500 字", allui | set(cjk[:3500]))
    row("整套字面", cmap)

    print("\n=== 分片顺序：同样 40 片、同样覆盖范围，只差排序 ===")
    target = sorted(allui | set(cjk[:3500]))
    for name, ordered in (
        ("按码位序", target),
        ("按频次序（界面用字排前）", sorted(cn) + [c for c in target if c not in cn]),
    ):
        n = 40
        chunks = [ordered[i * len(ordered) // n : (i + 1) * len(ordered) // n] for i in range(n)]
        hit = [c for c in chunks if any(x in cn for x in c)]
        pulled = sum(woff2_size(src, c) for c in hit)
        print(f"  {name:24} 中文页命中 {len(hit):2}/{n} 片，首屏拉取 {pulled/1024:8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
