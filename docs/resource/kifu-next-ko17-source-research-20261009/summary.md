# First five: source-only Korean-name research

Queue order is by `slots` descending. These five are still shortlist entries, not final qualification decisions. No Korean transliteration was inferred and no candidate was approved.

| PROD ID | Han name | Source-published Latin | Finding |
|---:|---|---|---|
| 6531 | 黄家胤 | Huang Jia-Yin | Taiwan Go / Haifong identify the player; searches and saved Korean rosters yielded no direct Korean form. |
| 5806 | 萧睿杉 | Wesley Hsiao | Taiwan Go / Haifong identify the player; Naver exact Han query explicitly returned no results. |
| 5115 | 杨以伦 | Yang Yilun | U-Go / GoRatings identify the same Go professional; Korean Go pages use “Yang Yilun” in Latin, not Hangul. |
| 5214 | 柯沛辰 | Ke Peichen | GoRatings / Haifong identify the same Taiwanese professional; no Korean Go name found. |
| 5543 | 王紫涵 | Wang Zihan | GoRatings identifies the player; Korean search results returned unrelated player names, no same-person form. |

## Capture handling

- Actual authority-page and search response bodies are in `captures/`; the JSON indexes record exact URL, request method, HTTP status, fetch time, body length, SHA-256, body path, excerpt and locator.
- The authority-page captures are exact name/identity sources. Naver/Bing pages are bounded discovery captures, not proof of global absence.
- Reused KBA, TVBaduk and Daum response bytes are referenced in each owner record with their original capture timestamps and hashes. Daum is a 2012 community list, not an official name authority.
- GoRatings Korean-path checks for 5115, 5214 and 5543 returned HTTP 200 but displayed English-name headings (`Yang Yilun`, `Ke Peichen`, `Wang Zihan`); those are recorded as English fallbacks, not Korean names.
- `KO` remains pending for all five. Their Latin spellings are recorded as published forms; the source packets do not establish a Korean reading or Hangul spelling. Further rule work is separate.
