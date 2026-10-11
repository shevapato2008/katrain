# NIKL Chinese-to-Korean rule research

**Status:** source findings for later review. This packet does not approve a product naming rule or generated player name.

## Official current rule

The National Institute of Korean Language’s current *Foreign Language Transliteration Rules* says contemporary Chinese personal names are, in principle, written under the Chinese transcription rules; historical people are written using the established Sino-Korean reading. The Chinese rule says tones are not distinguished in Hangul and supplies a Hanyu Pinyin/Bopomofo-to-Hangul initial and final table. It also has a specific vowel adjustment after ㄐ, ㄓ, ㄗ, ㄑ, ㄔ, ㄘ. The full directly captured rule page contains all of these clauses and tables:

- [Complete current rules: Pinyin/Hangul table, Chinese-specific clauses, and names principle](https://korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003)
- Raw response: `captures/foreign-regulation-full.html`
- HTTP 200; fetched `2026-10-08T21:30:16Z`; 456,809 bytes; SHA-256 `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b`

The table confirms these ordinary Mandarin surname readings **when the supplied pinyin is verified as Hanyu Pinyin**. Some are explicit table entries; the others are compositions of the official initial and final entries:

| Hanzi | Verified Hanyu Pinyin | Official table entries | Hangul derivation |
|---|---|---|---|
| 王 | Wáng | `wang (uang) → 왕` | 왕, explicit final entry |
| 黄 / 黃 | Huáng | `h → ㅎ`; `uang` is listed as the final of `wang (uang) → 왕` | 황, composed from official entries |
| 陈 / 陳 | Chén | `ch → ㅊ`; `en → 언` | 천, composed from official entries |
| 谢 / 謝 | Xiè | `x → ㅅ`; `ie` appears as `ye (ie) → 예` | 셰, composed from official entries |
| 赵 / 趙 | Zhào | `zh → ㅈ`; `ao → 아오` | 자오, composed from official entries |
| 徐 | Xú | `x → ㅅ`; pinyin `u` after `x` is represented by `yu (u) → 위` | 쉬, composed from official entries |

These are rule-derived spellings, not evidence that a particular person uses that form. Pinyin tone marks are not reproduced in Hangul, as the Chinese-specific rule expressly says tones are not distinguished.

The general spacing clause says a form separated in the original may keep that separation in Hangul, **or may be joined**. This is a general foreign-word spacing rule, not a special personal-name convention; it does not by itself choose a display format for a particular player.

## Identity and romanization limits

NIKL’s answer to a question about overseas Chinese names says there is no clearly defined separate transcription standard limited to overseas Chinese people. In the absence of a separate rule, it directs writers to the person’s actual language and pronunciation, and to how the person or close associates say the name. That makes automatic Mandarin transcription inappropriate where the person uses another language or pronunciation.

- [NIKL guidance on overseas Chinese personal names](https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=&pageIndex=1&qna_seq=328375)
- Raw response: `captures/nikl-chinese-diaspora-name-guidance.html`
- HTTP 200; fetched `2026-10-08T21:30:19Z`; 86,002 bytes; SHA-256 `75f6b4f4ad61654f3a0f72aac9bbfc03eb57f76bebcb99738476be007f51af9b`

NIKL also says it does not separately regulate whether Chinese characters are simplified or traditional; its dictionary’s use of traditional characters is editorial guidance, not a mandatory script rule.

- [NIKL guidance on simplified/traditional character choice](https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=261&pageIndex=1&qna_seq=325065)
- Raw response: `captures/nikl-simplified-traditional-guidance.html`
- HTTP 200; fetched `2026-10-08T21:30:22Z`; 93,690 bytes; SHA-256 `f52bdf67b89693ff519f06c5e30e036fbb91845a450790288f36eb218fd8bb15`

Operational limit: use the table only after a reliable source verifies Mandarin and the Hanyu Pinyin reading. English romanization alone does not establish the romanization system. Forms such as **Chun/Chung** remain on hold until their pinyin and actual reading are independently established; do not silently reinterpret them as Hanyu Pinyin. This hold is a conservative research boundary, not a special NIKL rule.

## Captured sources

All actual URLs, request descriptors, HTTP status, capture timestamps, byte counts, content types, and SHA-256 values are in [`capture-index.json`](capture-index.json). The Chinese rule body was freshly fetched; the existing Japanese NIKL capture packet is cited in `rule-findings.json` only as Japanese-specific evidence and is not used to establish Chinese conversion.
