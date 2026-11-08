"""Canonical native Go UI messages survive PO -> MO without Chinese fallback.

Follow KioskApp's real local import closure, including shared feature widgets; the
small kifu fallback stays an explicit existing exception, not a second catalog.
"""

import ast
import gettext
import io
import json
import re
from pathlib import Path

import polib
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "katrain/web/ui/src"
LOCALES = ("cn", "tw", "en", "jp", "ko")
STRING = r"""(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")"""
CALL = re.compile(
    r"\b(?:(?:t|kioskText|uiMessage)\(\s*|uiError\([^,\n]*,\s*)("
    + STRING
    + r")\s*(?:,\s*((?:"
    + STRING
    + r"\s*\+\s*)*"
    + STRING
    + r"))?"
)
IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)['"](\.[^'"]+)['"]""")
HAN = re.compile(r"[\u3400-\u9fff]")


def _sources():
    todo = [SRC / "kiosk/KioskApp.tsx"]
    found = set()
    while todo:
        path = todo.pop()
        if path in found:
            continue
        found.add(path)
        for relative in IMPORT.findall(path.read_text()):
            base = path.parent / relative
            candidates = [
                base,
                *(Path(str(base) + ext) for ext in (".ts", ".tsx")),
                base / "index.ts",
                base / "index.tsx",
            ]
            target = next((p.resolve() for p in candidates if p.is_file()), None)
            if target and target.suffix in (".ts", ".tsx") and target.is_relative_to(SRC):
                todo.append(target)
    return sorted(found)


def _unquote(value):
    return ast.literal_eval(value)


def _calls():
    calls = {}
    for path in _sources():
        # Standalone comments contain examples which are not rendered messages.
        source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        source = re.sub(r"(?m)^\s*//.*$", "", source)
        for match in CALL.finditer(source):
            key = _unquote(match[1])
            default = "".join(_unquote(s) for s in re.findall(STRING, match[2])) if match[2] else None
            calls.setdefault(key, default)
    return calls


def _catalog(locale):
    return polib.pofile(str(ROOT / f"katrain/i18n/locales/{locale}/LC_MESSAGES/katrain.po"))


def test_inventory_follows_native_route_imports():
    paths = {str(p.relative_to(SRC)) for p in _sources()}
    assert len(paths) > 200
    assert "features/aiLadder/blockingCopy.ts" in paths
    assert "kiosk/components/vision/GeometryCalibrationScreen.tsx" in paths
    assert "kiosk/pages/PlatformLobbyPage.tsx" in paths
    assert len(_calls()) > 1600


@pytest.mark.parametrize("locale", LOCALES)
def test_actual_native_literal_messages_have_reviewed_catalog_entries(locale):
    local_kifu = json.loads((SRC / "kiosk/appearance/kifuMessages.json").read_text())
    catalog = {e.msgid: e for e in _catalog(locale)}
    missing = []
    untranslated = []
    for key in _calls():
        entry = catalog.get(key)
        if entry is None or not entry.msgstr.strip():
            if not local_kifu.get(key, {}).get(locale):
                missing.append(key)
        elif entry.obsolete or "fuzzy" in entry.flags or "TODO" in entry.comment:
            untranslated.append(key)
    assert not missing, f"{locale}: missing actual native UI messages: {missing}"
    assert not untranslated, f"{locale}: messages excluded from real MO or still placeholders: {untranslated}"


EXPECTED = {
    "cn": ("画面过亮，暂时无法可靠识别", "确认落子", "概览", "已连接 · 进入平台专页"),
    "tw": ("畫面過亮，暫時無法可靠辨識", "確認落子", "概覽", "已連線 · 進入平台專頁"),
    "en": ("Image too bright for reliable recognition", "Confirm move", "Overview", "Connected · Open platform"),
    "jp": ("明るすぎて正確に認識できません", "着手を確定", "概要", "接続済み · プラットフォームへ"),
    "ko": ("화면이 너무 밝아 정확히 인식할 수 없습니다", "착수 확인", "개요", "연결됨 · 플랫폼 열기"),
}
CONTEXT_EXPECTED = {
    "cn": ("你是{rank}，配到{rung} —— {reason}。", "第 {n} 档", "{color}领先 {points} 目", "{color}胜率 {percentage}"),
    "tw": ("你是{rank}，配到{rung} —— {reason}。", "第 {n} 階", "{color}領先 {points} 目", "{color}勝率 {percentage}"),
    "en": (
        "You are {rank}, matched to {rung} — {reason}",
        "level {n}",
        "{color} leads {points} pts",
        "{color} win rate {percentage}",
    ),
    "jp": (
        "{rank}、対戦相手は{rung} — {reason}。",
        "第{n}段階",
        "{color}が{points}目リード",
        "{color}の勝率 {percentage}",
    ),
    "ko": (
        "내 급단위는 {rank}, 상대는 {rung}입니다 — {reason}",
        "{n}단계",
        "{color} {points}집 우세",
        "{color} 승률 {percentage}",
    ),
}
CONTEXT_KEYS = (
    "ladder:matched_rung_summary",
    "ladder:rung_number",
    "report:color_leads_points",
    "report:color_winrate",
)

REPRESENTATIVE = (
    "vision:lighting_overexposed_title",
    "game:local_confirm_move",
    "growth:tab_overview",
    "platform:connected_enter",
)


@pytest.mark.parametrize("locale", LOCALES)
def test_reviewed_camera_button_growth_platform_messages_reach_compiled_runtime(locale):
    runtime = gettext.GNUTranslations(io.BytesIO(_catalog(locale).to_binary()))
    for key, expected in zip(REPRESENTATIVE, EXPECTED[locale]):
        assert runtime.gettext(key) == expected
    for key, expected in zip(CONTEXT_KEYS, CONTEXT_EXPECTED[locale]):
        assert runtime.gettext(key) == expected
    for key in (
        "ladder:sync_waiting",
        "game:territory_black_lead",
        "growth:cal_grid_aria",
        "report:library_game_accessible",
    ):
        default = _calls()[key]
        translated = runtime.gettext(key)
        assert translated != key
        assert set(re.findall(r"\{[^{}]+\}", translated)) == set(re.findall(r"\{[^{}]+\}", default))
        if locale in ("en", "ko"):
            assert not HAN.search(translated), (locale, key, translated)


def _dynamic_keys():
    """Read descriptors and the finite template tables used by native widgets."""
    keys = set()
    for path in _sources():
        source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        source = re.sub(r"(?m)^\s*//.*$", "", source)
        keys.update(
            re.findall(
                r"""['"]((?:vision|rank|platform|grade|tutorial|game|auth|settings|tsumego):[^'"${}]+)['"]""", source
            )
        )
        if path.name == "accessPolicy.ts":
            keys.update(
                _unquote(value)
                for value in re.findall(r"\b(?:label|description|backLabel):\s*(" + STRING + r")", source)
            )
        elif path.name == "nativePresentation.ts":
            # Only this bounded presenter owns these fixed backend enum/reason tables.
            keys.update(value for value in map(_unquote, re.findall(STRING, source)) if HAN.search(value))
        elif path.name == "settlement.ts":
            messages = source.split("const notCountedMessages", 1)[1].split("export const useAiLadderSettlement", 1)[0]
            keys.update(value for value in map(_unquote, re.findall(STRING, messages)) if HAN.search(value))
        elif path.name == "platformErrorMessage.ts":
            reasons = source.split("const KNOWN_PLATFORM_ERRORS", 1)[1].split("]);", 1)[0]
            keys.update(map(_unquote, re.findall(STRING, reasons)))
        elif path.name == "playerRank.ts":
            names = source.split("const GOLAXY_AI_NAMES", 1)[1].split("]);", 1)[0]
            keys.update(map(_unquote, re.findall(STRING, names)))
        elif path.name == "ledColors.ts":
            labels = source.split("export const LED_LABEL", 1)[1]
            keys.update(_unquote(value) for value in re.findall(STRING, labels))
        elif path.name == "PhysicalStatePanel.tsx":
            keys.update(_unquote(value) for value in re.findall(r"titleZh:\s*(" + STRING + r")", source))
        elif path.name == "VisionSyncOverlay.tsx":
            keys.update(_unquote(value) for value in re.findall(r"message:\s*(" + STRING + r")", source))
        elif path.name == "GolaxySpectatorPage.tsx":
            validator = source.split("function snapshotError", 1)[1].split("\n}", 1)[0]
            keys.update(value for value in map(_unquote, re.findall(STRING, validator)) if HAN.search(value))
            keys.update(_unquote(value) for value in re.findall(r"message:\s*(" + STRING + r")", source))
        elif path.name == "PvpSpectatorPage.tsx":
            errors = source.split("const message =", 1)[1].split("throw new Error(message)", 1)[0]
            keys.update(value for value in map(_unquote, re.findall(STRING, errors)) if HAN.search(value))
            keys.update(
                _unquote(value) for value in re.findall(r"(?:error:\s*|throw new Error\()(" + STRING + r")", source)
            )
        elif path.name == "tsumegoUnits.ts":
            categories = source.split("export const CATEGORY_META", 1)[1].split("};", 1)[0]
            keys.update(f"tsumego:{category}" for category in re.findall(r"^  (\w+):", categories, flags=re.M))
        elif path.name == "TutorialCategoriesPage.tsx":
            assert "tutorial:layer_${key}_lead" in source
            for row in re.findall(r"\['(book|chapter|section|figure)'", source):
                keys.update(f"tutorial:layer_{row}_{part}" for part in ("lead", "t", "s"))
        elif path.name in ("MoveGradePanel.tsx", "DiagnosisPanel.tsx"):
            keys.update(f"grade:phase_{phase}" for phase in ("all", "opening", "midgame", "endgame"))
            if path.name == "MoveGradePanel.tsx":
                keys.update(f"grade:player_{side}" for side in ("both", "B", "W"))
        elif path.name == "BaipuSessionPage.tsx":
            assert "game:${side}_wins_${ending}" in source
            keys.update(f"game:{side}_wins_{ending}" for side in ("black", "white") for ending in ("resign", "timeout"))
        elif path.name == "GolaxyPregameSetupPage.tsx":
            keys.update(
                f"platform:match_time_{choice}{suffix}"
                for choice in re.findall(r"\bid:\s*'([^']+)'", source)
                for suffix in ("", "_details")
            )
        elif path.name == "SettingsPage.tsx":
            groups = source.split("const GROUPS", 1)[1].split("];", 1)[0]
            keys.update(f"settings:nav_{group}" for group in re.findall(r"\bkey:\s*'([^']+)'", groups))
    return keys


@pytest.mark.parametrize("locale", LOCALES)
def test_dynamic_descriptor_messages_compile_with_the_same_parameters(locale):
    catalog = {e.msgid: e for e in _catalog(locale)}
    chinese = {e.msgid: e.msgstr for e in _catalog("cn")}
    runtime = gettext.GNUTranslations(io.BytesIO(_catalog(locale).to_binary()))
    calls = _calls()
    local_kifu = json.loads((SRC / "kiosk/appearance/kifuMessages.json").read_text())
    for key in sorted(set(calls) | _dynamic_keys()):
        if key not in catalog:
            # Existing kifu fallback is verified separately and is not a PO entry.
            assert local_kifu.get(key, {}).get(locale), (locale, key)
            continue
        entry = catalog[key]
        assert not entry.obsolete and "fuzzy" not in entry.flags and "TODO" not in entry.comment, (locale, key)
        value = runtime.gettext(key)
        assert value == entry.msgstr, (locale, key, value)
        expected_source = calls.get(key) or chinese[key]
        assert sorted(re.findall(r"\{[^{}]+\}", value)) == sorted(re.findall(r"\{[^{}]+\}", expected_source)), (
            locale,
            key,
            expected_source,
            value,
        )
        if locale in ("en", "ko"):
            assert not HAN.search(value), (locale, key, value)
