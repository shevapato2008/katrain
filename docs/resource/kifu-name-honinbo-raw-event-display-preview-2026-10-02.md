# Honinbo raw-event display preview (2026-10-02)

Prepared a mechanical **34 raw values × 11 locales** display preview for the exact `1st Honinbo` through `34th Honinbo` cohort. This preview creates no candidate approvals, does not alter the signed or pending Honinbo bundle, and does not modify code or the database.

## Frozen scope and inputs

- The pinned production inventory and `event-components-v4` group identify 34 exact raw event values affecting **1,617 album links**. The first, 17th, and 34th values affect 46, 74, and 33 games, respectively. The ordinal is an edition component; `round_name` remains separate.
- The input base forms are the 11 source-reviewed conventional event names: `Honinbo`, `本因坊战`, `本因坊戰`, `本因坊戦`, `본인방전`, `Hon’inbō`, `Torneo Hon'inbō`, `Tournoi Hon'inbō`, `Турнир Хонинбо`, `Honinbo Turnuvası`, and `Турнір на звання Хон'імбо`. Their source evidence and series boundary are recorded in the [11-language source memo](kifu-name-honinbo-11lang-source-memo-2026-10-02.md); this preview makes no new source claim and does not treat a series name as approval of a full edition label.
- Inputs are pinned in the protected JSON: frozen inventory file SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`, group artifact file SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05` (internal content SHA-256 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`), and source-reviewed base-name file SHA-256 `c9698402c05fa9863cc024c11f53b30229cd435c132620b4acf4775086bb9001`.

## Mechanical output samples

The protected JSON contains every label. The renderer places the core first and the edition second, joined by ` · `.

| Raw event | Games | English | Simplified Chinese | Japanese | Korean | Ukrainian |
|---|---:|---|---|---|---|---|
| `1st Honinbo` | 46 | `Honinbo · 1st` | `本因坊战 · 第1届` | `本因坊戦 · 第1回` | `본인방전 · 제1회` | `Турнір на звання Хон'імбо · 1-й розіграш` |
| `17th Honinbo` | 74 | `Honinbo · 17th` | `本因坊战 · 第17届` | `本因坊戦 · 第17回` | `본인방전 · 제17회` | `Турнір на звання Хон'імбо · 17-й розіграш` |
| `34th Honinbo` | 33 | `Honinbo · 34th` | `本因坊战 · 第34届` | `本因坊戦 · 第34回` | `본인방전 · 제34회` | `Турнір на звання Хон'імбо · 34-й розіграш` |

## Template checks and blocker

`structure_event` extracts the leading English ordinal as `edition` and preserves `Honinbo` as the core. `render_event_components` then uses `_EDITION` from `name_candidates.py`: `en` writes an English ordinal; `cn/tw` use `第N届/屆`; `jp/ko` use `第N回/제N회`; the remaining locales use the configured Ausgabe / edición / édition / розыгрыш / edisyon forms. The output is suitable for inspecting the component values, but **not safe to approve or import as full raw-event names yet**:

- The edition parser correctly sees the raw ordinal as a prefix (`1st Honinbo`), while the formatter always moves it after the series core. This is a generic template behavior, not a reviewed Honinbo-specific syntax decision.
- More concretely, the Japanese renderer emits `本因坊戦 · 第N回`; the official Nihon Ki-in edition records use `第N期 本因坊戦` (as documented in the source memo). The edition unit and order therefore do not match this series' source form. Other locale outputs also remain unreviewed combinations; source evidence for a base series name alone does not establish the composed phrase.
- The two current parsers also disagree at the classification layer: `structure_event` recognizes these raw strings as `english_ordinal_edition`, while `parse_event` leaves each full raw value `unclassified_pending`. A new raw-event owner therefore needs its own reviewed category declaration; component parsing alone does not approve the raw value or display.

There are **zero normalized display collisions** within all 34 editions in each locale. Maximum generated label lengths are:

| Locale | Collisions | Max code points | Max UTF-8 bytes |
|---|---:|---:|---:|
| en | 0 | 14 | 15 |
| cn | 0 | 11 | 24 |
| tw | 0 | 11 | 24 |
| jp | 0 | 11 | 24 |
| ko | 0 | 11 | 24 |
| de | 0 | 22 | 26 |
| es | 0 | 30 | 34 |
| fr | 0 | 30 | 33 |
| ru | 0 | 30 | 53 |
| tr | 0 | 31 | 33 |
| ua | 0 | 41 | 72 |

## Remaining raw-event approval and import work

The current [preimage-binding record](kifu-name-honinbo-corrected-name-preimage-binding-2026-10-02.md) describes the pending bundle: it contains the 34 reviewed event-link scopes and the 11 base `event` name candidates, but it has no exact `raw_event` owners. `strict_slot_approvals` requires both the linked event name and an approved exact raw-event display whenever the raw value has structured components. The preview cannot fill that slot.

1. Settle a reviewed Honinbo-specific edition convention for each locale, including the Japanese `期` form and the target-language word order. Pin a named formatter/rule version if deterministic composition is approved; otherwise research the full edition forms as conventional names. The current preview is not evidence for either choice.
2. In a new bundle copy, declare one raw-event owner for each of the 34 exact raw spellings, with exact occurrence IDs and scope hashes and an independently reviewed raw-value category. Preserve the existing 1,617 link scopes and edition/round boundary. Do not edit the existing bundle.
3. Prepare 374 full raw-event display candidates (34 × 11), each attached to the exact raw owner and language. Supply target-language source evidence for conventional names, or meet the validator's full generated-name, reading, rule-version, and review requirements. A source-reviewed core name cannot substitute for the edition-bearing raw display.
4. Capture and bind the new raw-name row preimages (null for newly created owners), then have an independent final reviewer approve the 374 candidates after binding. Complete the separate final review for the 11 base `event` names as well; they remain pending in the preimage-bound bundle.
5. Rebuild the bundle with authentic producer/reviewer records and recomputed hashes; require the offline validator to clear all event-owner and raw-event-owner language checks. On a current production snapshot, verify `strict_slot_approvals` for all 1,617 event slots, then use the established isolated-copy dry-run/apply/conditional-undo gate before any production import.

## Protected machine-readable artifact

The full 34 × 11 preview, edition parts, occurrence counts, source-record pins, collision results, and per-locale character/byte maxima are stored outside the repository at `~/.local/share/kifu-name-audit/2026-10-02/honinbo-display-preview/honinbo-34x11-raw-event-display-preview.json`. Directory mode is `0700`; file mode is `0600`; file SHA-256 is `2fa193a437172029c30d48067c4f70d437199dee7318d3a5213785fa7aba4129`. The artifact explicitly marks every output as preview-only and records that no approvals or database writes occurred.
