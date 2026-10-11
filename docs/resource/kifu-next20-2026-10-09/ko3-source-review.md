# KO3 source and NIKL review request

Unsigned, producer /root/restore_tw_twenty; captured research SHA-256 `6f9ff419993a588268fcfcba06d8aa6bb6378a654737fc64e59978e8fef7ec97`. Root reviews source and rule before fresh TEST/PROD owner binding.

| ID | Original → full kana → KO candidate | Games | Japanese identity/reading sources | Bounded conflict query hits |
|---:|---|---:|---|---|
| 5396 | 浜中隆光 → はまなか たかみつ → 하마나카 다카미쓰 | 12 | [Japan Go Association](https://www.nihonkiin.or.jp/player/htm/ki000173.html); [Igo compact profile](https://www.igorating.com/players/takamitsu-hamanaka) | original 0, candidate 1 |
| 4276 | 奥村靖 → おくむら やすし → 오쿠무라 야스시 | 9 | [Japan Go Association](https://www.nihonkiin.or.jp/player/htm/ki000240.htm); [Igo compact profile](https://igorating.com/players/yasushi-okumura) | original 0, candidate 2 |
| 4782 | 明戸和巳 → あけど かずみ → 아케도 가즈미 | 9 | [Japan Go Association](https://archive.nihonkiin.or.jp/player/htm/ki000129.htm); [Igo compact profile](https://www.igorating.com/players/kazumi-akedo) | original 0, candidate 0 |

NIKL official rule pages: [Japanese personal names, Chapter 4 Section 2 Article 3](https://korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000146); [Japanese kana table](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000108); [Japanese transcription details](https://www.korean.go.kr/front/page/pageView.do?mn_id=97&page_id=P000129). Actual raw page captures were retained in `../kifu-next-throughput-2026-10-09/reused-NIKL-three-page-captures.json` and included in each pending research record.

- 浜中：は→하, ま→마, な→나, medial か→카; initial た→다, medial か→카, み→미, つ→쓰.
- 奥村：お→오, medial く→쿠, む→무, ら→라; や→야, す→스, し→시.
- 明戸：あ→아, medial け→케, ど→도; initial か→가, ず→즈, み→미.

Igo retains exact compact Japanese names required by the current validator; the Japan Go Association pages independently show the same full kana and person context with spaces in their name headings. The two actual Naver queries per person are bounded conflict checks, not a publication or universal absence claim. Same-spelling candidate results: 浜中 Namu Wiki tournament bracket; 奥村 Hangame Go directory and Namu Wiki bracket; 明戸 none. No different Korean spelling was found in these six captured first pages.

Files: `ko3-actual-source-captures.json.gz` (raw source and search responses), `ko3-unsigned-research.json.gz` (native-validator-passing pending records), `ko3-source-rule-review-request.json` (hashes and review request). No preimage binding, reviewer signature, SQL, or Git mutation.
