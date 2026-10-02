# Park Junghwan (player 54): independent Russian display review

Reviewed 2026-10-02 by `/root/park_ru_review_sol` (`gpt-6.1-sol`). This reviews the pending Sol producer artifact in commit `d7e7b0f4`; it does not produce a new candidate or authorize a database write.

## Decision

**PASS for the source-level display `Пак Чонхван`** for `player:54`, `ru`. The pinned [Russian Wikipedia biography, revision 149787533](https://ru.wikipedia.org/w/index.php?title=Пак_Чонхван&oldid=149787533) uses that exact spelling in the person heading, infobox full-name field, opening identification, and biography prose. Its `박정환`, `朴廷桓`, 1993-01-11 birth date, Korean Go profession, and 9-dan rank match the separately captured [Korea Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457). These are direct identity-specific uses, sufficient to select one conventional display from the conflicting forms.

The competing spellings remain genuine attestations. The pinned [Russian Wikipedia 2010 Asian Games Go article, revision 146406034](https://ru.wikipedia.org/w/index.php?title=Го_на_летних_Азиатских_играх_2010&oldid=146406034) calls the Korean team and mixed-pair winner `Пак Чжон Хван` in several result rows. The biography's GoGameWorld, Sensei's Library, KBA, and game-link **labels** also use that form; those are Russian Wikipedia editor labels, not evidence that the destination pages publish a Russian name. The event article and biography are one publisher, so their repeated text is not independent corroboration. The separately published [Korea.net Russian report](https://russian.korea.net/Government/Current-Affairs/International-Events/view?affairId=2580&articleId=239703&subId=133&viewId=68450) uses `Пак Чон Хван` in its photo caption and team prose. It supports the `Чон` reading, but its spacing differs and the host is absent from registry `.3`; it cannot be treated as a registry-bound display check. The conflict therefore limits a claim of one universal Russian spelling, but does not defeat the biography's specific display evidence.

For search, retain `Пак Чжон Хван` and `Пак Чон Хван` as **documented alternate queries**, with their exact sources and provenance; do not silently rewrite either to the approved display in evidence. If an alias index is later populated, bind each spelling to player 54 only after its own identity and collision review. Do not use these aliases for name-only game association or treat them as separately approved displays. This review makes no alias-table change.

## Verification

I independently hashed the complete retained files in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/ru-sol/` and inspected the relevant body passages:

| Body | Bytes | SHA-256 |
|---|---:|---|
| `wiki-pinned.md` | 38,853 | `a7fb5e115d567456ac46ab0a9edf4f258c035d4e5280c41c841a39d8df669476` |
| `wiki-pinned-raw.html` | 505,165 | `ec6c6997d9ae91676ef272754560a582357eed9959d1d832c96020402e095853` |
| `wiki-asian-games-pinned.md` | 121,619 | `d5edc03cf904c505b84bfcf3b51eadde251645c0f221cae2bc25a441e230f323` |
| `korea-net-ru.md` | 25,115 | `4964796bf7c84e15eb4b39b058f10ee0e7d4d86feeab819e0ec3165e3a6546da` |
| `../bodies/kba_identity.md` | identity anchor | `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e` |

The positive and alternate `article_evidence.passage_sha256` values recompute from the literal strings `Пак Чонхван` and `Пак Чжон Хван`. Registry `2026-10-02.3` recomputes to canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. `research-pending.jsonl` has raw SHA-256 `3933672617f66b18d5bc5865abd13e891aed63f5d3540a4cfdc6d254a79ca33c` and canonical row SHA-256 `986b9a96a3521636bbb5200869f266e86145be10e595dba72959b9eed4070599`; `candidate-pending.jsonl` has raw SHA-256 `308003c4e184de622d0fb948e20460893363b6dab8b4c7557fc22b8de4358557` and canonical row SHA-256 `dd688860439856e5c72ca033bbc5b570ade10f3cb3e0d22876766a005adb9e1e`. The candidate's `research_sha256` equals the recomputed research hash. `scripts/kifu_name_research.py validate` exited 0 against registry `.3` on this pending research file.

This is approval of the conventional spelling judgment only. The archived candidate remains pending, has no independent approval signature or production preimage, and player 54 has no approved album link in this review. No database, registry, candidate, or alias artifact was modified.
