# Judan English source repair (2026-10-02)

This is a new, one-row pending English research artifact for `event:@judan-series-2026-10-02`, original name `十段戦` (`ja`). It replaces no earlier artifact and contains no approval signature.

The registered English Go source is the CWI archive index, [SGF records of Japanese professional go games](https://homepages.cwi.nl/~aeb/go/games/games/index.html). In its `Tournaments` / `name period` table, the exact standalone entry is `Judan (1962-2026)`. The page title identifies its collection as Japanese professional Go games; the table identifies `Judan` as a recurring tournament series. This supports the exact English display form `Judan` directly.

Separate identity capture: the registered [Nihon Ki-in 64th-edition page](https://www.nihonkiin.or.jp/match/jyudan/064.html), HTML language `ja`, labels the event `第64期 十段戦`, gives the formal series name `大和ハウス杯十段戦`, and lists the Nihon Ki-in, Kansai Ki-in, and Sankei Shimbun as organizers. Captures and exact excerpts are retained in the protected directory below.

## Controlled artifact

Protected files are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-en-repair/` (directory mode `0700`, files mode `0600`): raw HTML bodies, `capture-manifest.json`, `research.pending.jsonl`, and `research.validated.jsonl`.

- CWI response: HTTP 200, observed language `en` by reviewed page text (the HTML has no `lang` attribute), body SHA-256 `388e0f1434799d941720cadf5cfc9d9ee10409f280a785d3af0c8fa5fd4c741a`.
- Nihon Ki-in response: HTTP 200, observed language `ja` by HTML `lang`, body SHA-256 `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78`.
- Canonical registry SHA-256 (`2026-10-02.5`): `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`.
- Pending JSONL SHA-256: `2b02297da55b49c9802e18011eb8207cfcb7cdde6b6a2e0d6452e660aa424492`.
- Capture manifest SHA-256: `8db9e053e87db05d39cc27710cf23711f909c56edcf66341edbe7443e2e3bdcc`.
- Validated JSONL SHA-256: `de1ad42a0ee49e320d98233d91e9cd0eed75dfdaeb65aa7484c3f410aac512ea`.

Validation completed successfully:

```sh
python scripts/kifu_name_research.py --registry docs/resource/kifu-name-source-registry-2026-10-02.5.json validate \
  --input /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-en-repair/research.pending.jsonl \
  --output /Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-en-repair/research.validated.jsonl
```

The row remains `pending`. Producer model is recorded as parent-configured `gpt-6-luna` (high reasoning); runtime model identity is not independently attested. No candidate signature, database write, or commit was made.
