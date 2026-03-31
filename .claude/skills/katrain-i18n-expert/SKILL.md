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

## Quick Reference: Complete Workflow

```bash
# 1. Add translations to batch script (scripts/batch_translate_galaxy.py)
# 2. Run batch translation
python scripts/batch_translate_galaxy.py

# 3. Compile .mo files
python i18n.py

# 4. Rebuild frontend
cd katrain/web/ui && npm run build
```

## Recommended Method: Batch Translation Script

Use `scripts/batch_translate_galaxy.py` for all Galaxy UI translations. This script:
- Contains translations for all 11 languages in a single dict
- Automatically handles PO file formatting
- Provides clear output of what was updated

### Adding New Keys to Batch Script

Edit `scripts/batch_translate_galaxy.py` and add entries to `GALAXY_TRANSLATIONS`:

```python
GALAXY_TRANSLATIONS = {
    # Use namespaced keys for organization
    "timer:main": {
        "en": "MAIN",
        "cn": "主时",
        "tw": "主時",
        "jp": "持時",
        "ko": "기본",
        "de": "HAUPT",
        "es": "PRINC",
        "fr": "PRINC",
        "ru": "ОСН",
        "tr": "ANA",
        "ua": "ОСН",
    },
    # Simple keys work too
    "Captures": {
        "en": "Captures",
        "cn": "提子",
        "tw": "提子",
        "jp": "アゲハマ",
        "ko": "따낸 돌",
        # ... other languages
    },
}
```

### Key Naming Conventions
- Use lowercase with spaces or namespaced with colons
- Namespace prefixes: `dashboard:`, `play:`, `lobby:`, `analysis:`, `menu:`, `timer:`, `game:`
- Examples: `timer:main`, `play:vs_ai_free`, `Settings`, `PASS`

## Frontend Integration (React/TypeScript)

### Using the useTranslation Hook (Preferred)

```tsx
import { useTranslation } from '../hooks/useTranslation';

const MyComponent = () => {
    const { t } = useTranslation();

    return (
        <Typography>{t("timer:main")}</Typography>
    );
};
```

The `useTranslation` hook:
- Returns `{ t, language }` where `t` is the translation function
- Automatically re-renders when language changes
- Located at: `katrain/web/ui/src/hooks/useTranslation.ts`

### Translation Function Behavior
- `t("key")` - returns translation or key as fallback
- Falls back gracefully if translation not found

### Galaxy UI Components with i18n
All Galaxy components should import `useTranslation`:
```tsx
import { useTranslation } from '../hooks/useTranslation';
// or for components deeper in the hierarchy:
import { useTranslation } from '../../hooks/useTranslation';
```

### CRITICAL: Always Use useTranslation() Hook — Never Use i18n.t() Alone

**Every React component that calls `i18n.t()` MUST also call `useTranslation()`.** Without the hook, the component will not re-render when the user switches languages from the sidebar, because there is no React state change to trigger a re-render.

```tsx
// WRONG — translations will not update on language switch
import { i18n } from '../../../i18n';

export default function MyComponent() {
  return <Typography>{i18n.t('live:try', 'Try')}</Typography>;
}

// CORRECT — component re-renders when language changes
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';

export default function MyComponent() {
  useTranslation(); // subscribes to language changes, triggers re-render
  return <Typography>{i18n.t('live:try', 'Try')}</Typography>;
}
```

**Why this matters:** `i18n.t()` reads from the global `i18n` singleton which does update internally, but React has no way to know the data changed unless a state update triggers a re-render. The `useTranslation()` hook subscribes to `i18n.notify()` via `useState`, which is what triggers the re-render.

**Checklist when adding translations to a component:**
1. Does the component import `useTranslation`? If not, add the import.
2. Does the component function body call `useTranslation()`? If not, add the call.
3. Verify by switching languages in the sidebar — text should update immediately without a page refresh.

### i18n Class (Low-level)
- Source: `katrain/web/ui/src/i18n.ts`
- Loads translations from API: `/api/translations?lang=xx`
- Used internally by `useTranslation` hook
- **Do not use `i18n.t()` in React components without also calling `useTranslation()`**

### Settings Context
- Location: `katrain/web/ui/src/galaxy/context/SettingsContext.tsx`
- Default language: `cn` (Simplified Chinese)
- Manages language state globally

## Backend Integration (Python)

```python
from katrain.core.lang import i18n

# Get translated string
text = i18n._("your new key")
```

## Manual PO File Editing (Alternative)

If needed, you can edit PO files directly:

### 1. Edit English Source
`katrain/i18n/locales/en/LC_MESSAGES/katrain.po`:
```po
msgid "dashboard:welcome"
msgstr "Welcome to Galaxy Go"
```

### 2. Edit Target Language
`katrain/i18n/locales/cn/LC_MESSAGES/katrain.po`:
```po
msgid "dashboard:welcome"
msgstr "欢迎来到 Galaxy Go"
```

### 3. Compile and Rebuild
```bash
python i18n.py
cd katrain/web/ui && npm run build
```

## Troubleshooting

### Translations Not Appearing
1. Check .mo files exist: `ls katrain/i18n/locales/cn/LC_MESSAGES/*.mo`
2. Verify component uses `useTranslation()` hook
3. Check browser console for API errors
4. Ensure key exists in en.po (source of truth)
5. Verify batch script ran: check for "Updated X entries" output

### Component Not Re-rendering on Language Change
Ensure component uses `useTranslation()`:
```tsx
const { t } = useTranslation(); // This subscribes to language changes
```

### Duplicate Key Errors
The `i18n.py` script automatically removes duplicates. Check output for warnings.

### Batch Script Not Updating Keys
The batch script only updates existing entries. If a key is truly new:
1. Add it to en.po first manually
2. Run `python i18n.py` to propagate structure
3. Then run batch script to fill translations

## Key Files Reference

| Purpose | File |
|---------|------|
| **Batch translation script** | `scripts/batch_translate_galaxy.py` |
| i18n sync/compile script | `i18n.py` |
| useTranslation hook | `katrain/web/ui/src/hooks/useTranslation.ts` |
| Frontend i18n class | `katrain/web/ui/src/i18n.ts` |
| Settings context | `katrain/web/ui/src/galaxy/context/SettingsContext.tsx` |
| English translations | `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` |
| Translation API | `katrain/web/api/v1/translations.py` |

## Quality Gates

- Never hardcode user-facing text in components
- Always use `useTranslation()` hook in React components
- Add all new keys to `scripts/batch_translate_galaxy.py`
- Run `python i18n.py` after any .po file changes
- Test language switching after adding new keys
- Provide translations for all 11 languages when adding new keys

## Common Translation Keys by Category

### Timer/Game Controls
- `timer:main`, `timer:byo`, `timer:periods`
- `Captures`, `PASS`, `RESIGN`
- `Black`, `White`

### Navigation
- `Dashboard`, `Play`, `Research`, `Live`, `Settings`
- `Login`, `Logout`, `Language`

### Play Menu
- `play:choose_mode`, `play:vs_ai_free`, `play:vs_ai_rated`
- `play:vs_human`, `play:vs_ai_free_desc`

### Game Room
- `leave_game_title`, `leave_game_warning`
- `resign_and_exit`, `continue_game`
- `game:result_win`, `game:result_loss`
