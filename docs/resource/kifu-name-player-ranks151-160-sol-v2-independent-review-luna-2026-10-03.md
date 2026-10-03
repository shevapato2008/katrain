# Ranks 151–160 Sol v2 source package: independent review

2026-10-03. Independent source review of the frozen Sol v2 packet only; no edits to the source packet, database access, candidate approval, or production authorization.

## Result

Reviewed all 50 owner/language cells (10 owners × cn/tw/jp/ko/en): **29 PASS, 21 HOLD**. PASS counts by language: cn 6, tw 5, jp 9, ko 7, en 2. Nine owners have at least one PASS; rank154 remains HOLD in all five languages.

PASS means the source-positive cell survived this review as a candidate: there is an identity anchor and an actual target-language display string supported by the captured page/variant. It is not approval to merge a name into application data.

## Checks

The 29 candidate article captures matched their recorded hashes, QIDs, page titles, and revisions. Explicit Chinese variant captures matched `zh-Hans-CN` or `zh-Hant-TW` and the displayed title. All 10 official identity-anchor capture hashes matched. Korean disambiguation article titles were retained while the person’s net name was taken from the relevant biography text.

The source package reviewed is `~/.local/share/kifu-name-audit/2026-10-03/player-ranks151-160-wikipedia-increment-sol-v2/`; Sol’s source memo is `kifu-name-player-ranks151-160-wikipedia-source-increment-sol-2026-10-03.md`.

## Findings requiring care

- **Rank151 identity-conflict note:** the retained conflict assertion is not reproduced by its cited `zh-315.html` capture/hash: that capture gives DOB 1986-08-13, matching the official, English, and entity sources. The name cells remain PASS on the identity evidence; do not use that conflict assertion as evidence.
- **Rank151 tw:** PASS is supported by an explicit `zh-tw` rendered variant (`zh-Hant-TW`) with displayed name `白洪淅`. It is the same canonical article/QID and revision as cn, not a separate zh-tw sitelink or article.
- **Rank157:** KBA’s birth-date field is blank. The match is supported by the official Korean name and KBA career entry for the 2010 Gosei title, alongside the same-person Go/Wikipedia evidence; no official DOB is asserted.
- **Rank154:** all five cells remain HOLD because the Korean `장타오` page is a common-name disambiguation and the independent Go-player page could not be resolved from this packet. No absence claim is made.
- **Ranks153 and 158 cn/tw:** remain HOLD because the packet has generic zh discovery evidence but no explicit cn/tw variant capture.

## Protected review record

Independent row-by-row review record and summary are frozen read-only at:
`~/.local/share/kifu-name-audit/2026-10-03/player-ranks151-160-v2-independent-review-luna/`

The matrix records 50 row decisions and the supporting page/variant/revision, captures, identity source, and findings. Its summary records source packet hashes and integrity checks. This is a source review only, not self-approval or database authorization.

SHA-256: `review-matrix50.jsonl` `3c3726160da0458a81fed95a9aa103f685401155a32bfed16c68ac10658133ba`; `review-summary.json` `58a38d34f5eec09e023e5675deb42e7f60f5a83bf0d5b6c16565534383a64af8`.
