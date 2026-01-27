# Skill: KaTrain i18n Expert

## Description
Manages multilingual translations for KaTrain's Galaxy Go web UI. Uses Gettext (PO/MO files) with 11 supported languages.

## Supported Languages
| Code | Language | File Path |
|------|----------|-----------|
| en | English (source) | `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` |
| cn | Simplified Chinese | `katrain/i18n/locales/cn/LC_MESSAGES/katrain.po` |
| tw | Traditional Chinese | `katrain/i18n/locales/tw/LC_MESSAGES/katrain.po` |
| jp | Japanese | `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` |
| ko | Korean | `katrain/i18n/locales/ko/LC_MESSAGES/katrain.po` |
| de | German | `katrain/i18n/locales/de/LC_MESSAGES/katrain.po` |
| es | Spanish | `katrain/i18n/locales/es/LC_MESSAGES/katrain.po` |
| fr | French | `katrain/i18n/locales/fr/LC_MESSAGES/katrain.po` |
| ru | Russian | `katrain/i18n/locales/ru/LC_MESSAGES/katrain.po` |
| tr | Turkish | `katrain/i18n/locales/tr/LC_MESSAGES/katrain.po` |
| ua | Ukrainian | `katrain/i18n/locales/ua/LC_MESSAGES/katrain.po` |

## Workflow: Adding New Translation Keys

### 1. Choose a Translation Key (msgid)
- Use lowercase English, words separated by spaces or namespaced with colons.
- Examples: `update timer`, `dashboard:welcome`, `play:vs_ai_free`.
- Namespace prefixes help organize keys: `dashboard:`, `play:`, `lobby:`, `analysis:`, `menu:`.

### 2. Update English Source File
Edit `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`:
```po
msgid "dashboard:welcome"
msgstr "Welcome to Galaxy Go"
```

### 3. Update Target Language Files
For each language that needs translation, edit the corresponding .po file. For systematic updates across all languages, use a batch script.

### 4. Compile Translations
Run from project root:
```bash
python i18n.py
```
This generates `.mo` binary files from `.po` source files.

### 5. Rebuild Frontend
```bash
cd katrain/web/ui
npm run build
```

## Frontend Integration (React/TypeScript)

### Using Translations in Components
```tsx
import { i18n } from '../../i18n';  // Adjust path as needed

// Basic usage with fallback
i18n.t('dashboard:welcome', 'Welcome to Galaxy Go')

// In JSX
<Typography>{i18n.t('Settings', 'Settings')}</Typography>
```

### CRITICAL: Subscribe to Translation Changes
Components MUST use `useSettings()` hook to re-render when language changes:
```tsx
import { useSettings } from '../context/SettingsContext';

const MyComponent = () => {
    useSettings(); // Subscribe to translation changes for re-render

    return (
        <Typography>{i18n.t('my_key', 'Fallback')}</Typography>
    );
};
```
Without `useSettings()`, components won't update when the user switches languages.

## Automation and Batch Processing
When many keys need to be translated across all 11 languages, use a script with `polib`.

### Example Batch Script (`scripts/batch_translate_galaxy.py`)
```python
import polib
from pathlib import Path

def update_po_file(lang_code, translations):
    po_path = Path(f"katrain/i18n/locales/{lang_code}/LC_MESSAGES/katrain.po")
    po = polib.pofile(str(po_path))
    for msgid, lang_map in translations.items():
        if lang_code in lang_map:
            entry = po.find(msgid)
            if entry:
                entry.msgstr = lang_map[lang_code]
            else:
                po.append(polib.POEntry(msgid=msgid, msgstr=lang_map[lang_code]))
    po.save()
```

## Quality Gates
- **No Hardcoding**: Never hardcode user-facing text in code.
- **English Fallback**: Always provide an English fallback in `i18n.t('key', 'fallback')`.
- **Compile After Change**: Always run `python i18n.py` after editing `.po` files.
- **Verification**: Test language switching in the UI to ensure new keys load correctly.
- **Hook Usage**: Ensure all Galaxy UI pages/components have the `useSettings()` hook.