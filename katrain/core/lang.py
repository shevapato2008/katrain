import gettext
import os
import sys

from kivy._event import Observable

from katrain.core.utils import find_package_resource
from katrain.gui.theme import Theme


class Lang(Observable):
    observers = []
    callbacks = []
    FONTS = {"jp": "NotoSansJP-Regular.otf", "tr": "NotoSans-Regular.ttf", "ua": "NotoSans-Regular.ttf"}

    def __init__(self, lang):
        super(Lang, self).__init__()
        self.lang = None
        self.switch_lang(lang)

    def _(self, text):
        return self.ugettext(text)

    def set_widget_font(self, widget):
        widget.font_name = self.font_name
        for sub_widget in [getattr(widget, "_hint_lbl", None), getattr(widget, "_msg_lbl", None)]:  # MDText
            if sub_widget:
                sub_widget.font_name = self.font_name

    def fbind(self, name, func, *args):
        if name == "_":
            widget, property, *_ = args[0]
            self.observers.append((widget, func, args))
            try:
                self.set_widget_font(widget)
            except Exception as e:
                print(e)
                # pass
        else:
            return super(Lang, self).fbind(name, func, *args)

    def funbind(self, name, func, *args):
        if name == "_":
            widget, *_ = args[0]
            key = (widget, func, args)
            if key in self.observers:
                self.observers.remove(key)
        else:
            return super(Lang, self).funbind(name, func, *args)

    def switch_lang(self, lang):
        if lang == self.lang:
            return
        # get the right locales directory, and instantiate a gettext
        i18n_dir, _ = os.path.split(find_package_resource("katrain/i18n/__init__.py"))
        locale_dir = os.path.join(i18n_dir, "locales")
        # `fallback=True`: the compiled `.mo` files are **not in the repo** (`.gitignore`),
        # they only exist where someone ran `i18n.py` by hand. Without the fallback a clean
        # checkout raises FileNotFoundError *here*, and because `i18n = Lang(...)` runs at
        # module scope that is an **import-time crash of the whole app**, not a missing
        # translation. `katrain/vision/README.md:78` documents the manual workaround, which
        # is how we know this has been hit before. Degrade to the untranslated msgids and
        # say so on stderr -- silently serving an empty catalog is the dishonest half.
        locales = gettext.translation("katrain", locale_dir, languages=[lang, DEFAULT_LANGUAGE], fallback=True)
        if not hasattr(locales, "_catalog"):
            print(
                f"No compiled translations for '{lang}' in {locale_dir} -- showing untranslated text. "
                f"Run `python i18n.py` to build them.",
                file=sys.stderr,
            )
        self.ugettext = locales.gettext
        # Assigned **after** the load, not before: `switch_lang` early-returns when
        # `lang == self.lang`, so setting it first means a failed load (a truncated `.mo`
        # from a partial rsync, say) leaves the object claiming to be in a language whose
        # catalog it never loaded -- and the *next* call for that language returns 200 with
        # the previous language's table and no error anywhere.
        self.lang = lang
        self.font_name = self.FONTS.get(lang) or Theme.DEFAULT_FONT

        # update all the kv rules attached to this text
        for widget, func, args in self.observers:
            try:
                func(args[0], None, None)
                self.set_widget_font(widget)
            except ReferenceError:
                pass  # proxy no longer exists
            except Exception as e:
                print("Error in switching languages", e)
        for cb in self.callbacks:
            try:
                cb(self)
            except Exception as e:
                print(f"Failed callback on language change: {e}", file=sys.stderr)


DEFAULT_LANGUAGE = "en"
i18n = Lang(DEFAULT_LANGUAGE)


def rank_label(rank):
    if rank is None:
        return "??k"

    if rank >= 0.5:
        return f"{rank:.0f}{i18n._('strength:dan')}"
    else:
        return f"{1-rank:.0f}{i18n._('strength:kyu')}"
