# Ranks101–150：30 身份/读音与 5 mapping 独立审核

2026-10-03。Reviewer：`/root/raw30_anchor_review_astra`；模型记录为 `GPT-6; requested gpt-6-astra/max; runtime subtype unverified`，不冒称工具独立认证了具体子型号。本轮只读冻结文件；未连接活动 TEST/PROD，未改 producer 原包。

结论：**source-profile identity 30 PASS；reading anchor 20 PASS / 10 HOLD；5 mapping 来源关系 PASS，精确导入记录 0 PASS / 5 HOLD。整体 import/write HOLD。**

| 范围 | 实际结论 |
| --- | --- |
| 30 外部人物对应 | 官方姓名、完整 DOB、GoRatings profile ID 与指向官方档案的链接吻合；只签来源人物对应，不批准 DB 唯一人物 ID、album FK 或通用 alias |
| 20 读音锚点 | 保持 producer content 不变，签精确 owner 与既有有限 raw scope；全部实际通过 `validate_transliteration_anchor` |
| 10 读音 HOLD | 5 mapping 前提、6 韩国别名规范化、1 脚本依据问题；前两组重叠 2 条 |
| 155 主五语候选、次六语 rule/batch | 本次没有批准，仍需各自的独立审核与导入闸门 |

## 受控产物

目录：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-identity-reading-independent-review-astra-v1/`。目录 `0700`，文件 `0400`。

- 本包 manifest SHA：`dc034fd59cc13fea4d146854e114eab22e59e18574444c4fffba908a48f9670c`。
- 输入 producer manifest SHA：`5b5748cb13b33c3249299bb763add88b0a5697d381fc121ebc86b9c24703aa25`，全部 279 个受控文件的 hash/size 一致。
- `identity30.source-profile.approved.jsonl`：带明确审批范围的 30 个来源身份记录；每条完整签名记录的 canonical SHA 可作为后续新 mapping 的 provenance 指针。
- `reading-anchors20.approved.jsonl`、`reading-anchors10.HOLD.jsonl`、`raw-original-mappings5.source-PASS.import-HOLD.jsonl`：精确决定与逐条原因。
- `checks30.actual.json`、`validator.actual.json`、`summary.actual.json`、`review.py`：正文定位、实际校验与有限人工决定的生成记录。

## 必要更正与边界

**5 mapping 全部保留导入 HOLD：**金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱。官方正文分别支持 `김명훈/金明訓`、`伊田篤史/IDA, Atsushi`、`나 현/羅 玄`、`羽根泰正/HANE, Yasumasa`、`楊子萱`；兼容汉字及简繁差异可解释，Hane 的精确英文 heading 也已捕获。但当前 `research_record_sha256` 指向历史未签 identity proposal，不能把来源关系成立写成该导入对象已批准。

下一步顺序必须是：producer 将这 5 条重新绑定本包已签来源身份记录 SHA → 独立审批新的精确 mapping → producer 重新生成对应 anchor，且 `anchor.produced_at >= mapping.reviewed_at` → 独立复审新 anchor。不得在旧 anchor 倒填审批时间。

**6 韩国别名规范化 HOLD：**金彩瑛 `Kim Chaeyoung`、金明训 `Kim Myounghoon`、罗玄 `Na Hyun`、安成浚 `An Sungjoon`、徐能旭 `Seo Nungwuk`、金惠敏 `Kim Hyemin`。官方 Hangul 与发表别名的同人关系通过；`kim/young/myoung/hoon/hyun/sung/joon/nung/wuk` 等需要显式、有限的别名到 Hangul/读音规则，再独立审核。韩国国立国语院允许既有专名拼法继续使用，因此这些 HOLD 不表示已发表英文姓名错误；它们表示本包没有把历史别名自动提升为通用 RR 音节规范。[官方 Romanization 说明](https://www.korean.go.kr/front_eng/roman/roman_01.do)

`安祚永 / 안조영 / An Joyeong` 与 `洪性志 / 홍성지 / Hong Seongji` 的给定音节直接对应，已包含在 20 条 PASS 中。其余 PASS 为：彦坂直人、童梦成、陶欣然、曹大元、谢尔豪、赵晨宇、今村俊也、丁浩、许嘉阳、王晨星、谢科、孟泰龄、廖元赫、濑户大树、淡路修三、李维清、三村智保、邬光亚。

**徐靖恩 script provenance HOLD：**身份、中文原名及 `Xu Jingen` 来源通过；`徐靖恩` 三字本身不区分简繁。Producer 硬编码 `zh-Hans`，而冻结、相互链接的海峰原生档案是 `html lang=zh-tw`，正文明确为繁中。应绑定原生脚本依据，或明确说明字段仅描述 GoRatings 的页面显示形式，再生成并审核精确 anchor；不能从网站主机或国别直接推出脚本。

**URL-host-origin 问题确认：**本组 25 个韩国棋院档案中，17 个正文明确对应中国、台湾或日本棋手。逐人姓名、原文页面和档案内容支持本次 30 个语言家族选择；韩国主机不等于棋手原语为韩语。徐靖恩的具体脚本标签仍如上 HOLD。

已有 26 个 context exclusion 原样保留。本包 20 个 approved anchor 只是有限来源证据，未批准译名候选、规则、批次、DB import 或部署；后续仍需候选独立审核及真实目标快照/运行时闸门。
