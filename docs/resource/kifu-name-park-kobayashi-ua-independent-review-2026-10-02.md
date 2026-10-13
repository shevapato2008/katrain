# Independent review: Park Junghwan and Kobayashi Koichi in Ukrainian

Review date: 2026-10-02. Reviewer model: GPT-6; the runtime did not expose a more specific model identifier. Scope: read-only review of producer commit `716eaf434a199def7babac6a63cd74fac14aa7d2`; no candidates or database rows were edited.

## Findings

| Player | Candidate | Independent conventional-form decision | Basis |
|---|---|---|---|
| Park Junghwan, ID 54 | `Park Junghwan` | **PASS — approve as a source-attested Ukrainian-context conventional form.** | The authored Ukrainian answer to question 6 names `Park Junghwan (Корея)` among contemporary professional Go players. The Korea Baduk Association identity capture matches Korean name `박정환 (朴廷桓)`, Korean affiliation, 9-dan and birth date 1993-01-11. |
| Kobayashi Koichi, ID 82 | `Кобаясі Коічі` | **PASS — approve as a source-attested Ukrainian conventional form.** | The authored Ukrainian answer to question 5 lists `Кобаясі Коічі` among Japanese Go masters whose books the respondent read. The Nihon Ki-in profile pairs `小林 光一` with `コバヤシ コウイチ / KOBAYASHI, Koichi`, and identifies the Japanese 9-dan born 1952-09-10. |

These decisions approve the exact spellings as conventional candidate names under the project's six-language source rule. They are based on one community Go source use each; they do not establish an official Ukrainian naming standard or broad usage frequency. For Park, the attested name is Latin-script `Park Junghwan`, not a Ukrainian-script rendering.

## Capture, registry, and text audit

- Reviewed producer commit: `716eaf434a199def7babac6a63cd74fac14aa7d2`.
- Controlled source: `https://forum.ufgo.org/viewtopic.php?p=88633`; manifest records final URL unchanged, HTTP 200, fetch time `2026-10-02T04:30:53.600481+00:00`, and 84,507 body bytes.
- Raw HTML SHA-256 recomputed from the controlled capture: `64668631b1c5da55d8bcdf85423050b57eb7b5e3aa18238fc510426634e8e5cf`, matching both manifest and the two source-check body hashes. The page declares `lang="uk"`. I inspected the surrounding answer text: both passages are authored Ukrainian responses; the Russian heading/forum chrome is separate and does not support either name.
- Park passage, exact: `Park Junghwan (Корея) сильний у всьому але у нього немає якоїсь однієї риси, яку можна було б назвати надпотужною.`
- Kobayashi passage, exact: `В основному це книги японських майстрів 80-х років - Рін Кайхо, Ісіда Йосіо, Кобаясі Коічі, Чо Чікун.`
- The archived registry snapshot parses as `2026-10-02.3`; its raw-file SHA-256 is `9e2016ac9675c44aa0bbdb304f8c5e1134a4a020d4d577c1c37890a813e0821b`, and its canonical registry hash recomputes to `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`, matching both research records. `ufgo` is registered as `language_go`, language `uk`, home `https://ufgo.org/`; the validator accepts the `forum.ufgo.org` subdomain.
- Identity-capture hashes independently recomputed and matched: Park/Korea Baduk Association `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`; Kobayashi/Nihon Ki-in `c8fc10a734da7143d0c9bf5225f32a241556ca936a8e59311dc49ee90afa6e7d`.
- `validate_research_record` passed for both records against the captured `.3` registry. Candidate `research_sha256` values match the canonical hashes of their corresponding research records, and the exact candidate names match the source passages.

## Validator and release limits

The supplied rows remain `pending`, which is correct before this independent review. They are not currently usable as a production-ready batch. Running `validate_candidate` against the available production inventory failed both rows with `entity ID/ref absent from pinned inventory and approved links`: IDs 54 and 82 have no album foreign-key links in that snapshot. Thus the producer note's statement that candidate checks pass using an explicit local allowlist is not reproducible from the archived evidence bundle; the allowlist is not included, and it does not substitute for the pinned production inventory.

The candidate rows also lack `name_preimage_sha256` and `preimage_binding`, so they cannot be write-ready. No inventory binding, approved album link, production bundle, or database write was reviewed. The PASS decisions above are limited to the linguistic and identity evidence for the two conventional names.

The capture audit verifies local bytes against the supplied hashes and manifest; it does not independently repeat the HTTP fetch or establish the poster's identity. The identity link for Park uses the exact Latin name plus the forum's Korean-player context and the official Korean profile; the forum itself gives no kanji or birth date. Kobayashi likewise has no biography in the forum post, so the match uses the Japanese Go-author context and official profile.
