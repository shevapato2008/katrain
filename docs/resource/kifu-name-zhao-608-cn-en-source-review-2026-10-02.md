# Zhao/Cho Chikun player 608: Chinese/English source review

Independent source-only review, 2026-10-02. Producer: `/root/zhao_occurrence_luna`. This review checks the captured positive name evidence and identity cross-checks only. It does not approve player ID 608 as the identity of any raw tournament slot, resolve a 2,052-slot inventory, or approve a candidate/preimage/database write.

## Result: PASS for positive source evidence

I independently fetched all four recorded URLs. Each returned HTTP 200 at the recorded final URL, and response byte counts and SHA-256 values exactly match the mode-`0600` captures and manifest:

| Source | Language/use checked | Bytes | SHA-256 |
|---|---|---:|---|
| China General Administration of Sport, Chess and Card Games Administration Center report | `zh-Hans`; directly lists `赵治勋` among the first-round players, without a rank suffix | 30,257 | `b23cbf39ccb47465d5a27fa05d041546997cfc41963f51c5d1d67e520432b682` |
| CWI Database of Go Games, Cho Chikun collection | English title and body use `Cho Chikun`; separately describes him as a Japanese Go player from Korea | 2,181 | `8ef933b0daf719a8382dddeadb1d56d9a51e52d7ee0deb02a4729e3f97a8ccd0` |
| Nihon Ki-in official player profile | Japanese official profile identifies `趙 治勲`, `CHO, Chi Hun`, 9-dan, born in Busan | 53,611 | `665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c` |
| Korea Baduk Association player profile | Korean official profile identifies `조치훈 (趙治勳)`, 9-dan, born 1956-06-20, affiliated with Japan | 31,465 | `0a17c1a56ece67066b4e79b5a54639b515dea63f4649947d5697e6bb3ac7039a` |

The two independent professional-association records corroborate the CWI subject through the Korean/Japanese name, birth date, professional rank, and Japan affiliation. The Chinese sports report supplies direct mainland simplified-Chinese name use. Its article credits Xinhua; the hosting government sports-center site and its direct article body were retrieved successfully. The Chinese occurrence has no rank suffix. On the CWI page, `Cho Chikun` is the collection heading/name; rank progression is separately stated, so rank is not part of the supported name.

The captures are mode `0600`. Their manifest records UTC fetch times in chronological order: China sports 21:38:52.096416Z, CWI 21:38:52.358546Z, Nihon Ki-in 21:38:58.836580Z, and Korea Baduk Association 21:38:59.752516Z on 2026-10-01. Registry `2026-10-02.3` canonical SHA-256 is `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`; its registered source entries match the four source IDs and URLs (`china-sport`, `cwi-go`, `nihon-kiin`, `korea-baduk`).

## Recorded discrepancy and boundary

CWI says Cho Chikun was born in Seoul. Nihon Ki-in and the Korea Baduk Association say Busan. This conflict is explicitly recorded and remains unresolved; birthplace is excluded from the identity match. No change is needed to the source finding. If birthplace is later used as an identity discriminator, it needs separate resolution from stronger biographical evidence.

This is a positive source-evidence PASS only. It does not establish that the raw spelling `赵治勋` found at a news occurrence maps to this player in a specific tournament slot. The occurrence-to-slot identity still requires its own evidence and review. The capture also does not close Chinese or English source scope.
