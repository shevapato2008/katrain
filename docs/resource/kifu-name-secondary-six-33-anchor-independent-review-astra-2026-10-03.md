# 33 人双来源读音锚点独立审核

**原始两个 Luna 候选包的 33 条锚点全部 HOLD；保留原件后的新版 33 条锚点全部 PASS。** PASS 仅批准精确原名、来源罗马字、已审核音节/姓名词界及三份来源记录的对应链。六语显示结果、五语用名、数据库人物/QID、SGF 槽位/FK 和生产写入均未获本次批准。

审核于 `2026-10-02T19:56:09.550856+00:00` 完成（北京时间 2026-10-03）。审核者 `/root/secondary_six_anchor_decision`；父任务指定 `gpt-6-astra / max`，运行时仅可见 GPT-6 标识，工件如实保留型号未独立认证的限制。新版 producer 为 `/root`、模型声明 `GPT-6`，与审核者不同；生产时间和内容由独立的 producer attestation 固定。

依据[双来源裁决](kifu-name-secondary-six-two-source-decision-astra-2026-10-03.md)，逐项重算 67 个不同源文件的字节哈希：一份含 1,062 人的官方名单及 33 对 GoRatings 中英人物页。对每人核实官方精确姓名唯一、CWA 编号/完整生日、中文版 H1/生日、英文版 H1/生日、同站人物 ID 与语言切换链接，并比较捕获清单中的 URL、哈希和时间。英文页面实际 HTML 语种为 `en`，中文为 `zh`；官方中文原名使用 `reviewed_text` 依据，不伪造 HTML 语种。全部来源对应核对通过。

原候选的 66 个 GoRatings `body_excerpt` 是 `title=…; h1=…; context=…` 等拼接摘要，不能作为原文摘录签署；其值有来源支持不等于该工件合格。新版改为从真实 H1 到生日表格行的连续 HTML 子串，33 个官方 JSON 行也都是原响应的字面子串；**99/99 个新版摘录通过原始正文包含检查**。新版逐人绑定旧候选规范哈希，两份旧包保持原哈希。

审核者逐人检查了下表的原始罗马字和音节，未把拼音工具推导当作读音来源。`曾志豪` 按页面 `Zeng Zhihao` 批准 `zeng | zhi hao`；`金茜倩` 按 `Jin Qianqian` 批准两个 `qian`。`汪美成` 的 Wikidata `Q101543732/P21` 冲突按[既有五语复核](kifu-name-five-primary-chinese-professional-review-2026-10-03.md)排除在对应理由之外，且已写入 producer attestation 和本次内容绑定的批准理由；未批准其 QID 或性别事实。

各条批准保持新版候选 `content` 不变，并固定候选/内容哈希、producer/reviewer、时间、限定范围和个案例外。签署后实际调用提交 `87b15d32` 的 `validate_transliteration_anchor`：**33/33 通过**。旧包没有制作伪批准或以批准状态调用校验器。

| 原名 / CWA 编号 | 来源罗马字 | 审核音节（姓 \| 名） | 原包 → 新版锚点 |
| --- | --- | --- | --- |
| 邱峻 / CWA000027 | Qiu Jun | qiu / jun | HOLD → PASS |
| 彭荃 / CWA000032 | Peng Quan | peng / quan | HOLD → PASS |
| 牛雨田 / CWA000034 | Niu Yutian | niu / yu tian | HOLD → PASS |
| 宋容慧 / CWA000216 | Song Ronghui | song / rong hui | HOLD → PASS |
| 王群 / CWA000239 | Wang Qun | wang / qun | HOLD → PASS |
| 吴肇毅 / CWA000102 | Wu Zhaoyi | wu / zhao yi | HOLD → PASS |
| 安冬旭 / CWA000184 | An Dongxu | an / dong xu | HOLD → PASS |
| 廖桂永 / CWA000131 | Liao Guiyong | liao / gui yong | HOLD → PASS |
| 宋雪林 / CWA000065 | Song Xuelin | song / xue lin | HOLD → PASS |
| 佟禹林 / CWA000097 | Tong Yulin | tong / yu lin | HOLD → PASS |
| 岳亮 / CWA000091 | Yue Liang | yue / liang | HOLD → PASS |
| 李鑫怡 / CWA000689 | Li Xinyi | li / xin yi | HOLD → PASS |
| 李亮 / CWA000282 | Li Liang | li / liang | HOLD → PASS |
| 邱金波 / CWA000422 | Qiu Jinbo | qiu / jin bo | HOLD → PASS |
| 丁波 / CWA000274 | Ding Bo | ding / bo | HOLD → PASS |
| 公彦宇 / CWA000342 | Gong Yanyu | gong / yan yu | HOLD → PASS |
| 谷宛珊 / CWA000691 | Gu Wanshan | gu / wan shan | HOLD → PASS |
| 金茜倩 / CWA000300 | Jin Qianqian | jin / qian qian | HOLD → PASS |
| 曾志豪 / CWA000538 | Zeng Zhihao | zeng / zhi hao | HOLD → PASS |
| 程宏昊 / CWA000590 | Cheng Honghao | cheng / hong hao | HOLD → PASS |
| 高恬亮 / CWA000403 | Gao Tianliang | gao / tian liang | HOLD → PASS |
| 王思尹 / CWA000635 | Wang Siyin | wang / si yin | HOLD → PASS |
| 王香如 / CWA000476 | Wang Xiangru | wang / xiang ru | HOLD → PASS |
| 李必奇 / CWA000571 | Li Biqi | li / bi qi | HOLD → PASS |
| 于富霖 / CWA000684 | Yu Fulin | yu / fu lin | HOLD → PASS |
| 于浩然 / CWA000645 | Yu Haoran | yu / hao ran | HOLD → PASS |
| 汪美成 / CWA000776 | Wang Meicheng | wang / mei cheng | HOLD → PASS |
| 王超 / CWA000599 | Wang Chao | wang / chao | HOLD → PASS |
| 李魁 / CWA000262 | Li Kui | li / kui | HOLD → PASS |
| 葛凡帆 / CWA000290 | Ge Fanfan | ge / fan fan | HOLD → PASS |
| 袁曦 / CWA000219 | Yuan Xi | yuan / xi | HOLD → PASS |
| 高逸典 / CWA000792 | Gao Yidian | gao / yi dian | HOLD → PASS |
| 范炳旭 / CWA000686 | Fan Bingxu | fan / bing xu | HOLD → PASS |

本次在已冻结目录上重新检查原名及来源罗马字与同语名称、canonical name、alias 和组内碰撞，结果为 0。目录为 `2026-10-02/honinbo-final-review-astra-v2/catalog-recheck.jsonl`，SHA-256 `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`，含 876 人、23 个 alias、22 条人物名称；未查询当前数据库。零碰撞不批准身份归并。梁伟棠的生日 HOLD、王子昂的切分 HOLD 和其他五语 HOLD 均不属于本次批准范围。

受控审核目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/secondary-six-33-anchor-review-astra/`（目录 `0700`、文件 `0600`）。`original-33.hold.jsonl` 保留逐人旧包 HOLD；`reviewed-33.jsonl` 保留逐人新包决定、内容哈希和检查；`anchors.approved.jsonl` 是可交给后续规则/批次制包的源锚点。该文件本身不能导入名称或关联棋谱。

| 工件 | SHA-256 |
| --- | --- |
| 原包 20 条 `candidates.pending.jsonl` | `9f63eec84481f317fe1b717b4ef88352e6c8ec75a0eb55c7e2dd49256dfb8a56` |
| 原包 13 条 `candidates.pending.jsonl` | `7007d8f55683b7948afb51072fcc763b6df6c7bc8081dc9bfe2ec01ca39a9c29` |
| 新版 33 条输入 | `aeacbafb671c21562205fcfc7097920e2fd427ac5be5bf41059288da121fe737` |
| 新版 producer attestation | `294864cf1dd53027dcb2acf76f6026ef3a41368cc4a3588258f9bc1f4013bdce` |
| `original-33.hold.jsonl` | `e16b7468b34eb395b701dc7906ad655742ca5d315d52bc1ef5d247f3a29b493f` |
| `anchors.approved.jsonl` | `dff6c196c3353666ecff1d0f59b4f692d1a27fa4522d18fb59042484fad3ab96` |
| `reviewed-33.jsonl` | `91d5858bf10535a3531f943852dfd2c435fd4d3654ace29f464f5379f2647738` |
| `review-manifest.json` | `d95200fa3fb4a703122dcdda12ef7990168fc105201824a87a28f0bf4f5ae5a8` |
| `review-signature.json` | `ad5455f21dae6980cf345a45b2815c9ffa54b7867e84c4bd6d4b76b8f69fd898` |

签署是独立审核者声明和精确内容绑定，不是审核者身份的密码学认证。本次仅写审核工件和备忘录，没有改代码、改原候选、使用数据库、提交 commit 或部署。
