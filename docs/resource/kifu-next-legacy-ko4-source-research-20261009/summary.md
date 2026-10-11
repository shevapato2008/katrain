# 四名旧韩文生成名：来源线索（source-only）

本目录只汇总已保存的资料；物理五语名称数量不等于 qualified。没有重抓页面、签名候选或检查最新数据库前像。两个存在韩文同人名称差异的个案标为 hold。

| PROD ID | 大致对局量 | 日文名 / 原文读音 | 已刊罗马字 | 当前 KO | 来源发现 / 处置 |
|---:|---:|---|---|---|---|
| 5244 | 333 | 橋本　誼 / ハシモト ヨシミ | Hashimoto Yoshimi | 하시모토 요시미 | same_spelling_Korean_Go_context_reference_found. NamuWiki tournament bracket page for the 15th Japanese Tengen tournament includes “하시모토 요시미” in the main-draw player list. It is a community encyclopedia/tournament page, not an official Go publisher. Exact official Japanese profile also prints HASHIMOTO, Yoshimi / ハシモト ヨシミ, bridging the romanization to the same Go player. No conflicting Korean spelling found in these bounded captures. |
| 4499 | 255 | 山崎祐男 / ヤマザキ マスオ | Yamazaki Masuo | 야마자키 마스오 | no_direct_Korean_same_person_form_in_saved_bounded_queries. The saved exact Han query results were unrelated/noisy, and the exact current-Hangul query did not surface a same-player Go source in the captured result text. No direct conflict was found. This is a bounded search observation, not global absence. Japanese official profile directly prints 山崎 祐男 / ヤマザキ マスオ / YAMAZAKI, Masuo. |
| 6496 | 127 | 高見沢忠夫 / たかみざわ ただお | Takamizawa Tadao | 다카미자와 다다오 | possible_same_person_Korean_Go_publisher_conflict_hold. Naver exact-Han Go query result links a Hangame Baduk player page titled “다카미자와 타다오” (page seq=1814). This differs from current “다카미자와 다다오”. The source page itself was not among the retained body captures, so preserve as a direct conflict lead and hold for root/manual decision; do not overwrite on search-snippet evidence alone. Japanese identity source has 高見沢忠夫 and たかみざわ ただお. |
| 3900 | 118 | 佐藤直男 / さとう すなお | Sato Sunao | 사토 스나오 | same_person_Korean_name_conflict_hold. The saved Naver result for exact Han query “佐藤直男” quotes Korean Wikipedia’s Go-player page for Yuuki Satoshi: “사토우 스나오(佐藤直男)9단의 문하생”. This directly identifies the same Japanese Go player and publishes “사토우 스나오”, differing from current “사토 스나오”. The exact Hangul query also returned Wikidata’s Korean label “사토 스나오” and a NamuWiki tournament bracket using “사토 스나오”; these illustrate competing published usages but do not resolve the Korean Wikipedia form. Hold for conventional-name review; do not prefer generated current form without adjudication. |

## 证据与缺口

- 权威锚点只取每人一份已保存的原始日本棋院或专业 Go rating profile，均含同人日文名与明示读音；URL、HTTP 状态、真实抓取时间、原文 SHA-256、引用定位和本地 gzip 包 SHA-256 在逐人 JSON 中。
- 每人的两条 Naver 查询响应原文及各自抓取时间、HTTP 状态、SHA-256、literal query 和结果摘录一并记录。它们是发现线索，不能取代页面本体。
- 只读 throughput 快照列出的 `product_qualified_languages` 对四人均为 `cn,en,jp,tw`，缺 `ko`；虽然 KO 行标为 `verified/generated/nikl-ja-ko-personal-name-v1`，其 `reference_url` / `reference_kind` 为 null。这是旧 KO 未进入产品资格语言集的直接缺口线索。解释文字和规则来源只作为待审线索；本次没有签名台账或最新前像审计，故不宣称其签名缺失。
- 5244 的 NamuWiki 15th Tengen bracket 有同名韩文围棋语境用例，但属 community source。4499 的有界已保存搜索未发现直接同人韩文刊名。6496 Hangame 与 3900 Korean Wikipedia 分别出现相冲突的韩文形式，建议先 hold。
