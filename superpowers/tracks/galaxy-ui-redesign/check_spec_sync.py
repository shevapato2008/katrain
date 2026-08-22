#!/usr/bin/env python3
"""规范 ↔ 消费方对账闸。

**它守的是什么**

2026-08-22，规范 §2.4 按 Fan 的裁定改写了（返回键移到左上角、上一级简称不上屏）。
实现跟着改了，而**冻结原型的 `cph()` 没跟** —— 稿子带着裁定前的形状活到了 S8，
靠人工比对才抓到。当时把这条记进待议：「`proto/check.py` 不与 spec 对账，
所以『规范改了、稿子没跟』这类漂移它是全盲的」。

`proto/check.py` 检的是另一件事：**清单里的每个控件在原型里有没有被画出来**。
它是标签匹配，看不见「页头的形状」这种东西 —— 返回键挪到哪、副标题有没有，
在它眼里全都一样。所以它不是这条漏洞的补丁，两者互不替代。

**这个闸怎么工作**

规范里给需要对账的小节打一条标记：

    <!-- spec-sync: id=2.4 rev=2026-08-22 -->

消费方（实现文件、测试、原型源码）在自己文件里声明它对齐到哪一版：

    spec-sync: 2.4 rev=2026-08-22 sha=1a2b3c4d

`sha` 是规范那一小节**正文**的哈希前 8 位。于是两种漂移都会红：

1. 有人改了规范正文但没动消费方  → 正文哈希变了，消费方声明的 sha 对不上 → 红
2. 有人改了规范正文却没 bump rev  → **同样红**，因为判据是哈希不是 rev 字符串

第 2 条是这个闸和「版本号戳」方案的分水岭：单靠 rev 字符串，忘记 bump 就等于没闸
（同族教训见 [[reference_every_gate_branch_must_execute_once]]：闸的每条分支都要
被执行过一次）。哈希不需要人记得。

**边界**

- 它证明的是「消费方**看过**当前这一版规范」，不是「消费方**做对了**」。
  做没做对由各自的测试守（`ModulePlate.test.tsx` 守页头形状，
  `useBoardCoordinates.test.ts` 守 §3.2 的坐标默认档，`loadbearing_*.js` 守布局结论）。
  这两层不互相替代。
- 它只看源码文本。所以要对齐的值必须是**字面量**，不能是变量或 env
  （同族：[[reference_gate_lives_where_operands_are]]）。

用法：
    python3 superpowers/tracks/galaxy-ui-redesign/check_spec_sync.py          # 对账
    python3 superpowers/tracks/galaxy-ui-redesign/check_spec_sync.py --update # 把 sha 写回消费方
退出码 0 = 一致；1 = 有漂移。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MANIFEST = HERE / "spec-sync.json"

SPEC_MARKER = re.compile(r"<!--\s*spec-sync:\s*id=(?P<id>[\w.]+)\s+rev=(?P<rev>[\w-]+)\s*-->")
CONSUMER_MARKER_TMPL = r"spec-sync:\s*{sid}\s+rev=(?P<rev>[\w-]+)\s+sha=(?P<sha>[0-9a-f]{{8}})"
HEADING = re.compile(r"^#{2,4}\s")


def section_body(lines: list[str], marker_index: int) -> str:
    """标记那一行之后、到下一个同级或更高级标题之前的正文。

    正文里**不含**标记行本身 —— 否则 bump rev 就会改变哈希，
    「改了正文没 bump」与「bump 了没改正文」两种情况就分不开了。
    """
    body: list[str] = []
    for line in lines[marker_index + 1 :]:
        if HEADING.match(line):
            break
        body.append(line.rstrip())
    # 去掉首尾空行，避免无意义的空白差异
    while body and not body[0]:
        body.pop(0)
    while body and not body[-1]:
        body.pop()
    return "\n".join(body)


def spec_sections(spec_path: Path) -> dict[str, dict]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    out: dict[str, dict] = {}
    for i, line in enumerate(lines):
        m = SPEC_MARKER.search(line)
        if not m:
            continue
        body = section_body(lines, i)
        out[m.group("id")] = {
            "rev": m.group("rev"),
            "sha": hashlib.sha256(body.encode("utf-8")).hexdigest()[:8],
            "line": i + 1,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="把当前 sha 写回消费方（人看过之后才用）")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    spec_path = REPO / manifest["spec"]
    if not spec_path.exists():
        print(f"FAIL 规范文件不在: {spec_path}")
        return 1

    sections = spec_sections(spec_path)
    problems: list[str] = []
    checked = 0

    for sid, consumers in manifest["sections"].items():
        if sid not in sections:
            problems.append(f"规范里找不到 §{sid} 的 spec-sync 标记 —— 标记被删了，闸就哑了")
            continue
        want = sections[sid]
        if not consumers:
            problems.append(f"§{sid} 一个消费方都没登记 —— 空清单会静默报绿")
            continue
        for rel in consumers:
            path = REPO / rel
            if not path.exists():
                problems.append(f"§{sid} 的消费方不在: {rel}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            m = re.search(CONSUMER_MARKER_TMPL.format(sid=re.escape(sid)), text)
            if not m:
                problems.append(
                    f"§{sid} 的消费方 {rel} 没有 spec-sync 声明"
                    f"（该写：spec-sync: {sid} rev={want['rev']} sha={want['sha']}）"
                )
                continue
            checked += 1
            if m.group("sha") != want["sha"]:
                if args.update:
                    new = text[: m.start()] + f"spec-sync: {sid} rev={want['rev']} sha={want['sha']}" + text[m.end() :]
                    path.write_text(new, encoding="utf-8")
                    print(f"  updated {rel}: {m.group('sha')} → {want['sha']}")
                else:
                    problems.append(
                        f"§{sid} 正文已变（现 sha={want['sha']}），但 {rel} 还声明着 "
                        f"sha={m.group('sha')} rev={m.group('rev')} —— 这一处没跟上规范"
                    )
            elif m.group("rev") != want["rev"]:
                problems.append(
                    f"§{sid} 的 rev 是 {want['rev']}，{rel} 写的是 {m.group('rev')} —— "
                    f"正文没变但版本标签对不上，两边有一个写错了"
                )

    if args.update:
        print("已把当前 sha 写回消费方。**这一步不代表看过** —— 请自己确认每个消费方确实跟上了新条款。")
        return 0

    if problems:
        print(f"spec-sync FAIL —— {len(problems)} 处漂移：")
        for p in problems:
            print("  - " + p)
        print()
        print("确认每个消费方都按新条款改好之后，再跑 --update 把 sha 写回。")
        return 1

    print(f"spec-sync OK —— {len(sections)} 个条款、{checked} 处消费方声明全部对齐。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
