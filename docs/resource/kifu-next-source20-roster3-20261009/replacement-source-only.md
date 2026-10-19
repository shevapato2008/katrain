# Korean roster replacement source-only check

**Status:** no fresh eligible replacements found.

I compared the complete 904-name Korean Baduk Association Chinese-player roster body with 631 Daum Korean-Hanja rows and the pinned post-591 strict approved-name snapshot. The exact identity join produced 18 four-language owners missing Korean; every match is already in batch 592 or the sibling roster3 scope. Fresh eligible matches: 0.

KBA roster response: POST `https://www.baduk.or.kr/record/player_in.asp` at `2026-10-08T21:25:25.328636+00:00`, HTTP 200, 80097 bytes, SHA-256 `fe86b432435c241b354b2286531cc7529fa9ebeccacb22684aa31e9bdbdab934`; raw body: `captures/replacement-kba-china-list.body`.
Daum full-table response: `https://m.cafe.daum.net/clubA7bodook/EMJA/3240?listURI=%2FclubA7bodook%2FEMJA`, `2026-10-08T20:59:49.643751+00:00`, HTTP 200, SHA-256 `19f1312b4f32d60a4926d24e15c9344b267ebbe3c70c8e2ddf91413fd1cf959b`; Daum is used only as an identity bridge.

Seven additional high-frequency candidates were queried by Hangul against the KBA Chinese roster; none returned the same Hangul profile. Their body hashes, request parameters and outcomes are in `replacement-source-only.json`. A `천자` prefix search returned unrelated similarly prefixed names and was not treated as a match.

No SQL, SSH, database writes, source approval, builds, or Git operations were performed.
