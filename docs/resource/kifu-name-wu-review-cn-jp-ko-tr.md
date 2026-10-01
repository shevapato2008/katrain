# Independent review: Wu Qingyuan ID 1 candidates (cn/jp/ko/tr)

Review timestamp: 2026-10-01T19:22:27Z  
Reviewer agent ID: `/root/lee_sources_luna`  
Reviewer model: `gpt-6-luna`  
Producer: `codex-wu-capture-2026-10-02` (`gpt-6-luna`)  
Owner under review: player ID 1, Wu Qingyuan / 吳清源

This is an independent research review memo only. It does not modify the pending candidate/evidence JSONL files and is not a database approval signature or authorization to import.

## Decisions

| Language | Candidate | Review conclusion | Basis |
|---|---|---|---|
| `cn` | `吴清源` | **Approve** | China’s General Administration of Sport article is Simplified Chinese and uses this exact name in its headline and body. It identifies a Go master born in Fujian, describes his Japan/Kensaku Segoe professional career, 9-dan promotion, and famous jubango record. This is a strong target-language source and a clear professional identity match. |
| `jp` | `呉清源` | **Approve** | The Nihon Ki-in official profile’s exact heading is `呉 清源（ゴ セイゲン / WU, Qing Yuan）`; the same page gives 9 dan, Fujian origin, career and 30 November 2014 death. This directly supports both Japanese spelling and identity. |
| `ko` | `우칭위안` | **Approve** | The Korean Baduk Association official player profile’s heading is `9단 우칭위안(오청원) (呉淸源)`, with Japanese affiliation and professional rank. This supports the proposed preferred name and independently records `오청원` as an alternate. The Korean Go outlet Cyberoro also uses `우칭위안` in a substantive centenary feature. Preference follows the association’s main heading, consistent with the policy decision. |
| `tr` | `Go Seigen` | **Approve** | The Turkish Istanbul Go School article contains the exact phrase `Büyük usta Wu Qingyuan (Go Seigen)` in a substantive Go discussion. The Turkish Asialogy article is headed `Go Seigen kimdir?` and its body says `Wu Qingyuan ya da batıda bilinen adıyla Go Seigen`, then provides biographical and professional-Go context. The Nihon Ki-in profile’s reading `ゴ セイゲン / WU, Qing Yuan` ties the two forms to the same professional. This is an established Latin form used in Turkish prose, not an inferred Turkish transliteration. |

## Re-fetch and identity checks

- [Simplified Chinese sports authority obituary](https://www.sport.gov.cn/n20001280/n20745751/n20767277/c21440500/content.html), fetched 2026-10-01: lines 24–30 give the headline `围棋大师吴清源…`, identify him as a Go master, describe his Fujian birth, Japan career, professional 9 dan and jubango record. The page is visibly Simplified Chinese (`lang` was manually reviewed in the original capture). The captured source response SHA-256 `93674aa5…f0624e` exactly matches a fresh HTTP 200 response.
- [Nihon Ki-in official profile](https://www.nihonkiin.or.jp/player/htm/ki001001.htm), fetched 2026-10-01: lines 26–45 show the exact Japanese form and reading, 9 dan, Fujian origin, career and death date. The captured SHA-256 `2abec7ca…e0a94` exactly matches a fresh HTTP 200 response.
- [Korean Baduk Association official profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=20001138), fetched 2026-10-01: lines 2–15 show the exact headline, primary and alternate Korean forms, Hanja, Japanese affiliation and 9 dan. The captured SHA-256 `1c46e4ae…533df2` exactly matches a fresh HTTP 200 response. [Cyberoro feature](https://www.cyberoro.com/news/N_news_view.oro?cmt_n=0&div_no=A1&num=519273&pageNo=1), fetched 2026-10-01, uses `우칭위안` in its headline, body, and game-record captions; it also uses `오청원` in a photo caption. Its body calls him a leading figure in modern Go and discusses his professional career.
- [Istanbul Go School article](https://www.gookulu.com/go_oyunculari_ve_akis/), fetched directly 2026-10-01: HTTP 200; the Turkish text says `Büyük usta Wu Qingyuan (Go Seigen)` while discussing Go’s philosophy. Its captured source SHA-256 `b0447606…bf2ae` exactly matches the fresh response.
- [Asialogy Turkish biography](https://www.asialogy.com/go-seigen-kimdir/), fetched 2026-10-01: the heading is `Go Seigen kimdir?`; body lines 96–103 identify `Wu Qingyuan` as `Go Seigen`, give birth date 19 May 1914, professional status, career and Go contributions. The captured response SHA-256 does **not** match the current live response, indicating this page changed since capture. The captured excerpt includes the exact title but not the full biographical passage; therefore I count this page as supplementary naming evidence, not as the sole identity basis. The Go School excerpt/hash and official Nihon Ki-in identity profile independently support the Turkish candidate.

The Japanese official record gives 19 May 1914; the Chinese obituary reports 12 June 1914. I do not use birth date to adjudicate the match. The Japanese profile’s exact name and romanized reading, together with the professional career markers repeated in Chinese and Korean Go sources, are sufficient. The Korean Association profile lists a 9-dan promotion date that differs from the Nihon Ki-in chronology; that date is not used as identity evidence.

## Capture provenance and limits

- The evidence JSONL file SHA-256 is `ed04126e…d5790`; the candidate JSONL file SHA-256 is `43aeb698…dac3c` (full hashes can be recomputed from the controlled files).
- For all four rows, the candidate `research_sha256` exactly equals the canonical SHA-256 of its matching evidence record. Each evidence row carries owner `{kind: player, id: 1}`, producer ID/model, capture time, pending status, registry version `2026-10-02.2`, and registered source IDs/URLs.
- The registry fingerprint recorded in those rows, `e2ed3cafa9b6f32d8ba30c78aecdf9667801df3cf34745227e5da588e98dd58e`, matches the canonical SHA-256 of the checked-in registry at review time. The three non-Turkish source response hashes and the Go School source hash were reproducible from fresh HTTP 200 responses; the Asialogy live body hash was not, as described above.
- These decisions concern the four names only. They do not establish eleven-language coverage, validate all game links for player ID 1, or authorize any DB write. The Turkish capture should be refreshed with a complete passage and current body hash before it is relied on by a formal batch validator; the direct Go School passage still supports the candidate in this review.
