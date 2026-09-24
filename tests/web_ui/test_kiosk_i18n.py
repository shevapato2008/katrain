"""**整个 kiosk** 的每一个界面字符串,11 个语种都要有真译文。

## 这条闸在守什么

`t(key, '中文默认')` 查不到就回退到第二个参数 —— 而第二个参数**是中文**。
所以一个没进 `.po` 的 key,在韩文界面上**不会报错、不会显示 msgid**,
它会安静地显示中文。屏上每个字都在,只是语言不对 ——
读代码看不出来,跑单测也看不出来(jsdom 里翻译表没加载,`t()` 恒返回默认值)。

2026-09-21 第一次量:`src/kiosk` 1174 个 key,其中 **959 个**在 `en.po` 里根本不存在。
先补掉开局设置三屏的 96 个,闸只圈那三屏;同日把剩下的 872 个也补完,
闸随之放宽到**全树**。

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

def _sources() -> list[Path]:
    """`src/kiosk` 下的全部源码,**排除测试**。

    测试文件里也有 `t('x','中文')` 形状的字面量(断言用的期望值),
    它们不上屏,不该要求进 `.po`。
    """
    return sorted(
        p for p in UI.rglob("*")
        if p.suffix in (".ts", ".tsx") and "__tests__" not in p.parts and ".test." not in p.name
    )

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
    """上屏的 key。

    **判据和 `kiosk-shell-contract.spec.ts` 闸四同一条**:默认值是中文的一定算;
    默认值不是中文时,只有 key 本身像 msgid(大写开头,或带命名空间冒号)才算 ——
    这样排除掉 `foo('a','b')` 这种碰巧同形的普通两参调用。
    """
    out: set[str] = set()
    for path in _sources():
        for key, default in _CALL.findall(_strip_comments(path.read_text(encoding="utf-8"))):
            if re.search(r"[\u4e00-\u9fff]", default) or key[:1].isupper() or ":" in key:
                out.add(key)
    return sorted(out)


def test_the_gate_can_read_its_operands():
    """取不到 key 就是闸瞎了,不是被测的东西对了。

    三屏加上共用件,`t()` 调用是**几十条**级别。读出个位数一定是正则和源码对不上
    (例如有人把 `t('x', 'y')` 换成了别的写法),那时候这条闸会假绿。
    """
    assert UI.is_dir(), f"{UI} 不在了 —— 目录挪了地方,这条闸要跟着改,不是删掉"
    assert len(_sources()) >= 100, f"只扫到 {len(_sources())} 个源码文件,路径对不上了"
    keys = _keys()
    assert len(keys) >= 900, f"只读出 {len(keys)} 个 key,正则和源码对不上了"
    # 每一屏都要有代表,少一族说明漏掉了整块
    for ns in ("setup:", "ladder:", "local:", "game:", "tsumego:", "kifu:", "review:", "platform:"):
        assert any(k.startswith(ns) for k in keys), f"一个 {ns} 的 key 都没读到"


@pytest.mark.parametrize("lang", LANGS)
def test_every_kiosk_string_is_really_translated(lang):
    catalog = {e.msgid: e for e in polib.pofile(str(REPO / "katrain" / "i18n" / "locales" / lang / "LC_MESSAGES" / "katrain.po"))}
    missing, untranslated = [], []
    for key in _keys():
        entry = catalog.get(key)
        if entry is None or not entry.msgstr.strip():
            missing.append(key)
        elif "TODO" in (entry.comment or ""):
            untranslated.append(key)
    assert not missing, (
        f"{lang}.po 里没有这些 kiosk 的 key(共 {len(missing)} 个,先列 20 个):{missing[:20]}\n"
        f"屏上会回退到 `t()` 的第二个参数 —— 那是**中文**,所以 {lang} 用户看到的是中文。\n"
        f"补法:把它们加进 `scripts/batch_translate_galaxy.py` 的 GALAXY_TRANSLATIONS,"
        f"跑一遍那个脚本,再跑 `python i18n.py`。"
    )
    assert not untranslated, (
        f"{lang}.po 里这些条目带着 TODO 标记:{untranslated}\n"
        f"那是 `i18n.py` 拿英文原文顶上去的占位(i18n.py:76/78),不是译文。"
    )


@pytest.mark.parametrize("lang", LANGS)
def test_login_facts_keys_are_translated(lang):
    """`platformLoginFacts.ts` 里的 key 是**变量**传给 `t()` 的(`t(f.titleKey, f.titleZh)`),
    上面那条通用闸的正则(只认两个单引号字面量)看不见这几条调用。

    看不见 ⇒ 少翻一条不会红 ⇒ 韩文界面上那一段安静地显示中文。
    所以这张表要单独点名。表变了这条会红,那是对的:提醒把新 key 也补进 .po。
    """
    src = (UI / "constants" / "platformLoginFacts.ts").read_text(encoding="utf-8")
    keys = sorted(set(re.findall(r"Key:\s*'([^']+)'", src)))
    assert len(keys) == 12, f"只扫到 {len(keys)} 个 key,正则和表对不上了(golaxy 3+3,ogs 4+4,whose/stored 两家共用 ⇒ 应为 12)"
    po = polib.pofile(str(REPO / "katrain" / "i18n" / "locales" / lang / "LC_MESSAGES" / "katrain.po"))
    have = {e.msgid: e for e in po}
    for k in keys:
        assert k in have, f"{lang}.po 缺 {k}"
        e = have[k]
        assert e.msgstr.strip(), f"{lang}.po 的 {k} 是空的"
        assert "TODO" not in (e.comment or ""), f"{lang}.po 的 {k} 被英文顶上了(TODO)"
