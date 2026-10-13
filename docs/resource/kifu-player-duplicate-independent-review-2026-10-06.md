# 重复棋手执行器独立审查

审查者：`/root/duplicate_executor_review_astra`。范围为 commit `e469f48b51cd0bc742b530af77db83794031022a` 的执行器、CLI、测试、说明文档及两对真实 pending 提案/完整前像。仅审查朴文垚/朴文尧、李喆/李哲；张豊猷保持 held。

**代码审查通过：未发现要求修改执行器的阻断问题。两组旧提案存在一个必须在执行安排中处理的真实前像冲突；主线程已接受下述顺序与重新审签方案。此结论不代替真实数据库 check/dry-run 或具体提案的独立批准。**

## 已确认的执行冲突与最小处理

两组在 TEST/PROD 均共享 11 条 album；其中以下 8 条双方都需要迁移：

`104512, 104585, 104606, 104609, 104613, 104657, 104663, 104697`。

因此先 apply 任一组都会改变另一组这 8 条 album 的完整前像。原两份 pending SHA 不能直接顺序 apply。`_capture_match` 和逐行 CAS 会拒绝第二组，属于预期保护，不能通过忽略对手 FK 或放宽前像比较绕过。

主线程已明确采用：先完成朴文垚组并 verify；再真实只读捕获李喆当前前像，证明业务差异严格等于前批 receipt 中这 8 个朴文垚 FK。只有该差异成立，才生成李喆后继提案，更新完整前像 canonical SHA、gzip 文件 SHA、受影响槽位的完整 album SHA 及相关回滚包，再独立签署新计划 SHA；身份依据及所有实际操作、314/247 计数保持不变。任何额外差异应停止并重新审查。

`_check_before` 只拒绝退役 owner 本人在 `kifu_players` 的既有变更历史，不拒绝已有 album 变更历史，故首批不会阻挡上述合法后继提案。共享审计 registry 可复用。无需修改历史守卫。

后续撤销须按李喆→朴文垚逆序。李喆完成后，朴文垚首批的独立 verify/replay/undo 会因这 8 行出现后续变更而拒绝；这是当前完整后像契约的明确结果。组合验收应引用首批在第二批之前成功的 verify，并检查两份 ledger 组合后的当前行；不能声称首批仍独立满足原完整后像。李喆撤销后可恢复朴文垚批的完整后像。

## 关键边界核对

- 固定四组环境 ID 与姓名，拒绝其他 pair；计数严格限定朴 328/238、李 314/247，操作只包括列举 FK、单条 raw metadata.player_id、新 alias 和空旧 owner 删除。保留 owner 的整行不修改。
- PostgreSQL 写事务复用两个 advisory lock，对所有业务捕获表持 SHARE ROW EXCLUSIVE，并额外锁批次及逐行审计表；拿锁后重新捕获完整范围。五个实际 FK 及 player_id 相关列清单、模型完整列集合均纳入检查。
- CAS 在锁内比较完整行，album UPDATE 额外带旧 FK 条件，写后再次读取完整行；删除旧 owner 前重查所有 declared FK、raw metadata 引用与 owner 原行。
- 新 alias 的实际 ID、timestamp 和完整行进入 receipt/ledger。批次绑定原计划、完整前像、身份依据 SHA、独立审查及实际执行者。要求 reviewer != producer，允许 reviewer 兼任执行者，符合已给授权边界。
- apply 后核对完整 ledger、变更后像、受保护范围及后像 hash。replay 只在全部后像仍吻合时返回 already_applied；undone 批次不允许复用原计划再次 apply。
- 专用 undo 先验证全部后像，再恢复旧 owner、逆向恢复 FK/raw metadata，最后仅删除 receipt 的 alias。写入异常回滚数据和审计；后续数据、引用、名字、来源或 ledger 变化均会拒绝撤销。
- 李喆五条真实名字均是 `review / legacy_unverified / evidence_id=NULL`，完整行受保护；执行器没有名字写入路径，也不把它们计为五语完成。

## 实际验证

在指定 worktree 用仓库现有虚拟环境运行：

`python -m pytest -q tests/web_ui/test_kifu_player_duplicate.py`

结果：**36 passed in 22.81s**。覆盖 dry/apply/verify/replay/undo、前像漂移、新引用、schema 漂移、独立审查、ledger 损坏及正反向事务中途失败。

四份真实 gzip 前像与原 pending proposal 均通过执行器 `_validate`；文件字节 SHA、完整前像 canonical SHA、身份依据 SHA 均匹配。原计划 SHA 为：

| 对象 | 环境 | canonical SHA-256 |
|---|---|---|
| 朴文垚 | PROD | `27bcbfb484570b7fe2f272d5b1047f8021be31eec5c5790b1ee4897ec15361ea` |
| 朴文垚 | TEST | `4d94f393d902c76afaf761da7509d9a3cb1d4344e5f7300e99e451458d4d34e3` |
| 李喆原 pending | PROD | `d5288945b72d344befa33816bfadad46a81d02209db4e03fb9cd9498c0cfd062` |
| 李喆原 pending | TEST | `7d8186f703dbca4f67f9d02f42961ed4359915016b0ee09cdd0d2ddfb9ba98ba` |

另在内存中将原李喆前像的上述 8 个对手 FK 按朴文垚原提案转换，并更新对应完整前像/槽位 hash；两环境后继计划都通过 `_validate`，证明原执行器能接受该最小合法后继变更。此演算没有生成批准，也没有替代随后必须取得的真实前像。

未修改仓库生产代码；未 SSH、未部署、未连接 TEST/PROD。测试只使用既有测试创建的临时 SQLite。PostgreSQL 真实前像重捕获、锁执行、rollback dry-run 与正式 receipt 由主线程继续完成。

## 第二轮：实际执行包有限审查

审查对象：`/tmp/kifu-player-duplicate-execution-20261006` 的 README、`run-remote.py`、`capture-container.py`、`prepare_second.py`、`replay-container.py` 与 immutable manifest。

**本轮通过，未发现必须阻止 root 按既定顺序执行的新增问题。** 未重复 36 项测试，未 SSH 或连接数据库。

审查锚点：manifest 文件字节 SHA-256 为 `9e125a5e028a40d734d6b97f850ce2fdb5467880c6f6223202b57354e8c3477d`。其中 20 个文件 hash 全部匹配；执行器、CLI、models 三份 overlay 与 commit `e469f48b51cd0bc742b530af77db83794031022a` 逐字节一致。四个辅助脚本通过 Python AST 解析。后续传输应保持此 manifest 与文件内容一致。

确认事项：

- Li capture 在同一个 PostgreSQL REPEATABLE READ/read-only 事务内调用 `_check_applied`，核对真实 Piao 原计划、批准、完整 ledger 与当前完整后像，再捕获 Li，并输出八条实际 ledger 前后像；没有自行宣布批准。
- 后继生成要求真实 applied/verified receipt 的 batch ID、alias ID、change_count、counts 匹配 DB proof，apply receipt 另外匹配计划及后像 SHA。dry-run receipt 无法通过。current canonical SHA 和 captured_at 绑定同事务 proof。
- 八条变化逐条限定为 Piao 的对手 FK；每条比较整个 album，其他业务范围整体相等。Li 五条 legacy 名字明确检查保持原状态。后继保留原身份依据 SHA 和原 producer ID，顶层 producer 如实标记机械生成器 `/root/player_duplicate_impl`，未伪称该生成器作出 Astra 的身份决定；状态仍为 pending，另需 root 独立审签。
- wrapper 在 Docker 调用前核对 immutable 文件、明确提供的计划 SHA 和 review 文件字节 SHA。参数通过 argv 列表和 Python `repr` 构造，无 shell 插值；数据库 URL 仅在父进程/临时容器环境中传递。review 解析后的路径须处于挂载包内。临时容器及绑定均只读，模型 overlay 只在显式选择时启用。
- replay 使用独立只读入口，只接受既有 exact batch，没有 apply fallback。capture 和后继输出拒绝覆盖既有文件。输出目录已存在。

执行时沿用已确定的 ID 绑定：`verify/undo` 的实际选择由 `--batch-id` 决定，wrapper 的 pair 参数用于路径与 receipt 标签，未额外约束该批属于此 pair。因此应从对应真实 apply receipt 取得 batch ID，避免把不同 pair 的 ID 填入同一标签命令；本次 root 已按此安排。此说明不要求扩展执行器或新增通用校验层。
