"""grade:* 文案必须 11 个语言齐全。

这一族键有个 grep 抓不到的坑：TrendChart.tsx 里阶段与棋手筛选的键是
模板字符串拼出来的（``t(`grade:phase_${p}`)`` / ``t(`grade:player_${c}`)``），
扫源码的闸看不见它们。所以这里从 **yaml 的档位表 + 一份显式清单** 取键，
不从 TSX 里 grep。
"""

import os

import polib
import pytest

from katrain.core.move_grade import tiers

LOCALES = ["en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua"]

# 模板字符串拼出来的键，grep 不到，只能显式列。
# 改 TrendChart 里的 phase/player 键名时必须同步改这里。
DYNAMIC_KEYS = [
    "grade:phase_all",
    "grade:phase_opening",
    "grade:phase_midgame",
    "grade:phase_endgame",
    "grade:player_both",
    "grade:player_B",
    "grade:player_W",
]

STATIC_KEYS = [
    "grade:performance",
    "grade:brilliance",
    "grade:unrated",
    "grade:no_rated_moves",
    "grade:truncated_note",
    "grade:histogram_footer",
    "grade:unrated_count",
]

ALL_KEYS = [t["i18n"] for t in tiers()] + DYNAMIC_KEYS + STATIC_KEYS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _catalog(lang):
    path = os.path.join(ROOT, "katrain", "i18n", "locales", lang, "LC_MESSAGES", "katrain.po")
    return {e.msgid: e.msgstr for e in polib.pofile(path)}


@pytest.mark.parametrize("lang", LOCALES)
def test_every_grade_key_is_translated(lang):
    cat = _catalog(lang)
    missing = [k for k in ALL_KEYS if not cat.get(k, "").strip()]
    assert not missing, f"{lang} is missing {len(missing)} grade keys: {missing}"


@pytest.mark.parametrize("lang", [l for l in LOCALES if l != "en"])
def test_grade_keys_are_not_left_in_english(lang):
    """漏翻时 i18n.py 会拿英文顶上，看起来「有值」但其实没翻。

    判据只能落在**整句**上：单词级的档位名在多种语言里会合法地与英文同形
    （法语的 "Performance" 就是），拿它当判据会误报。误报一次就会长出白名单，
    所以这里换掉判据对象，而不是给 fr 开例外。

    变异记录：把 fr 的 grade:truncated_note 改成英文原句，本用例会红（实测）。
    """
    en = _catalog("en")
    cat = _catalog(lang)
    for key in ("grade:no_rated_moves", "grade:truncated_note", "grade:histogram_footer"):
        assert cat[key] != en[key], f"{lang}:{key} is still the English string"


def test_tier_i18n_keys_come_from_the_yaml():
    """档位键名必须与 yaml 一致 —— 生成的 TS 用的就是这些键。"""
    assert [t["i18n"] for t in tiers()] == [
        "grade:brilliant",
        "grade:best",
        "grade:very_good",
        "grade:playable",
        "grade:inaccuracy",
        "grade:mistake",
        "grade:blunder",
    ]


# --------------------------------------------------------------------------- 批量脚本

def _batch_translations():
    import importlib.util

    path = os.path.join(ROOT, "scripts", "batch_translate_galaxy.py")
    spec = importlib.util.spec_from_file_location("batch_translate_galaxy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.GALAXY_TRANSLATIONS


def test_batch_script_has_no_duplicate_keys():
    """dict 字面量里重复的 msgid 会被 Python 静默丢掉，只留最后一个。

    仓里真的发生过：'Advice' 出现两次，后一个写着「建议」，
    于是任何人跑一次这个脚本，界面上的「支招」就被悄悄改成「建议」。
    dict 本身看不出重复，只能扫源码文本。

    变异记录：在脚本里再粘一个 "grade:best" 块，本用例会红（实测）。
    """
    import collections
    import re

    path = os.path.join(ROOT, "scripts", "batch_translate_galaxy.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    keys = re.findall(r'^    "((?:[^"\\]|\\.)*)": \{$', src, re.M)
    dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
    assert not dupes, f"duplicate msgids silently dropped by Python: {dupes}"


@pytest.mark.parametrize("lang", LOCALES)
def test_batch_script_agrees_with_the_po_files(lang):
    """脚本必须是幂等的：跑它不应该改动任何已有译文。

    不幂等时它会把别人后来直接改进 .po 的译文悄悄回滚 —— 而且只在有人
    碰巧跑一次脚本时发生，git diff 里看起来像是无关改动。
    """
    cat = _catalog(lang)
    drift = {
        msgid: (cat.get(msgid), langs[lang])
        for msgid, langs in _batch_translations().items()
        if lang in langs and msgid in cat and cat[msgid] != langs[lang]
    }
    assert not drift, (
        f"{lang}: running scripts/batch_translate_galaxy.py would silently change "
        f"{len(drift)} existing translations: {list(drift)[:5]}"
    )
