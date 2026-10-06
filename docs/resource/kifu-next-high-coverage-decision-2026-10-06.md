# 下一阶段高覆盖决策（2026-10-06）

**决定：完成已冻结的 g / DK / DL 后，主线转向一个有限的中文混合标题 literal profile，先做最多 150 raw；不继续把四局一组的兼容标题作为主线。** 仅允许本批已冻结的原文与原有分段，补足 ASCII 品牌词、“第 N 期”“N 届”这些实际阻塞。纯 Latin、多个 core、损坏标题留待后批。此决定按用户已授权的独立判断作出，无需再次确认路线；不替代真实候选的独立签审。

本次仅检查本地只读证据与代码并写本文，未改代码、未连接数据库、未部署，也未启动子代理。

## 证据与收益

采用 PROD `2026-10-06T02:51:11.190532+00:00` 的 `/tmp/kifu-event-title-next150f-20261006/PROD/discovery-readonly.json`。文件实际有 **6,323 组**，不是交接描述的 6,473；SHA256 为 `d3e6dfad2b0fc2e48dedf7061044fb938406c6482ef9e36bf75173fb8a8d4ff5`。筛选仅使用 `eligible == total`、`selected == 0`、`names == 0` 的完整组，并核对保存的 `parsed_data.structure.parts`。没有把 mixed/selected/named 的组算成未覆盖。

| 路线 | 本地证据可见收益 | 判断 |
|---|---:|---|
| 继续当前兼容低频批 | g 已冻结 150 raw / 605 局 | 可马上完成，但后续每条工作收益很低 |
| 全部 Han 不兼容高频组 | 863 raw / 7,973 局 | 包含复杂分段，不能直接全部放行 |
| 本次窄形态候选 | **788 raw / 7,404 局** | 每条只有一个 core，kind 不重复，原分段可无损拼回 |
| 窄形态前 150 raw | **2,979 局，99 个不同 core** | 相同 750 条五语名称，候选受益约为 g 的 **4.9 倍** |
| 窄形态前 20 raw | **1,017 局** | 小样本已经超过一整批低频标题 |
| 全部 no-Han 高频组 | 383 raw / 4,216 局；前 150 为 2,739 局 | 语言与音译语义需另判，当前没有收益优势 |

前 150 中，103 条含 ASCII 字母，47 条主要受现有届次语法限制；本次排除了 75 raw / 569 局的其他 Han 形态。筛选保持现有字符集合，仅增加 ASCII 字母，并对实际 edition/round 片段容许带或不带“第”的届/期等形式；这是发现候选的统计条件，**不是可直接入库的授权正则**。

2,979 是此快照的候选收益上限：尚须验证完整 first-GN/EV/source/SGF、当前 owner 状态、碰撞与译文。前 150 中例如“第12期日本女自本因坊战预选”有疑似错字，应跳过或补足足以说明字面含义的证据，不能顺手纠正 SGF 或赛事身份；从同一排序的后续候选补位即可。不要把 7,404、7,973 或全调查 152,357 次出现数记为新增完成。

## 前 20 个精确原文

这些行在发现快照中均为完整 eligible 组且无现有 names/selection。表中局数是待核对的受益候选，不是本次写入数。

| raw owner ID | 精确 raw | 局数 | 当前主要阻塞 |
|---:|---|---:|---|
| 69852 | KB国民银行杯2012韩国围乙联赛 | 339 | ASCII KB |
| 86675 | 第2期日本幽玄杯精锐循环赛 | 67 | 第2期 |
| 69855 | KB国民银行杯2013韩国围乙联赛 | 65 | ASCII KB |
| 58195 | 2016年IMSA智英会男子团体赛 | 45 | ASCII IMSA |
| 56760 | 2013韩国nTV元老女棋手队式对抗赛 | 37 | ASCII nTV |
| 66584 | 3届韩国最强棋手战循环圈 | 35 | 原文 3届 无“第” |
| 67863 | 5届韩国最强棋手战循环圈 | 34 | 原文 5届 无“第” |
| 56539 | 2013go9dan首届世界循环赛 | 33 | ASCII go9dan |
| 53425 | 1届YK建设杯快棋循环圈 | 32 | YK 与 1届 |
| 85344 | 第2届BC信用卡杯64强赛 | 32 | ASCII BC |
| 53458 | 1届北海新绎杯世界公开赛64强 | 31 | 原文 1届 无“第” |
| 58307 | 2016象屿杯中国CCTV快棋赛64强赛 | 31 | ASCII CCTV |
| 86175 | 第2届韩国LetsRunPark杯64强赛 | 31 | ASCII LetsRunPark |
| 88876 | 第3届BC信用卡杯64强赛 | 31 | ASCII BC |
| 91372 | 第4届BC信用卡杯64强赛 | 31 | ASCII BC |
| 76612 | 第12期日本会津中央病院女子立葵杯预选 | 30 | 第12期 |
| 85390 | 第2届Mlily梦百合世界公开赛64强赛 | 29 | ASCII Mlily |
| 97607 | 第9届CCTV电视快棋赛 | 29 | ASCII CCTV |
| 59974 | 2019中国浙江平湖当湖十局杯CCTV快棋赛64强赛 | 28 | ASCII CCTV |
| 59266 | 2018中国平湖当湖十局杯CCTV快棋赛第1轮 | 27 | ASCII CCTV |
| **合计** | **20 raw** | **1,017** | |

明显不适合放入本次 profile 的例子是“宏达杯第1届世界星锐战第3站”（28 局）：已有 parts 含两个 core。不能把它折叠成新 core 来通过校验。纯 Latin 的 `6th Nihon Ki-in #1`（71 局）、`ChinaCityLeagueA,1st`（65 局）等收益虽高，但不应借中文 profile 放行；既有独立决定还明确保留了 Nihon Ki-in #1，需另批处置。

## 最小实现边界

1. **一个新 profile，复用当前有限 manifest 协议。** 例如 `sgf_chinese_mixed`，仍最多 150 个 exact raw，并绑定 raw 集合 hash、各 owner 原有 parts hash、两库各自完整 preimage/member/scope。原文必须经审核确认为可读中文 GN；含汉字只是发现条件，不能据此自动宣称原文语言。允许 ASCII 品牌词与本批实际出现的期/届片段，不开放纯 Latin、假名/韩文、任意 Unicode 或任意 parser 形态。
2. **原 parts 原样保存。** 一个 core，各 kind 唯一，所有 text 原样拼回 raw；不重新解析、不补“第”、不把 year 从 core 拆出、不折叠多个 core。五语最终名称可以按原文含义直译，但保留年、届、轮、64强、队式等区别；`围乙` 不能译成围甲。KB、BC、IMSA、nTV 等可以保留品牌字母，未有证据不扩写其全称。
3. **改动集中在两个既有入口。** `katrain/web/kifu/raw_event_translation.py` 增加窄 profile 校验及 research/owner-marker 匹配；`scripts/kifu_raw_event_title_owners.py` 为新 profile 继承 `sgf_chinese` 的全部完整范围与未命名 owner 检查。注意 common ordinal 检查在 SGF 分支之前，单改字符正则仍会拒绝“期/无第”。现有 `render_event_components` 已支持数值的“届/期”，无需改通用 parser 或展示优先级。若实际实施发现还需修改其他守卫，应仅做新 profile 的必要接线，不顺带重构。
4. **所有既有边界保留。** owner 仍只改变 review status/metadata；先批准 owner，再由实际 producer 绑定 afterimage 生成 names；原 FK、identity、alias、rank、SGF 与 source 不变。完全 public NULL、nonhidden、nonduplicate、unselected、unnamed，且所有 SGF first GN 精确为 raw、EV 符合现行空值规则。碰撞沿用当前规则，不能新增身份豁免或用无依据的文字绕过碰撞。

## 最低充分 gate 与推进次序

1. root 先完成已冻结 g 及正在处理的 DK/DL。一次冻结下一批候选；复用现有只读 capture 和 manifest，取得两库当前完整范围。遇到不满足条件的 raw 整条跳过并补位，不反复扩大调查范围。
2. 一次小补丁、一次独立代码审查。沿用现有两个 `test_kifu_raw_event_title_owners.py` / `test_kifu_raw_event_title_translation.py`：加入 KB、期、无“第”的真实形态，以及少量参数化拒绝用例，覆盖换 raw/parts/profile、丢失成员、已有 name/link/selection、无 marker 和纯 Latin 越界。继承现有来源、碰撞、事务、重放/撤销测试，不再造一套审计框架或跑无关全库测试。
3. 对实际两种 reader 做一个新 profile 名称的五主语言显示/精确搜索与一个英语回退语言验证，并用另一种分段形态确认新分支可读。自动化已覆盖的 marker 拒绝不再逐语种重拍。确认旧 `sgf_chinese` 和已批准 profile 的现有聚焦回归仍通过。
4. 按现有 TEST→PROD 有限部署与入库流程执行：必要的纯校验模块部署后，在 TEST 走 owner/name dry-run→apply→afterimage/reader 核对，再在 PROD 走同样精确流程。全批记录 names 与相应证据、零越界字段变更、完整成员数量；以五语都实际入库且两个 reader 可读取为完成。资料审核仅围绕 99 个 core 复用结果；有歧义的品牌/专名使用已有资料或一次本地语言 Wiki、棋院、专业名录核验，不对每年/每轮重复查询。
5. 新 profile 如被迫需要修通用 parser、容许多 core 或改身份/碰撞政策，就删去引起扩张的候选，继续此次窄范围。达到上述 gate 即交付，不追加全面 parser 重写、更多抽象、全状态截图或全库逐条赛事考证。

一次有限实现有望先得到约 2,900 局的受益，并让同一窄形态余下候选继续按现有 150 条批次推进；该收益足以覆盖一轮小补丁与发布成本。它仍不等于全库 95%：按当前总量 173,025，2,979 局最多约提高 1.72 个百分点。最终目标必须按棋手、赛事的真实五语覆盖分别继续核对，不能用 pending 组数、单语言、英语回退或相互重叠的口径代替。
