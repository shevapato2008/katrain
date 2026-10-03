# Ranks101–150：十条 reading HOLD 的有限修正候选

2026-10-03。Producer：`/root/player10_hold_resolution_sol`；模型：`GPT-6 (runtime identity; subtype unverified)`。只读取冻结来源，未连接活动数据库、未改应用代码、未 commit/push。**全部新产物 pending；本 producer 未审批自己的候选。十个 owner 仍为 HOLD。**

受控目录：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-hold10-resolution-pending-sol-v1/`，目录0700、文件0400。Manifest SHA：`370009820acb32f2a3b67b986f3c0173ad3dc05d2ba59cdd8ff42746afabafdd`。输入独立审核 manifest SHA：`dc034fd59cc13fea4d146854e114eab22e59e18574444c4fffba908a48f9670c`。

| 产物 | 本次修正 | 剩余闸门 |
| --- | --- | --- |
| `mappings5.rebound.pending.jsonl` | 金明训、伊田笃史、罗玄、Hane Yasumasa、杨子萱：`research_record_sha256` 重绑完整已签 external-profile identity 记录；实际重算与 reviewer 给定 SHA 全部相等。来源关系沿用已有独立 PASS；新 mapping 不继承审批 | 独立审新的精确 mapping；之后产生新的 anchor，时间不得早于 mapping review；再独立审 anchor |
| `korean-alias-normalizations6.pending.jsonl` | 六人逐个绑定已签身份、有限 scope、已发表别名、韩文字和参考 RR 音节；保留既有 published tokens，不把别名普遍转成 RR | 独立审这六个有限关系；金明训、罗玄同时受 mapping 闸门约束 |
| `anchors5.corrected.pending.jsonl` | 金彩瑛、安成浚、徐能旭、金惠敏：在 normalization basis 明示本人逐音节关系。徐靖恩：`source_lang` 改为 `zh-Hant`，依据同一 GoRatings profile 指向的海峰原生正文及 `lang=zh-tw` | 独立审新的五条 anchor 和相关 normalization；不提升候选译名、通用规则或 DB import |
| `dependency-status10.jsonl` | 列出十个精确 owner、旧 anchor canonical SHA 及尚缺审批顺序 | 无隐含批准 |

六个有限关系（左为原 published tokens，右为韩文及解释性 RR 参考；右侧不是替换 anchor tokens 的新来源名字）：

| raw | published tokens | Hangul | RR 参考 |
| --- | --- | --- | --- |
| 金彩瑛 | kim / chae young | 김 / 채 영 | gim / chae yeong |
| 金明训 | kim / myoung hoon | 김 / 명 훈 | gim / myeong hun |
| 罗玄 | na / hyun | 나 / 현 | na / hyeon |
| 安成浚 | an / sung joon | 안 / 성 준 | an / seong jun |
| 徐能旭 | seo / nung wuk | 서 / 능 욱 | seo / neung uk |
| 金惠敏 | kim / hye min | 김 / 혜 민 | gim / hye min |

韩国国立国语院冻结正文 SHA `d3921e37c9b96b913f15157552f7db5113769ccbea4f193a842f67527fa27540` 已重算。Section 2 的字母表提供参考，3(4)规定姓名及 given-name 音节，3(7)允许既有专名拼法。姓氏 Kim 是这些人的实际来源拼法，不能推导成通用 ㄱ→k 规则；一般 RR 参考与已发表个人别名有明确区别。以上关系只绑定本人和已签有限 raw display subset，不建立可反向推断任意姓名的 alias 字典。[官方说明](https://www.korean.go.kr/front_eng/roman/roman_01.do)

徐靖恩 native script 来源位于输入 producer 的 `sources/d227fc1aea622ac223fca9bf07235865f1009582815638d0648da7e6b022fd5f.html`；实际 hash 相符，包含 `zh-tw` 和本人中文名字，身份记录已签同一 profile/DOB。`徐靖恩` 三字本身不辨简繁，因此新 `zh-Hant` 描述原生来源正文脚本，不能据三字形状或国别推断。英文 `Xu Jingen` 与音节保持原来源值。[海峰档案](https://www.haifong.org/profession/venue/5F56B6A27939285C8C6CE8EAF86E33FD)

五条 mapping 的 dependent anchor 本轮没有提前生成。金明训、罗玄即使 normalization 先获批，仍须等待 mapping；其余三条 mapping owner 不缺韩国别名修正。另四条韩国 anchor 和徐靖恩 anchor 已有精确 pending 对象可交独立 reviewer。已有20 PASS anchor 和26 context exclusions未修改；本轮不批准155译名候选、次六语规则、person FK、alias、运行时部署或导入。
