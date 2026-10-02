# Ukrainian 33-name syllable-rule candidates — Luna — 2026-10-03

Status: pending translation research only. No name, source segmentation, identity, signature, or database link is approved.

## Scope and chosen rule source

Read the two frozen candidate files in `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/`:

- `secondary-six-40-anchor-candidates-luna/candidates.pending.jsonl`, SHA-256 `9f63eec84481f317fe1b717b4ef88352e6c8ec75a0eb55c7e2dd49256dfb8a56` (20 candidates)
- `secondary-six-40-anchor-candidates-luna-batch02/candidates.pending.jsonl`, SHA-256 `7007d8f55683b7948afb51072fcc763b6df6c7bc8081dc9bfe2ec01ca39a9c29` (13 candidates)

The source tokens below follow each pending anchor's `reading_words` (`pinyin-syllables-v1`) exactly; this work did not independently verify the candidate's Chinese reading or segmentation. The batch uses all 60 distinct tokens and the selected reference has an explicit table entry for each.

Primary rule reference: [Academic system for transcribing Chinese words and proper names into Ukrainian](https://chinese-studies.com.ua/pinyin_to_ukrainian_26.06.2019.pdf), body SHA-256 `6ac441c5784986b9c127d8db94f83010e49807c0a8f177a6b2fa73391283c0ab`. The document states it was approved on 2019-06-26 by the Academic Council of the A. Yu. Krymskyi Institute of Oriental Studies, National Academy of Sciences of Ukraine. It says Chinese surname and given name are written separately, in surname-first order (examples include `Лі Дачжао`), and provides pinyin-to-Ukrainian syllable correspondences. It describes the method as transcription, not mechanical transliteration from pinyin letters. Accordingly this proposal uses the Ukrainian table itself, including `qiu → цю`, `jun → цзюнь`, `ge → ґе`, `yi → ї`, and `zhao → чжао`; it does not reuse Russian Palladius spellings.

The pending artifact `uk-33-candidates.pending.json` in the protected packet contains the full `syllable_map_v1`, all 33 source readings, candidate parts/displays, input hashes, and collision report. Proposed rendering keeps the supplied surname/given grouping: surname + space + given name; syllables within a two-syllable given name are joined as in the reference's `Лі Дачжао` example. No tone marks are added because source readings are tone-free published Roman forms.

## Pending scoped displays

| Chinese | Pending source reading | Ukrainian display candidate |
|---|---|---|
| 邱峻 | Qiu Jun | Цю Цзюнь |
| 彭荃 | Peng Quan | Пен Цюань |
| 牛雨田 | Niu Yutian | Ню Юйтянь |
| 宋容慧 | Song Ronghui | Сун Жунхуей |
| 王群 | Wang Qun | Ван Цюнь |
| 吴肇毅 | Wu Zhaoyi | У Чжаої |
| 安冬旭 | An Dongxu | Ань Дунсюй |
| 廖桂永 | Liao Guiyong | Ляо Ґуйюн |
| 宋雪林 | Song Xuelin | Сун Сюелінь |
| 佟禹林 | Tong Yulin | Тун Юйлінь |
| 岳亮 | Yue Liang | Юе Лян |
| 李鑫怡 | Li Xinyi | Лі Сіньї |
| 李亮 | Li Liang | Лі Лян |
| 邱金波 | Qiu Jinbo | Цю Цзіньбо |
| 丁波 | Ding Bo | Дін Бо |
| 公彦宇 | Gong Yanyu | Ґун Янюй |
| 谷宛珊 | Gu Wanshan | Ґу Ваньшань |
| 金茜倩 | Jin Qianqian | Цзінь Цяньцянь |
| 曾志豪 | Zeng Zhihao | Цзен Чжихао |
| 程宏昊 | Cheng Honghao | Чен Хунхао |
| 高恬亮 | Gao Tianliang | Ґао Тяньлян |
| 王思尹 | Wang Siyin | Ван Сиїнь |
| 王香如 | Wang Xiangru | Ван Сянжу |
| 李必奇 | Li Biqi | Лі Біці |
| 于富霖 | Yu Fulin | Юй Фулінь |
| 于浩然 | Yu Haoran | Юй Хаожань |
| 汪美成 | Wang Meicheng | Ван Мейчен |
| 王超 | Wang Chao | Ван Чао |
| 李魁 | Li Kui | Лі Куй |
| 葛凡帆 | Ge Fanfan | Ґе Фаньфань |
| 袁曦 | Yuan Xi | Юань Сі |
| 高逸典 | Gao Yidian | Ґао Їдянь |
| 范炳旭 | Fan Bingxu | Фань Бінсюй |

## Rule scope, collisions, and exceptions

Every token in these 33 anchors is covered by the selected table: 60/60 mapped; no unsupported token was invented or held. The exact token-to-output dictionary is included in the pending JSON artifact. Candidate displays are unique within this batch (33 distinct outputs; no collisions).

A secondary Ukrainian-language table, [Ча Дао transcription table](https://teahut-com-ua.github.io/library/articles/chinese-symbols-table/), body SHA-256 `053ae02182b307dcd6421b1ba8538b61b2614c3375c0aebbb0117d557de3214ac`, describes the expert seminar and cautions against mechanical transfer of Russian Palladius. Its transcription proposals are not identical in every syllable to the approved 2019 PDF: for example its `j` series uses `дз`, while the approved PDF maps `jun` through `цз`. Since `jun` is present in 邱峻, this creates a concrete variant `Дзюнь` versus the selected-table candidate `Цзюнь`; retain this as a reviewer-visible standard choice, not a hidden normalization. The approved PDF's explicit status was preferred for this pending proposal.

The [Ukrainian orthography reference](https://spelling.ulif.org.ua/ptr_1.htm), body SHA-256 `8d695a7ad811854c138ede25806666257a0043b07380b134aa2f8bcc356a66b2`, confirms Chinese family names and following complex given names are capitalized in examples such as `Мао Цзедун`, but represents a different, established spelling tradition. A [peer-reviewed article on Chinese transcription in Ukrainian](https://chinese-studies.com.ua/index.php/journal/article/view/99), body SHA-256 `b5f32d24585b00c5d50564f714f2b4946782f7c262b2ab25a431e02b73496766`, discusses the lack of a consistently unified standard in earlier Ukrainian usage. Thus these output forms are explicitly tied to the selected system, not claimed as the only Ukrainian spellings.

No conventional Ukrainian Go-player-name exception was evidenced for these 33 names in the bounded search. This is not proof none exist. `Zeng` for 曾 and the readings inside multi-character given names are inherited from the pending pinyin anchor; polyphonic-character readings and player-preferred Ukrainian forms remain outside this rule pass. No alternative forms were silently substituted. Review `Цзюнь`/`Дзюнь` and the remaining displays before any approval.

## Protected packet

Captured source bodies, `ua-33-candidates.pending.json`, and a hash manifest are in `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/ukrainian-33-rule-luna/` (directory mode 0700; files mode 0600). The pending JSON SHA-256 is `04baf95b1233f02afd4e7e6d28990908263b8ef5e57082432447634718475fd4`; manifest records body URLs, languages, sizes, and hashes. No code or DB files were changed.
