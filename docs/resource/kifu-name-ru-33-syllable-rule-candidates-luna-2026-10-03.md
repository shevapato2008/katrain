# Russian transcription candidates for the 33 Chinese players

**Status: pending and unsigned. Prepared by GPT-6 Luna.** This is a finite proposal for the 33 pending English-reading anchors, not approval of their readings, Russian names, or a production rule.

## Sources and rule

The [Palladius table](https://cidian.ru/palladius) identifies itself as a Pinyin-to-Russian table for the Palladius system. I retrieved its raw HTML with HTTP 200 and retained the bytes; SHA-256 is `942c4f4b633939c1da9facfd29c00cfe4e04a549410bd3833f5681ed92a9b6ab`. The proposed map contains the 60 distinct Pinyin syllable tokens present in these 33 pending records. It follows the table’s spelling per syllable, joins syllables within the supplied surname or given-name component, keeps a space between those components, and capitalizes each component. It does not add tone marks.

The [Go Federation-associated “Who Is Who / World” GoLib page](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html) is a community encyclopedia of foreign Go specialists. Its indexed page text directly pairs **Цю Цзюнь (Qiu Jun)** and **Пэн Цюань (Peng Quan)** with China. These agree with the proposed token map. I could not retrieve the original page body: direct HTTP and browser navigation timed out, and Firecrawl returned an insufficient-credit error. Therefore its raw-body SHA-256 is unavailable; the packet records a separate hash for the retained web-index excerpt. Only those two spellings are marked as directly attested Russian Go-directory forms. Every other emitted string below is a rule-generated candidate, not a verified conventional name.

The table gives `hui` as both `хуэй` and `хой`, without a selector. **宋容慧 / Song Ronghui is held** rather than choosing a variant. The other 32 names have token-complete generated candidates. The English forms are the pending source readings from the earlier anchor packets; they are not treated as Russian conventions.

## Pending display candidates

| Han name | Published English reading | Russian candidate |
|---|---|---|
| 邱峻 | Qiu Jun | Цю Цзюнь — GoLib-attested |
| 彭荃 | Peng Quan | Пэн Цюань — GoLib-attested |
| 牛雨田 | Niu Yutian | Ню Юйтянь |
| 宋容慧 | Song Ronghui | **HOLD: `hui` has two table forms** |
| 王群 | Wang Qun | Ван Цюнь |
| 吴肇毅 | Wu Zhaoyi | У Чжаои |
| 安冬旭 | An Dongxu | Ань Дунсюй |
| 廖桂永 | Liao Guiyong | Ляо Гуйюн |
| 宋雪林 | Song Xuelin | Сун Сюэлинь |
| 佟禹林 | Tong Yulin | Тун Юйлинь |
| 岳亮 | Yue Liang | Юэ Лян |
| 李鑫怡 | Li Xinyi | Ли Синьи |
| 李亮 | Li Liang | Ли Лян |
| 邱金波 | Qiu Jinbo | Цю Цзиньбо |
| 丁波 | Ding Bo | Дин Бо |
| 公彦宇 | Gong Yanyu | Гун Яньюй |
| 谷宛珊 | Gu Wanshan | Гу Ваньшань |
| 金茜倩 | Jin Qianqian | Цзинь Цяньцянь |
| 曾志豪 | Zeng Zhihao | Цзэн Чжихао |
| 程宏昊 | Cheng Honghao | Чэн Хунхао |
| 高恬亮 | Gao Tianliang | Гао Тяньлян |
| 王思尹 | Wang Siyin | Ван Сыинь |
| 王香如 | Wang Xiangru | Ван Сянжу |
| 李必奇 | Li Biqi | Ли Бици |
| 于富霖 | Yu Fulin | Юй Фулинь |
| 于浩然 | Yu Haoran | Юй Хаожань |
| 汪美成 | Wang Meicheng | Ван Мэйчэн |
| 王超 | Wang Chao | Ван Чао |
| 李魁 | Li Kui | Ли Куй |
| 葛凡帆 | Ge Fanfan | Гэ Фаньфань |
| 袁曦 | Yuan Xi | Юань Си |
| 高逸典 | Gao Yidian | Гао Идянь |
| 范炳旭 | Fan Bingxu | Фань Бинсюй |

## Packet

Protected machine-readable files are in `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/ru-33-syllable-rule-candidates-luna/`:

- `rule.candidate.pending.json` — the finite map, composition rule, evidence limitations, and source metadata; SHA-256 `b85217c57945967829d44a62b93fd8317a92a666b69cff74ae3841884abded30`.
- `displays.pending.jsonl` — all 33 records with per-name status and source-reading tokens; SHA-256 `75cbe80b7809aa72483f2e3d9774b9a4baca34393691138bbe287caf8927ca3e`.
- `holds.pending.json` — the `hui` exception; SHA-256 `87073508ab4cead457adc1eccd071342c148228e5ac61ab1e49f7db5ada43eb5`.
- `manifest.json` — hashes for the outputs, raw mapping-table capture, GoLib indexed excerpt, and both input packets.

No source-anchor approval, identity approval, reviewer or production signature, code change, or database write is asserted.
