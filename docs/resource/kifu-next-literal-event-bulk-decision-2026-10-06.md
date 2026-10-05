# 下一批中文原文赛事批量直译决策

日期：2026-10-06；独立决策：GPT-6 Astra。依据用户授权：赛事可直接按原文字面翻译；生产数据范围、身份、签名和撤销边界保留。

## 决定

**批准一次最小协议调整，后续中文 SGF 直译范围由独立审核的有限 manifest 与批准 owner metadata 限定，不再逐标题增加运行时代码白名单。下一研究批次选 150 raw / 4,104 盘，目标 750 个五语名称。** 此处批准实现方向与研究范围，不签署名称或生产写入。

先完成主流程正在进行的 national15 实际 TEST/PROD 部署与 HTTP 验收，再实施这一调整；不要将 national15 的未完成发布与下一批混为一次交付。

## 已实际读取的候选范围

本次经现有 PROD SSH master 执行只读事务，设 statement timeout，未写库或修改远端文件。

- 2026-10-05 23:29 UTC：pending、无 name rows、全部 occurrence 为 public/NULL event/nonduplicate/nonhidden/no selection 的原文 **24,427 / 57,010 盘**。
- 其中中文汉字、数字与有限标点组成，既有 parser parts 无损、唯一 core、现有中文 edition/round/year 语法可用的候选 **8,615 / 25,084 盘**。这是待研究库存，不能直接计为可写入翻译。
- 对其中频次前 **220 raw** 再实际读取全组 SGF、owner 和 selection：全部满足无 EV、首个 GN 精确等于 raw；没有截取部分盘来凑范围。
- 排除初步中文身份/alias/非 literal 名称碰撞 **3 raw / 63 盘**：`棋圣战` 25、`名人战` 17、`2026野狐围棋研究会春季循环赛` 21。继续保留原碰撞门禁，不虚构译名规避。
- 剩余 **217 raw / 5,125 盘**；按原频次顺序选前 **150 raw / 4,104 盘**。共 **107 个 distinct core**；parts 形态为单 core 52、edition+core+round 32、edition+core 39、core+round 27。

冻结清单：`/tmp/kifu-next-literal-event-bulk-20261006/bulk150-candidate-scope.json`。

排序原文集合 canonical SHA-256：

`ba7493df99e514297f46467723f112c32354e5bd2c92921af9e8c24dd6ab3df4`

完整只读支撑：同目录 `PROD-candidate-scan.json`、`PROD-Chinese-single-core-candidates.json`、`PROD-top220-GN-scope-capture.json`。最后一份捕获时间为 2026-10-05 23:32:35 UTC，保存全部 scope rows/SGF refs/hash 与排除原因。

高覆盖例子：`2013职业精英网络赛` 125、`全运会` 103、`2015日本国家队新浪网络训练赛` 86、`2013日本国家队网络训练赛` 73、`2025野狐围棋研究会循环赛` 72。名称只表达原文含义；“新人王”“日本小棋圣”“新闻棋战”等不得补上原文没有的国家、身份、主办方或官方名称。

## 最小实现

1. **一个复用的 owner CLI profile，例如 `sgf_chinese`。** 本次每份 manifest 最多 150 raw；raw-set SHA、raw 数量、逐项成员与总盘数从明确提供的 frozen manifest 取得。prepare/dry-run/apply 对该 profile 均读取同一 manifest，并校验现有外部 `--expected-manifest-sha256`；plan 同时绑定这些值，逐项与全部当前 occurrence 比较。复用已有 `--manifest` 参数即可，不新建注册中心、配置服务或审批系统。旧 profiles/default 保留。
2. **共享 pure 分支移除逐标题常量依赖。** 保留 `source_basis=sgf_literal_v1`、已存在 raw_event、`original_language=zh-Hans`、`reviewed_sgf_gn`、完整 scope/refs/hash、五语言完整标题。新批仅允许上述中文汉字/数字/有限标点原文；至少含汉字，排除 Latin 标题、kana/Hangul、控制字符、损坏或不可读内容。字符筛选不代替 producer/reviewer 对中文原文含义的判断。沿用现有唯一 core、lossless、中文 year/edition/round 规则，不增加任意 stage/game/英文届次语法。
3. **parts 从真实 owner parser 来，别沿用 national15 的 `raw.partition("第")` 特例推导。** candidate 阶段对比 owner 完整 preimage 内 `parsed_data.structure.parts` 的 kind/text；owner 审批把该真实 parts 的 canonical SHA 写入现有 `review_metadata` 的一个明确 SGF 字面标记中，inspect 时重新计算核对。runtime 通过已经读取的 `review_metadata` 将该 parts hash 与 research.raw_parts 对齐，继续对齐完整 scope hash。这样无需给 legacy SQL reader 新增 parsed_data 查询或 ORM 依赖。旧 national15 没有该新标记，继续使用其已批准固定兼容路径；新范围必须有新标记，不能借旧任意 approved owner 绕过。
4. **原来源与候选协议复用。** GN refs 必须逐一覆盖完整唯一 scope；`ev_values=[]`、first GN=raw，后续 GN 注释和原始 SGF hash 保留。辅助网页按既有 `translation_support` 保存真实 URL/excerpt/SHA/时间/用途；没有辅助网页也可作字面翻译，不恢复逐标题网络检索前提。source checks、research/candidate hash、真实独立 producer/reviewer、时序及 preimage binding 按既有 SGF 分支处理。
5. **身份和事务规则不动。** 仅已有 pending、无名称的 `unclassified_pending` raw owner 可按该 profile 审批；不得用于 player/raw_player/entity event，不创建身份或修改 alias/FK/SGF/parser/rank。现有全 scope、public/NULL/nonduplicate/no selection、双层锁、完整 before/CAS、catalog/inventory pins、plan SHA、ledger/undo 继续执行。已批准 literal raw 之间同名的既有规则保持；身份及非 literal 冲突仍拒绝。

这是一项现有协议的受限中文扩展：运行时信任经过检查的批准 owner 数据，每批范围仍由外部 hash 固定的具体 manifest 决定。后续同形中文批次只换研究和 manifest，不再改代码或部署。

## 本批执行与最低验收

- producer 按冻结 150 清单工作，复用 107 个 core 的五语字面译法，保留每条完整标题/届次/轮次。当前文件是候选读取捕获，尚未有 TEST 对照、最终标准 preimage/manifest 或五语完整碰撞结果；正常绑定前刷新两库完整范围和 catalog。若实际五语冲突或 scope 不一致，明确 hold 该 raw，并在签署前重新冻结最终清单/hash，不能在已签包内静默丢项。
- 实现后只做该分支的聚焦检查：四种真实 parts 形态；错误 raw/parts/scope/manifest/member/hash/签名；越过 150 上限或使用玩家/entity/非中文；第二 GN 注释；原 national15 和旧来源分支。用两份不同有限 manifest 证明同一实现可复用即可，不建立额外审计框架或全库回归。
- 一次独立代码审查、一次必要运行时更新；TEST→PROD 继续现有 owner→name 流程。实际列表、精确搜索、English fallback 与旧 national15 做代表性 HTTP 核对。只有最终五语名称已写入且真实 reader 可读的盘数进入新增覆盖统计。

本次只写本决策与本地候选捕获，未修改实现、签名、提交、写数据库或部署；未重复运行测试。
