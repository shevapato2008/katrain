import polib
import os

locales = ['de', 'ru', 'fr', 'es', 'ua', 'tr', 'jp', 'ko', 'tw']
translations = {
    'de': 'Abbrechen',
    'ru': 'Отмена',
    'fr': 'Annuler',
    'es': 'Cancelar',
    'ua': 'Скасувати',
    'tr': 'İptal',
    'jp': 'キャンセル',
    'ko': '취소',
    'tw': '取消'
}

for lang in locales:
    po_path = f'katrain/i18n/locales/{lang}/LC_MESSAGES/katrain.po'
    if os.path.exists(po_path):
        po = polib.pofile(po_path)
        found = False
        for entry in po:
            if entry.msgid == 'cancel':
                entry.msgstr = translations[lang]
                if entry.comment and 'TODO' in entry.comment:
                    entry.comment = entry.comment.replace('TODO', '').strip()
                found = True
                break
        if found:
            po.save()
            print(f"Updated {lang} translation for 'cancel'")
        else:
            print(f"Warning: msgid 'cancel' not found in {lang}")