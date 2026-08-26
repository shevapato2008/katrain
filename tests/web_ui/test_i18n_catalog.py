"""The compiled gettext catalogs (`.mo`) are **not in the repo** -- `.gitignore` excludes
them and only `python i18n.py`, run by hand, produces them. Nothing in the build, the CI
config or the SBC deploy path invokes it.

That makes "no catalog on disk" a state every clean checkout starts in, so the two tests
here pin what happens in it. Both were red before 2026-08-26:

* without `fallback=True`, `gettext.translation` raises -- and since `katrain/core/lang.py`
  builds `i18n = Lang(DEFAULT_LANGUAGE)` at **module scope**, that is an import-time crash
  of the entire application, not a missing translation. (`katrain/vision/README.md:78`
  tells the reader to run `i18n.py` first "because core.baipu needs it" -- someone had
  already been bitten and wrote down the workaround instead of the fix.)
* `self.lang` was assigned *before* the load. `switch_lang` early-returns when the language
  is unchanged, so a load that raised left the object claiming a language whose catalog it
  never had -- and the next request for that language returned 200, with the *previous*
  language's table, and no error anywhere.

Both tests drive the real module-level `i18n` singleton and restore it afterwards: it is
process-wide state, and leaving it pointed at a temp directory poisons every later test in
the same worker.
"""

import os

import pytest

from katrain.core import lang as lang_mod


def _locales(tmp_path, langs=("en", "cn"), mo=None):
    # Both languages the tests can pick as a target, plus `en` because `switch_lang` always
    # asks for `[lang, DEFAULT_LANGUAGE]` -- if `en` were absent the lookup would differ.
    """A locales tree shaped like the repo's: `.po` present, `.mo` only if asked for."""
    pkg = tmp_path / "katrain" / "i18n"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    for lang in langs:
        d = pkg / "locales" / lang / "LC_MESSAGES"
        d.mkdir(parents=True)
        (d / "katrain.po").write_text('msgid ""\nmsgstr ""\n')
        if mo is not None:
            (d / "katrain.mo").write_bytes(mo)
    return str(pkg / "__init__.py")


@pytest.fixture
def restore_i18n():
    i18n = lang_mod.i18n
    saved = (i18n.lang, i18n.ugettext, i18n.font_name)
    yield i18n
    i18n.lang, i18n.ugettext, i18n.font_name = saved


def test_missing_catalog_degrades_instead_of_raising(tmp_path, monkeypatch, restore_i18n, capsys):
    """No `.mo` anywhere -> untranslated text, not an exception.

    Mutation check: drop `fallback=True` from `switch_lang` and this raises FileNotFoundError.
    """
    resource = _locales(tmp_path)
    monkeypatch.setattr(lang_mod, "find_package_resource", lambda _p: resource)
    # Same precondition as the test below, and for the same reason: `switch_lang`
    # early-returns on the current language, so hardcoding one makes this test pass alone
    # and go vacuous in the full suite (measured: it did, whichever test ran before had
    # already left the singleton in `cn`).
    target = "en" if restore_i18n.lang == "cn" else "cn"

    restore_i18n.switch_lang(target)

    # Untranslated -- and the msgid comes back, so the UI shows *something* rather than
    # a blank screen. The web layer reads the same attribute (`server.py` /api/translations).
    assert getattr(restore_i18n.ugettext.__self__, "_catalog", {}) == {}
    assert restore_i18n._("main:newgame") == "main:newgame"
    # Degrading quietly would be the dishonest half: say so.
    assert "i18n.py" in capsys.readouterr().err


def test_a_failed_load_does_not_claim_the_language(tmp_path, monkeypatch, restore_i18n):
    """A corrupt `.mo` (partial rsync to a box) must not leave `lang` set to it.

    Mutation check: move `self.lang = lang` back above the `gettext.translation` call and
    the final assertion fails -- and with it the second call would silently early-return.
    """
    resource = _locales(tmp_path, mo=b"this is not a valid mo file")
    monkeypatch.setattr(lang_mod, "find_package_resource", lambda _p: resource)
    before = restore_i18n.lang
    # Must be a language it is not already in, or `switch_lang` early-returns and the test
    # proves nothing. Picked from the current value rather than hardcoded: `i18n` is
    # process-wide, so whichever test ran before decides what "current" is.
    target = "en" if before == "cn" else "cn"

    with pytest.raises(OSError):
        restore_i18n.switch_lang(target)

    assert restore_i18n.lang == before
