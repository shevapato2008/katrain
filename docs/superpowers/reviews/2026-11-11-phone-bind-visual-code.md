# Phone binding B5 visual and frontend review

Date: 2026-11-11. Baseline: `37c2867b9`; scope is the B5 frontend working tree.

| Gate | Decision |
| --- | --- |
| B5 visual | **Approved** — binding backend may begin for this journey |
| B5 frontend specification | **Approved** — no blocking finding in this slice |
| B5 frontend quality | **Approved** — no blocking finding in this slice |

The user delegated visual decisions to the independent Astra reviewer. The review applies `ui-ux-pro-max` and the already approved Galaxy/Zen and Kiosk themes. This is a frontend Fixture gate, not verification of actual binding, account balances, SMS, backend authorization or deployment.

## Visual evidence and accepted differences

At `output/playwright/phone-bind-b5-2026-11-11/`, the reviewer inspected the reference/implementation pairs in the same-size side-by-side images and their overlays: Galaxy 1440×900 and Kiosk 1024×600. The final Kiosk implementation uses 12px field gaps. Also inspected `kiosk-entry.png`, `kiosk-reauth-locked.png`, and `galaxy-bound-success.png`.

- **Reachable production entry:** the local Fixture imports the real `src/main.tsx`/`AppRouter`. Its browser journey clicks the existing Kiosk top-bar account action, reaches `/kiosk/membership`, and opens the new binding row. This is the real account landing point; the unused legacy `AccountSection` was not revived. Galaxy uses one entry under the existing sidebar account area.
- **Composition and geometry:** the existing account page remains visible behind the scrim. Galaxy's MUI title/content spacing and right-aligned action group differ modestly from the simplified static reference and are accepted. Kiosk inherits actual shell typography and larger controls, making the final card about 50px taller than the reference; all initial controls fit within 1024×600. In the lock state, content scrolling remains inside the dialog and the policy and bottom actions remain visible. There is no horizontal overflow, clipped primary action or overlapping label/value.
- **Typography, color and assets:** current brand assets, WenKai/Kiosk typography and dark surfaces are preserved. Galaxy uses the B1-approved local contrast treatment for focused labels and text/outlined actions; Kiosk retains its readable jade theme. Disabled controls remain visually distinct. The three fields are clearly labeled as mainland phone, SMS code and current-account password.
- **Honest state semantics:** the lock screenshot shows a red 900-second reauthentication warning and disabled confirmation, with the password cleared. The success screenshot shows a success message, server-supplied mask and the preservation/no-repeat-grant policy; private inputs and editable binding actions are absent. The sidebar account line shows the mask after success. These are Fixture observations, not proof of backend balance or grant behavior.
- **Policy and touch:** the copy explains SMS login after binding, preserved balance/membership and no repeat points. The entry/cancel actions meet the 44px minimum, confirmation is at least 48px, and SMS send is at least 56px. No new screen or account-management subsystem is introduced.

The implementer's browser script checks one challenge and one bind call, removal of the password field, the read-only mask after closing, and the unchanged Fixture wallet value. The reviewer inspected that script and the resulting images; no full-state screenshot matrix was requested or repeated.

## Frontend source review

Reviewed `PhoneBindDialog`, `PhoneBindingEntry`, the binding API additions, their tests, the two production entry insertions and the Kiosk-local styles.

- `PhoneBindingStatus` distinguishes unbound from bound-with-mask. Entry and dialog show loading/error with explicit retry; failed status reads are not interpreted as unbound. Already-bound accounts expose only the server mask.
- The UI hides guest, reserved administrator names and `is_admin` accounts. Strict Kiosk takes the launcher path without private API calls or a local dialog. Server-side eligibility, including local-shadow restrictions, remains authoritative for the backend phase.
- Status/challenge/bind requests use the caller's captured credential and `cache: no-store`, with no mutable `localStorage` fallback. The bind challenge uses `purpose: bind`; current password appears only in the final bind POST. No B5 code stores phone, OTP or password, inserts them into URLs, or logs them.
- The dialog's private form remounts on canonical identity or token changes. Request revision, abort and captured identity/token checks discard old status/bind responses; the entry independently checks ownership before installing a returned mask. Closing unmounts private form state. Successful binding clears phone/code/password/challenge before rendering the mask.
- The current-password field is confined to this binding form. B1 OTP login remains its existing two-field flow. Reauthentication errors clear the password, lock errors retain a countdown and block confirmation, and changing the phone does not reset a known reauthentication lock.
- Focused tests inspect final request shape/captured token, masked success, read-only binding, honest conflict/reauth/lock responses, token-change cleanup, eligibility/strict routing, failed-status retry and late private-status suppression. Existing browser evidence exercises the shared form through the actual application entry.

## Focused validation and new copy

The reviewer independently checked all 20 new `auth:bind_*` entries across en/cn/tw/jp/ko/de/es/fr/ru/tr/ua: identical key sets, no empty translations, matching `{seconds}` placeholders, and exact new-entry PO/MO agreement in all 11 compiled catalogs. Every new binding key used by the two components is covered, and existing translated entries are unchanged. Current-account password, preserved balance/membership, no repeat grant, status-load failure, lock wait and launcher-management wording were inspected. This is focused source/catalog review, not native-speaker or all-language visual certification.

The implementer reported **87 passed / 5 mode-conditional skips across 10 focused files**, with TypeScript checking already green. The reviewer read the relevant tests and used the real-entry browser evidence rather than repeating that suite. The normal/strict final builds and strict API boundary checks are being finalized separately for root's integration summary; this report does not claim those unfinished checks have passed. No additional screenshot matrix is required.

No backend source, credential, real manifest, remote host, real SMS service or RK device was accessed. The temporary B5 HTML entry is stage-local and must be removed during binding integration; this review does not require its premature removal before the approved Fixture phase ends.
