"""grade:* 文案必须 11 个语言齐全。

这一族键有个 grep 抓不到的坑：TrendChart.tsx 里阶段与棋手筛选的键是
模板字符串拼出来的（``t(`grade:phase_${p}`)`` / ``t(`grade:player_${c}`)``），
扫源码的闸看不见它们。所以这里从 **yaml 的档位表 + 一份显式清单** 取键，
不从 TSX 里 grep。
"""

import os
import re

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
    # AI 一致率 tab（TrendChart 第 5 个 tab）。这张表是硬编码的：新加的 key 不写进来，
    # 十一语缺翻这条闸对它就是永远绿的。
    "grade:match_rate",
    "grade:match_top1",
    "grade:match_top3",
    "grade:match_offbook",
    "grade:match_no_data",
    "grade:match_footer",
    "grade:match_undecidable",
    "grade:match_caveat",
    # 五个分析 tab 的改版（2026-09-01）。
    "grade:filter_phase",
    "grade:filter_player",
    "grade:filter_match_view",
    "grade:view_stats",
    "grade:view_distribution",
    "grade:axis_move_number",
    "grade:axis_brilliance",
    "grade:axis_points_lost",
    "grade:axis_aria",
    "grade:count_note",
    "grade:histogram_unrated",
    "grade:histogram_aria",
    "grade:def_brilliant",
    "grade:def_best",
    "grade:def_points_lt",
    "grade:def_blunder",
    "grade:def_unrated",
    "grade:brilliance_entry",
    "grade:match_timeline_legend",
    "grade:match_timeline_aria",
    "grade:match_longest_run",
    # 人类倾向列（AiAnalysis）。这四条也只有这一个闸在守。
    # 2026-09-01 那一列按 Fan 的裁定撤下了（`showHumanTendency` 不再传），但键留着 ——
    # 组件里那条分支还在、还有单测，撤掉翻译等于把它变成半死的代码。
    "live:human_pick_rate",
    "live:human_pick_rate_ranked",
    "live:human_pick_rate_hint",
    "live:human_pick_rate_hint_ranked",
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


# ── 这条闸补的是上面那份硬编码清单的洞 ────────────────────────────────────────

SCANNED_SOURCES = [
    "katrain/web/ui/src/components/live/TrendChart.tsx",
    "katrain/web/ui/src/components/live/AiAnalysis.tsx",
]

# 模板字符串拼出来的前缀：``t(`grade:phase_${p}`)`` 这种，扫源码只看得见前缀。
# 它们的完整键在 DYNAMIC_KEYS 里逐条列着，所以这里按前缀放行。
DYNAMIC_PREFIXES = ("grade:phase_", "grade:player_")


def test_no_grade_key_in_the_source_escapes_the_gate():
    """源码里出现的 grade:* / live:human_* 键必须全部在 ALL_KEYS 里。

    上面 STATIC_KEYS 是一份**硬编码清单**，它自己的注释就承认：新加的键不写进来，
    「十一语缺翻」那条闸对它永远是绿的 —— 也就是说那条闸守的是「有人记得登记」，
    不是「所有键都翻了」。这条把判据换成源码本身：漏登记会在这里红，
    不必等到某个语言的用户看见英文。

    为什么不干脆用扫描结果替掉 STATIC_KEYS：扫描看不见模板字符串拼出来的键
    （DYNAMIC_KEYS 那七条），两者互补，谁也替代不了谁。

    变异验证：把 STATIC_KEYS 里任意一条新键删掉，本用例红（实测删
    "grade:view_stats" 会红）；把 TrendChart 里某个 t('grade:xxx') 改成一个
    没登记的键名，同样红。
    """
    key_re = re.compile(r"""['"](grade:[a-z_0-9]+|live:human_[a-z_0-9]+)['"]""")
    known = set(ALL_KEYS)
    unregistered = {}
    for rel in SCANNED_SOURCES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            pytest.fail(f"扫描目标不存在：{rel}。文件挪了位置就要同步改 SCANNED_SOURCES，"
                        f"否则这条闸会静默地什么都不扫。")
        found = set(key_re.findall(open(path, encoding="utf-8").read()))
        missing = {k for k in found if k not in known and not k.startswith(DYNAMIC_PREFIXES)}
        if missing:
            unregistered[rel] = sorted(missing)
    assert not unregistered, f"这些键出现在源码里但没登记进 ALL_KEYS，十一语缺翻不会被发现：{unregistered}"
