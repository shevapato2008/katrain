# Named phone registration and concise authentication

## User-approved outcome

- Registration collects one unique public username (nickname), password, mainland phone and SMS code.
- A phone/code login never silently creates an unnamed account. After valid proof, an unknown phone enters the same registration completion flow. A known, complete account signs in normally.
- An existing password account without a phone uses password login and the existing reauthenticated phone-binding flow. Typing an existing username into registration never merges or claims that account.
- Historical phone-created accounts complete their public name/password **in place**. Their canonical username, ID, UUID, membership, wallet, claim and historical ledger remain unchanged.
- Login and registration are concise: no explanatory paragraphs. Signup reward appears only in an authoritative success notice. Error guidance is short, local and only shown when needed.
- Kiosk/launcher keeps its guest entry. Galaxy has no guest-login button: anonymous browsing is already guest access. Galaxy auth remains a modal over the actual Galaxy page.
- Preserve Galaxy/Kiosk's 11 locales and launcher's existing 5 locales.
- Release to TEST, then PROD, then RK3562; detect other RK deployments and acquire the existing maintenance lock before any write. Wait when busy. Never terminate another deployment, steal its lock, guess another device identity, or deploy via an unverified host.

## Approved visual basis

User confirmed the Kiosk Artifact and explicitly authorized implementation after the Galaxy guest/background corrections. Those corrections are incorporated in:

- `docs/design/phone-named-signup-2026-11-13/index.html`
- `docs/design/phone-named-signup-2026-11-13/login-kiosk-1024x600.png`
- `docs/design/phone-named-signup-2026-11-13/register-galaxy-1440x900.png`

Use these sizes for a representative runtime comparison. No further style exploration or repeated user confirmation is required for the accepted corrections.

## Minimal authority and data contract

Add only nullable `users.public_username`. The authoritative **server** database enforces its named unique index; a **board shadow** database stores it only as a trusted display cache and permits duplicate names. A deleted cloud account's public name can later belong to another canonical account while both historical shadows remain on the board. It is the sole new user-visible name; no alias framework, separate nickname column, registration-ticket table or configurable profile state machine.

Do not put `unique=True`, a UniqueConstraint, or this index on shared declarative metadata, including at runtime: `create_all`/generic missing-index creation must not recreate server uniqueness on a later board engine. A dedicated role-aware migration creates and verifies the ordinary, full, one-column unique index only for server authority (PostgreSQL and server-mode SQLite tests). Verify actual uniqueness, columns, and absence of predicates/expressions. Board mode does not create that index, does not resolve password login by cached public name, and leaves old public cache values unset until a validated cloud `/me`/bootstrap updates them. A trusted null must also clear a stale inferred value. Do not backfill generated board handles based on the absence of a local PhoneIdentity: those private identities live only on the cloud.

Canonical `username` remains JWT `sub`, token/refresh lookup, shadow identity and SSO bootstrap key. ID/UUID remain ownership and accounting keys. `/me.username` remains canonical; add optional `public_username` to trusted user projections. A display helper may suppress generated handles, but never supplies authentication or ownership decisions.

In the authoritative server, backfill old human accounts' public name with their exact canonical name. Legacy generated-handle compatibility uses full `u_[0-9a-f]{20}` match, a PhoneIdentity and non-admin status, excluding a same-user `bound_existing` claim. Retained claims may refer to deleted users, so their audit user ID must not be treated as a live identity FK. This compatibility classification changes no password or identity automatically; setting a public name/password requires that phone's valid OTP.

Keep the existing exact, case-sensitive uniqueness semantics. New names are 2–24 Unicode letters/digits or `_`/`-`; no whitespace/control characters. Reserve `guest`, `admin`, `admin:*` and `u_` prefixes case-insensitively for new claims. Existing names are not revalidated or normalized during login. Public names are set once in this slice.

Introduce a separate server password **login-name** lookup. It may resolve a canonical or public name but must reject ambiguity. Do not change canonical lookup used by JWT, refresh, ownership checks or SSO. Board password login forwards to this authority; it never authenticates through a cached public-name lookup. Audit production account writers so old human canonical names also occupy their public-name namespace. The shared shadow writer instead synchronizes the authoritative public field (including null) without inventing one from a generated canonical name.

New passwords: at least 15 Unicode characters, UTF-8 at most 72 bytes, no NUL; do not trim, normalize, silently truncate or restrict to ASCII. This follows current single-factor password guidance because SMS is an alternative, not a mandatory second factor. Existing password verification retains its prior semantics. Remove launcher-only ASCII restrictions from password login so newly set Unicode passwords work there.

## Authentication journey

1. Existing `purpose=login` challenge and phone/flow/code HMAC remain the proof. Preserve 5-minute TTL, active challenge, cooldown, failed-attempt budget and all send limits.
2. Correct `/auth/phone/login` proof:
   - complete bound account: consume and issue the existing token shape;
   - unknown phone or eligible legacy account needing a public name: `409 detail.code=profile_required`, optionally `mode=register|complete`; no token, no account/grant, no challenge consumption or lifetime extension.
3. New `/auth/phone/register` accepts `challenge_id`, `code`, `flow_id`, `public_username`, `password`. The form retains proof only in memory; it never asks for another SMS merely to complete a name. Finalization rechecks proof under the existing phone/challenge locks.
4. With no identity: create the internal handle and public name, phone identity, permanent claim (only if absent), and the existing 5000-credit signup adjustment. If a permanent claim already exists, registration grants zero.
5. With an eligible incomplete account: set public name/password on that same row; never touch membership, balance, claim or ledger. A complete account cannot be overwritten through registration.
6. Account/name claim, grant and challenge consumption commit together. A public-name conflict or ledger failure rolls back all finalization writes; a still-valid code can be retried with another name. Wrong-code accounting remains committed independently as today. Password hashing happens outside long-held account/billing locks, with proof rechecked before the final write.
7. Registration success carries an authoritative grant result (zero or 5000 credits) separately from token installation, so only a newly awarded grant produces “注册成功，已赠送50积分”. Completion/return login never announces a new award.

Remote clients and launcher stage the candidate token, validate canonical `/me`, and apply the existing generation/CAS checks before installing it. `profile_required` is an expected business outcome, never an installed session or trigger for token refresh/replay. Phone/code/password never enter URL, persisted browser storage, public user DTOs, logs or screenshots.

## Research supporting these choices

- [Supabase OTP reference](https://supabase.com/docs/reference/javascript/auth-signinwithotp) supports automatic signup and disabling it: this is a product choice, not a requirement of SMS login.
- [Auth0 progressive profiling](https://auth0.com/docs/manage-users/user-accounts/user-profiles/progressive-profiling) describes collecting missing profile information incrementally and avoiding repetitive questions.
- [Firebase account linking](https://firebase.google.com/docs/auth/web/account-linking) keeps the same user ID across linked authentication methods.
- [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) warns against account-enumerating errors; only reveal an unbound-phone continuation after valid OTP proof. It also distinguishes single-factor password length from MFA.

## Explicit exclusions

No account merging, public-name editing, new social-auth provider, billing repricing, reward increase, real SMS automation, real payment/paid analysis, unrelated camera/USB changes, or new deployment framework. Reuse established tests, catalogs, privacy controls and configuration-preserving release tooling.
