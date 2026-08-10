#!/usr/bin/env python3
"""哪些 t('…') 请求的键，词表里其实没有。

缺键不会报错，`t(key, fallback)` 会安静地渲染第二参数——所以缺口只能靠比对发现。
后果还分两种方向：galaxy 侧的兜底多半写死英文，kiosk 侧多半写死中文，
两边都在给另一半用户漏字。

用法（仓库根目录）：
    uv run python superpowers/tracks/galaxy-ui-redesign/audit_i18n_keys.py
    uv run python superpowers/tracks/galaxy-ui-redesign/audit_i18n_keys.py --area galaxy

只认第一个参数是**字面量字符串**的调用。模板字符串动态拼出来的键（`t(`tsumego:${cat}`)`）
本来就查不出来，也不该由这个脚本猜——真要查得另写一份按前缀反查的。
"""

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "katrain/web/ui/src"
PO = ROOT / "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"

# t('key' / t("key" / i18n.t('key'，允许前面有空白；(?<![\w.]) 挡掉 foo.t( 之类的误匹配
CALL = re.compile(r"""(?<![\w.])(?:i18n\.)?t\(\s*(['"])((?:[^'"\\]|\\.)*?)\1""")
MSGID = re.compile(r'^msgid "((?:[^"\\]|\\.)*)"', re.M)


def is_test(p: pathlib.Path) -> bool:
    return "__tests__" in p.parts or p.name.endswith(
        (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".d.ts")
    )


def area_of(rel: str) -> str:
    top = rel.split("/")[0]
    return top if top in {"galaxy", "kiosk"} else f"shared/{top}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", help="只列这个区域消费的缺键，例如 galaxy")
    args = ap.parse_args()

    msgids = set(MSGID.findall(PO.read_text(encoding="utf-8")))

    used: dict[str, set[str]] = collections.defaultdict(set)
    for p in sorted(SRC.rglob("*.ts*")):
        if is_test(p):
            continue
        for m in CALL.finditer(p.read_text(encoding="utf-8")):
            used[m.group(2)].add(area_of(str(p.relative_to(SRC))))

    missing = {k: v for k, v in used.items() if k not in msgids}

    print(f"UI 请求的不同键 {len(used)} → 词表里没有 {len(missing)}\n")
    by_area = collections.Counter("+".join(sorted(a)) for a in missing.values())
    for a, n in by_area.most_common():
        print(f"  {n:4}  {a}")

    if args.area:
        hits = sorted(k for k, a in missing.items() if args.area in a)
        print(f"\n=== {args.area} 相关缺键 {len(hits)} ===")
        for k in hits:
            print(f"  {k!r:44} <- {'+'.join(sorted(missing[k]))}")
        return 1 if hits else 0
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
