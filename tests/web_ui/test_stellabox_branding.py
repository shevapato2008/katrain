import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_FILES = [
    ROOT / "katrain/web/ui/src/legal/terms.ts",
    ROOT / "katrain/web/ui/src/legal/privacy.ts",
    ROOT / "katrain/web/ui/src/galaxy/pages/Dashboard.tsx",
    ROOT / "katrain/web/ui/src/galaxy/components/auth/LoginModal.tsx",
    ROOT / "katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx",
]
BRAND_TRANSLATION_KEYS = ("dashboard:welcome", "auth:login_title")


def _translation(po_path: Path, msgid: str) -> str:
    text = po_path.read_text(encoding="utf-8")
    match = re.search(rf'^msgid "{re.escape(msgid)}"\nmsgstr "([^"]*)"$', text, re.MULTILINE)
    assert match, f"missing single-line translation for {msgid} in {po_path}"
    return match.group(1)


def test_product_facing_galaxy_defaults_and_legal_copy_use_stellabox_brand():
    for path in PRODUCT_FILES:
        text = path.read_text(encoding="utf-8")
        assert "弈航" not in text, path
        assert "BoardNavi" not in text, path
        assert "Galaxy Go" not in text, path

    terms = PRODUCT_FILES[0].read_text(encoding="utf-8")
    privacy = PRODUCT_FILES[1].read_text(encoding="utf-8")
    assert "智星盒用户服务协议" in terms
    assert "智星盒团队" in terms
    assert '"智星盒"（StellaBox）' in terms
    assert "智星盒隐私策略" in privacy
    assert "智星盒团队" in privacy
    assert '"智星盒"（StellaBox）' in privacy


def test_brand_specific_translations_use_chinese_brand_only_for_cn_and_tw():
    locale_root = ROOT / "katrain/i18n/locales"
    for po_path in sorted(locale_root.glob("*/LC_MESSAGES/katrain.po")):
        locale = po_path.parents[1].name
        expected_brand = "智星盒" if locale in {"cn", "tw"} else "StellaBox"
        for key in BRAND_TRANSLATION_KEYS:
            value = _translation(po_path, key)
            assert expected_brand in value, (locale, key, value)
            assert "Galaxy Go" not in value, (locale, key, value)


def test_stable_internal_and_attribution_names_are_outside_the_product_brand_contract():
    # KaTrain identifiers, API enums, database names, authors and third-party/license
    # attributions are deliberately excluded: this task only changes user-facing branding.
    assert all("package-lock.json" not in str(path) for path in PRODUCT_FILES)
    assert all("models_db.py" not in str(path) for path in PRODUCT_FILES)
