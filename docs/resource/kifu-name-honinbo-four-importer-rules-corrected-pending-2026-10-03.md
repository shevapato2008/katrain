# Honinbo: four held importer rules corrected, pending independent review

The [partial independent review](kifu-name-honinbo-composition-partial-independent-review-astra-2026-10-03.md) approved the 34 raw-category declarations, finite scope and seven importer-format rules, but held `en cn jp de` for source-capture provenance. This new producer packet corrects **only those four rule content records**. Their series/base dependencies, locale styles, retained source URLs and body SHA-256 values, and all 34 rendered displays per language are unchanged. It signs no rule and does not regenerate the 374 candidates.

Protected packet: `/Users/fan/.local/share/kifu-name-audit/2026-10-03/honinbo-four-rule-correction/` (`0700`; files `0600`). Producer `/root/honinbo_final_candidates`, runtime model `inherited/unverified`; authentic packet production start `2026-10-02T18:02:05.135540Z`. The corrected `approval.status` is `pending` for every rule and contains no reviewer identity.

| Artifact | Byte SHA-256 |
| --- | --- |
| `honinbo-four-importer-rules-v2.pending.json` | `42731d807d38162886690073f5f2e7595120c2c0b6565db8622977e0cb9cb7e3` |
| `manifest.json` | `03ee8225ded11eda7e49cdd762c8eb93943c6f69f10dc306c5990decdb0ad95b` |
| `recapture-manifest.json` | `f90467d374c24dacfc169200925d1855aba96a7b12a46194ed154614b135efec` |

| Locale | Prior held importer-content SHA-256 | Corrected pending importer-content SHA-256 |
| --- | --- | --- |
| `en` | `71fbd57f715fd569c7fdf43abf4386dac616d59b32bb3f795fd7e2af6195f820` | `bea590bfee950338f754dc9133c4fe591f456dfb3ea04621a7a7546e5646291f` |
| `cn` | `7515116403847390ffed9825b878afe068944878da29e32c5aa0a69819844e6d` | `d1e39bc8999663eb75245275eac0e5ff3cad6e5a4f43f24bcbd24dd9866be9ac` |
| `jp` | `f7957fe688670d60ca3a6e34adfaefa465d5ab55e6ec3c1293467742711dc4b1` | `5f30fd40682f1c0ef2fac9f2fb46de2805ffe174f4b6b12f06e396494fd74a9d` |
| `de` | `5b822e514d22ed3b71048e4d015c79b6ed193228bf52ac63de1be7ac341950ea` | `a0bbdf972f8e40c9d08f62283058cb056c6a2ef8da7c70f92814d9d539f77d30` |

The English first-edition CWI body and Japanese official archive body reuse matching actual `fetched_at` receipts from the retained [v2 source-evidence capture](kifu-name-honinbo-v2-source-evidence-2026-10-02.md): `2026-10-02T14:39:46.990141Z` and `2026-10-02T14:39:38.553547Z`. Their body hashes and URLs match the original rule sources exactly. The other five sources were fetched again over HTTPS, with request start and response-read completion recorded separately. Each returned HTTP 200 and **byte-identical content** to its previously reviewed body: CWI editions 17/34, Kihuu Chinese, Igo Kifu Japanese, and German Wikipedia. The new `captured_at` fields use those actual response-read completion times on `2026-10-02T18:00:32–33Z`; no time was retroactively assigned to an old body. The German retained/recaptured HTML contains `wgRevisionId: 227470618`, now pinned as `content.sources[0].revision`.

The builder verified each retained/new body hash and URL, exact receipt binding, unchanged fields other than seven capture times and the German revision, and unchanged 1–34 rendered outputs for each locale. Repeat build produced the same packet and manifest bytes. Focused source-schema checks accepted all four rule source lists and recomputed all four content hashes. The seven previously signed rules, 34 category declarations and signed scope remain in the independent review artifact; this packet does not alter them. The existing 374 pending rows still bind the **old unsigned rule envelopes** and predate these corrections, so they must not be reviewed as final candidates. After independent signatures on these four exact corrected content hashes, fresh candidate production and current database preimage binding remain necessary. No clone, test or production database write, SGF change or deployment occurred.
