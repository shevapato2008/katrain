# SmartBox device appearance

Strict SmartBox kiosk builds (`build:smartbox-kiosk-2d`) read language and Chinese
interface font from the setup wizard's settings authority. Standalone Galaxy,
Zen and non-strict kiosk preferences retain their independent behavior.

`GET /api/v1/kiosk-preferences/device` returns only:

```json
{"language":"zh-TW","font":"kai"}
```

The server reads `SMARTBOX_SETTINGS_PATH`, defaulting to
`/var/lib/smartbox/settings.json`. Supported languages are `zh`, `zh-TW`, `en`,
`ja`, `ko`; fonts are `wenkai`, `kai`, `daoli`, `hei`. Missing first-boot files
and missing/unknown legacy enum fields use `zh` / `wenkai`. An existing unreadable,
malformed or non-object file returns 503. Responses use `Cache-Control: no-store`.
This route is read-only; the wizard remains the only global writer.

The Go UI maps language to `cn` / `tw` / `en` / `jp` / `ko` and font to
`wenkai` / `kaiti` / `lishu` / `heiti`. It waits for the first successful read
before mounting language-dependent pages, and retries on demand, focus and tab
visibility. A failed refresh retains the last valid app and exposes a retry
notice. Strict mode does not read or write a local language choice and does not
preload Chinese kifu data before the authority is known.

Go text size remains local in the existing typography endpoint. Size writes
preserve its legacy `{font,size}` payload; its font never overrides the global
font in strict mode. Global font updates do not reset local size.

OGS course requests use catalog IDs `zh-cn`, `zh-tw`, `en`, `ja`, `ko`.
Locale refresh replaces course/instruction/choice presentation while keeping the
original exercise judge, answer, move tree and physical-board problem key.
The owned font assets include licensed kana/Hangul support; see
`katrain/web/ui/src/kiosk-shell/fonts/CJK-FONT-SOURCES.md`.

## Verification

Focused UI coverage includes initial/error/retry/stale reads, local compatibility,
font/size ownership, course state preservation, five-language shell messages and
existing kifu locale/cache/history behavior. The pinned actual OGS source test
checks returned instructions for all 3,551 steps in all five languages. Source
commit: `1c1c2b82d027f7c307ab25886112cf0a6baf680a`; locale revision:
`5304fd731af8856a16d198d506111d61`. The exported content SHA-256 is
`9b61f2f14233e23f4a1967a2f55b9f20c5221012badefa56d4bd9a3b7dfbdfc0`.
That private source bundle is a test input and is not bundled into production.

Use an isolated SQLite database for these backend tests:

```sh
KATRAIN_DATABASE_URL=sqlite:////private/tmp/katrain-appearance-tests.sqlite \
  python -m pytest tests/web_ui/test_kiosk_preferences.py \
  tests/web_ui/test_ogs_course_bundle.py tests/web_ui/test_ogs_public_course.py -q
```

The actual built kiosk was checked in Chrome at 1024×600 with test-isolated
backend dependencies and the real OGS public response presentation. Japanese and
Korean glyphs hit the owned script face. A Japanese-to-Korean refresh retained a
solved move; an initial settings 503 prevented cold kifu requests until retry,
and subsequent refresh failure kept the last valid app visible.
