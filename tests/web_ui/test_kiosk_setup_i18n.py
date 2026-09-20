"""开局设置三屏(自由 / 升降级 / 本地)的每一个界面字符串,11 个语种都要有真译文。

## 这条闸为什么只圈这三屏

`t(key, '中文默认')` 这个写法在 kiosk 里是**普遍**的:整个 `src/kiosk` 有 1174 个 key,
其中 959 个在 `en.po` 里根本不存在 —— 也就是说,用户在设置里把语言切成韩文,
屏上绝大多数字仍然是中文(`i18n.t()` 查不到就回退到第二个参数,而第二个参数是中文)。

那 959 个不是这一轮造的,也不是这一轮能还的。**闸圈在这一轮真的补完的那一块上**:
三屏 + 它们共用的那套件。圈大了它今天就报 800 多条,报一次就会长出白名单,
从此谁也不看它 —— 那样还不如没有。剩下的欠账记在
`superpowers/tracks/kiosk-go-play-ai/r2-setup-acceptance.md` §7。

## 判据为什么是「非空 **且** 没有 TODO」

`i18n.py` 对某个语种缺的条目会**拿英文原文顶上去**,并在注释里打一个 `TODO`
(`i18n.py:76/78`)。只断言 msgstr 非空的话,一条被英文顶上的韩文条目照样是绿的 ——
那正是这条闸要挡的东西:看起来有值,其实没翻。
"""

import re
from pathlib import Path

import polib
import pytest

REPO = Path(__file__).resolve().parents[2]
UI = REPO / "katrain" / "web" / "ui" / "src" / "kiosk"

# 本轮重画的三屏 + 它们共用的那套件。**只有这些**,见上面的 docstring。
SOURCES = [
    UI / "utils" / "setupOptions.ts",
    UI / "pages" / "AiSetupPage.tsx",
    UI / "pages" / "PvpLocalSetupPage.tsx",
    *sorted((UI / "components" / "setup").glob("*.ts*")),
]

LANGS = ["en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"]

# `t('key', '默认')` —— 只认两个参数都是单引号字面量的那种调用。
_CALL = re.compile(r"\bt\(\s*'([^']+)'\s*,\s*'([^']*)'\s*\)")


def _strip_comments(src: str) -> str:
    """注释里提到的 key 不是界面字符串。

    本文件的 docstring 和被测源码里都写了 `t('setup:...', '...')` 这样的例子,
    不去掉注释的话闸会把它们当成真的调用 —— 误报一次就会长出白名单。
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _keys() -> list[str]:
    out: set[str] = set()
    for path in SOURCES:
        out |= {k for k, _ in _CALL.findall(_strip_comments(path.read_text(encoding="utf-8")))}
    return sorted(out)


def test_the_gate_can_read_its_operands():
    """取不到 key 就是闸瞎了,不是被测的东西对了。

    三屏加上共用件,`t()` 调用是**几十条**级别。读出个位数一定是正则和源码对不上
    (例如有人把 `t('x', 'y')` 换成了别的写法),那时候这条闸会假绿。
    """
    for path in SOURCES:
        assert path.exists(), f"{path} 不在了 —— 文件挪了地方,这条闸要跟着改,不是删掉"
    keys = _keys()
    assert len(keys) >= 100, f"只读出 {len(keys)} 个 key,正则和源码对不上了"
    # 三屏各自的命名空间都要出现,少一个说明漏掉了整整一屏
    for ns in ("setup:", "ladder:", "local:"):
        assert any(k.startswith(ns) for k in keys), f"一个 {ns} 的 key 都没读到"


@pytest.mark.parametrize("lang", LANGS)
def test_every_setup_string_is_really_translated(lang):
    catalog = {e.msgid: e for e in polib.pofile(str(REPO / "katrain" / "i18n" / "locales" / lang / "LC_MESSAGES" / "katrain.po"))}
    missing, untranslated = [], []
    for key in _keys():
        entry = catalog.get(key)
        if entry is None or not entry.msgstr.strip():
            missing.append(key)
        elif "TODO" in (entry.comment or ""):
            untranslated.append(key)
    assert not missing, (
        f"{lang}.po 里没有这些开局设置的 key:{missing}\n"
        f"屏上会回退到 `t()` 的第二个参数 —— 那是**中文**,所以 {lang} 用户看到的是中文。\n"
        f"补法:把它们加进 `scripts/batch_translate_galaxy.py` 的 GALAXY_TRANSLATIONS,"
        f"跑一遍那个脚本,再跑 `python i18n.py`。"
    )
    assert not untranslated, (
        f"{lang}.po 里这些条目带着 TODO 标记:{untranslated}\n"
        f"那是 `i18n.py` 拿英文原文顶上去的占位(i18n.py:76/78),不是译文。"
    )
