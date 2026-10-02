# Source registry `.7` candidate

Producer: GPT-6, `/root/ja21_independent_review`. This is a proposed immutable registry snapshot for independent review. It does not approve an individual source capture, name, identity or import.

Generated [kifu-name-source-registry-2026-10-02.7.json](kifu-name-source-registry-2026-10-02.7.json) from the immutable [.6 snapshot](kifu-name-source-registry-2026-10-02.6.json). Only the version, description and ten appended source entries change. All **39 existing source entries, eleven language tags, eleven language scopes and their search plans remain identical**; every negative-claim completeness flag remains false. The default `kifu-name-source-registry.json` is unchanged.

| Added source ID | Real host / starting path | Source language | Tier and basis |
| --- | --- | --- | --- |
| `goratings-zh` | `www.goratings.org/zh/` | `zh` | `language_go`; Chinese edition of one GoRatings publisher. |
| `goratings-ja` | `www.goratings.org/ja/` | `ja` | `language_go`; Japanese edition of that same publisher. |
| `goratings-ko` | `www.goratings.org/ko/` | `ko` | `language_go`; Korean edition of that same publisher. |
| `goratings-en` | `www.goratings.org/en/` | `en` | `language_go`; English edition of that same publisher. |
| `nihon-kiin-archive-jp` | `archive.nihonkiin.or.jp/` | `ja` | `official`; Nihon Ki-in archive Japanese pages and profiles. |
| `nihon-kiin-archive-en` | `archive.nihonkiin.or.jp/match/oza/061-e.html` | `en` | `official`; retained English archive starting page, same Nihon Ki-in publisher. |
| `weiqi-association-culture` | `wqwh.weiqi.org.cn/` | `zh-Hans` | `official`; China Weiqi Association culture/teaching subsite. Article attribution and capture transport remain separate checks. |
| `foxwq-cn` | `foxwq.com/` | `zh-Hans` | `language_go`; commercial specialist Go platform/reporting, including the cited `www` host. |
| `cna-tw` | `www.cna.com.tw/` | `zh-Hant` | `reference`; Central News Agency Taiwan reporting, not a Go organizer. |
| `sina-sports-cn` | `sports.sina.com.cn/` | `zh-Hans` | `reference`; Sina editorial sports reporting and player pages. |

All ten entries correspond to retained sources already cited in this round. The four GoRatings editions are retained with the same player ID and actual HTML languages in `high-volume-player-next11-root/manifest.pending.json` (for example ID `30`). GoRatings identifies its ranking data providers on its [own English page](https://www.goratings.org/en/); it is registered as a Go reference publisher, not an association authority. The archive Japanese/English pages and FoxWQ article are retained in `oza-five-source-pending-root/manifest.pending.json`: [Japanese archive](https://archive.nihonkiin.or.jp/match/oza/index.html), [English archive](https://archive.nihonkiin.or.jp/match/oza/061-e.html), [FoxWQ article](https://www.foxwq.com/news/listid/id/7453.html). FoxWQ's retained article attributes its text to Sina: this is a reprint, not an independent report.

CNA's [retained article](https://www.cna.com.tw/news/aspt/202411080075.aspx) and the association culture bodies are indexed in the high-volume next11 authority/supplement manifests. The association's [main site](https://www.weiqi.org.cn/) and [culture rules site](https://wqwh.weiqi.org.cn/rules/) identify the association publication; the retained culture HTML declares `zh-Hans` and the association footer. Publisher classification does not resolve the three retained culture bodies' explicit `tls_verified=false`: their transport limitation remains. No fresh verified raw body or successful local TLS capture is claimed by this registration. The [Sina 2017 article](https://sports.sina.com.cn/go/2017-08-30/doc-ifykkfat2688853.shtml) is retained with a verified body hash in the TW next20 replacement packet. None of the media publishers is assigned an official association tier.

## Schema and validator findings

Inspected `load_registry`, `_source_url_matches`, `_matches_target`, `_validate_check`, `validate_research_record` and the existing source-plan/registry tests before creating the file.

- `load_registry` checks unique IDs, HTTPS home URLs, nonempty tier/language and language-scope references. It accepts metadata notes; those notes do not create enforcement.
- The URL matcher checks the exact registered host or its subdomains. **It ignores paths.** GoRatings language-specific home URLs and notes describe the intended source editions, but do not make `/ja/` and `/ko/` mutually exclusive gates. A focused direct check confirms that the `goratings-ja` entry still accepts a `/ko/players/30.html` URL at host level. Source records must retain and independently review their exact language path, numeric profile ID, body hash and actual page language.
- Completed evidence checks require actual page language to match the target, but do not require it to match `source.language`. GoRatings `zh` is preserved as declared; it fails automatic `zh-Hans` and `zh-Hant` matching. Registration does not convert it into script-specific evidence or approve a glyph conversion.
- The archive contains Japanese and English pages at the same host; separate entries record these source languages, while notes explicitly identify their common publisher. GoRatings editions are also one publisher; they cannot count as independent publisher corroboration.
- `foxwq.com` covers the cited bare and `www` hosts under the existing matcher. `sports.sina.com.cn` does **not** cover sibling `sports.sina.cn`, `k.sina.cn`, or arbitrary Sina subdomains. Those sibling hosts remain outside this exact entry.
- Research records continue to bind the exact registry version and canonical content hash. `.6` evidence signatures are preserved; this candidate does not re-pin, migrate or self-approve earlier evidence. Adding these sources to the registry does not add them to the unchanged required search scopes.

No application-code change is proposed. These limitations must remain visible when a future evidence/import packet uses `.7`.

## Validation and hashes

`load_registry` successfully loaded `.7` with 49 unique sources. Direct comparisons confirmed all original sources, tags, scopes and all eleven `source_plan` results are identical to `.6`. Focused checks confirmed the intended host coverage, the noncoverage of Sina sibling hosts, neutral `zh` language behavior and the existing host-only path limitation.

Executed existing tests:

```text
.venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_evidence.py -k 'repository_source_registry or product_language_mapping or source_plan or record_is_bound_to_exact_registry_contents or a_found_name_requires_url_real_body_and_actual_target_language or capture_rejects_page_language_fallback or found_record_stays_pending'
17 passed, 88 deselected in 0.04s
```

The repository-default-registry test remains a check of the unchanged default file; the new `.7` is covered by the explicit `load_registry` and preservation comparisons above.

| Artifact | SHA-256 |
| --- | --- |
| `.7` raw JSON bytes | `e6ece1699371d54d719e8333cec2fa571c5fc6bb913f71815f0139399b2b591f` |
| `.7` canonical `registry_sha256` | `e7470d52d26b006a3eb7e799cf649857214e10eb35e565ecf5c269a8987b669a` |
| Immutable `.6` raw bytes | `7b857caa5a8058d198cf46ca6fb92eb07a664b0491aa6fe06a83130eaa6393a2` |
| Unchanged default raw bytes | `9a3b3bd517e85f6822d2edd55bc06816bd202919c72214d91a8b7f8a1fd7b7f5` |

No DB access/write, deployment or commit was performed.
