"""`src/kiosk-shell/` 是从 smartbox 共享外壳**整目录抄来的副本**,`MANIFEST.sha256` 逐文件钉着它。

## 这条闸补的是一个**没人在跑**的检查

那份清单一直只写在 `README.md` 和计划文档里,**没有任何自动化执行它** ——
于是它按预期漂了:`472436f5` 改 `tokens.css` 时连着重算了清单(对的做法),
下一次 `3f3798c6` 又改了它(`.kiosk-pagebar__iconbtn--labeled` 那一组)**却没重算**。
从那以后 `shasum -c` 一直是 293/294,而没有任何一次构建、测试或 CI 会说出来。
(2026-09-21 发现时,漂已经躺了一段时间。)

## 它答得了什么、答不了什么

`assets/` 和它的清单是**一起抄进来**的,所以这条闸只证明
**「我这份副本自己没被人不声不响地改过」**。
上游换了图、上游清单跟着重算,我这边两个都还是旧的、还互相自洽 —— 闸照样绿。
要答「我这份还等于上游那份吗」,得把**上游清单文件本身的 sha256** 也钉一次,
那一条还没做(见 `src/kiosk-shell/README.md`)。

故意**不**断言总行数:加图标、加字体分块都是正当的增量,钉死行数会让每次正当新增
都先红一次 —— 那种闸报一次就会长出白名单。这里只管「清单里写着的每一行,
文件还在、字节还对」,外加「清单本身别缩水到不像话」。
"""

import hashlib
from pathlib import Path

import pytest

SHELL = Path(__file__).resolve().parents[1] / "katrain" / "web" / "ui" / "src" / "kiosk-shell"
MANIFEST = SHELL / "MANIFEST.sha256"


def _entries() -> list[tuple[str, str]]:
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        rows.append((digest.strip(), name.strip()))
    return rows


def test_the_gate_can_read_its_operands():
    """取不到清单就是闸瞎了,不是副本对了。"""
    assert MANIFEST.exists(), f"{MANIFEST} 不在了 —— 副本的钉子没了,这条闸要跟着改,不是删掉"
    rows = _entries()
    assert len(rows) >= 200, f"清单只剩 {len(rows)} 行 —— 200 行都不到,说明它被截了,不是正当瘦身"
    assert any(n == "tokens.css" for _, n in rows), "清单里没有 tokens.css —— 那是这份副本的主体"


@pytest.mark.parametrize("digest,name", _entries(), ids=[n for _, n in _entries()])
def test_every_shell_file_matches_its_recorded_hash(digest, name):
    path = SHELL / name
    assert path.is_file(), (
        f"清单里写着 {name},但文件不在。抄进来的副本少了一块,"
        f"引它的地方会静默失效(CSS 的 url()/mask 求空不报错)。"
    )
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == digest, (
        f"{name} 的字节和清单对不上。\n"
        f"  清单:{digest}\n  实际:{actual}\n"
        f"改 `src/kiosk-shell/` 里的文件是允许的(`472436f5` 就那么做的),"
        f"但**必须连着重算清单**:\n"
        f"  cd katrain/web/ui/src/kiosk-shell && shasum -a 256 {name}\n"
        f"把那一行替换进 MANIFEST.sha256。漏了这一步,副本会一直漂到没人记得它动过。"
    )
