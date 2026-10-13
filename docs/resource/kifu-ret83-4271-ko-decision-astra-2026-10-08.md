# ret83 · 4271 太田清道 · Korean published-name decision

- Date: 2026-10-08 (Asia/Shanghai).
- Reviewer configuration: `gpt-6-astra`, reasoning `max`, as delegated.
- Scope: one source-only Korean-name decision. No database binding review, SQL, signatures, Git, or additional network research.

## Decision

**PASS — `오타 세도`, `published_name` / `found`.**

The captured Cyberoro professional-player page places `오타 세도` and `太田清道` in the same name field. This supports the published Korean form under the accepted policy. Preserve the official full reading `おおた　せいどう`; do not describe `세도` as a NIKL-generated result or as the uniquely established Korean name. The earlier `세이도` versus `세도` normative question is unnecessary for this published-name choice and is not resolved by this decision.

## Actual evidence inspected

1. [Cyberoro player profile](https://www.cyberoro.com/info/player_view.oro?prpl_code=10000262), captured HTTP 200 at `2026-10-07T20:26:12.969511+00:00`.
   - Body: `/tmp/kifu-player-next5retired83-20261008/4271-ko-cyberoro.body`, 56,177 bytes, decoded as CP949.
   - Independently recomputed SHA-256: `8c8b4c1a327bf8c8095f3dbbe41628fc1227cff7a5d72a31b59da449cc34b75d`.
   - Rendered own-profile field: `이름 : 오타 세도 9단 [太田清道]`. The original HTML entity `&#28165;` decodes to `清`.
2. [Kansai Ki-in official profile](https://kansaikiin.jp/kisi_prof/otaseidou.html), captured HTTP 200 at `2026-10-07T20:22:27.737910+00:00`.
   - Body: `/tmp/kifu-player-next5retired83-20261008/4271-official-retry.body`, 16,896 bytes.
   - Independently recomputed SHA-256: `69caa4f69e47f415c7d8d014dbb52ee79382b9d0b490127b37f4a27716ab4c21`.
   - Actual own-profile heading: `太田清道 九段 （おおた　せいどう）`. This is hiragana, not a captured katakana field.

## Limits

Cyberoro lists `소속 : 일본기원`, which conflicts with the official Kansai Ki-in affiliation; that field is not corroborating identity evidence. Its birthday field is empty, and its rank/history fields are not used as birthday, current-rank, or identity facts. The accepted correspondence rests on the exact original name in a professional Go player profile. Preserve the original failed official `www` request separately from the successful retry. Source status and database ownership remain separate decisions.

## Capture provenance

Both bodies and their adjacent `.capture.json` files were supplied by `/root/next_players_sources_resume`, which reported acquiring them. This reviewer inspected local bodies and did not fetch either URL. The capture metadata contains the actual URL, UTC times, HTTP status, byte count and body SHA, but does not contain capture-actor or capture-model fields; do not fill these from the reviewer's model or from a later freezer's identity. Preserve the original metadata when freezing copies. Cyberoro's recorded response encoding is `ISO-8859-1`; CP949 is the successful body-decoding choice used in this review, not an alteration to that recorded response metadata.
