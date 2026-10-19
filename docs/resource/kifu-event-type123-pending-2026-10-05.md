# 已审 123 局赛事类型关联：两环境待执行包

准备完成，**尚未独立签署或写入**。复用 [既有类型决定](kifu-event-type-only-independent-policy-astra-2026-10-04.md)，只取已存在赛事的 123 局：ID50 韩国联赛 50、ID75 中日对抗 43、ID73 全国团体 30。

2026-10-05 11:35 UTC 定向只读捕获 TEST/PROD，123/123 原文、source_path、SGF SHA 与旧批准清单一致；event_id/edition 均 NULL、非隐藏、非重复。两库均取得 3 个正确 canonical ID、15 个五语名称和 15 份当前批准证据；随后只读 check 再次匹配完整前像。没有重新捕获棋局全库。

| 环境 | Plan 规范 SHA | 压缩包文件 SHA |
| --- | --- | --- |
| [TEST](kifu-event-type123-test-pending-plan-2026-10-05.json.gz) | `5306dae015408232fdf81d282d0eb9363853aace15eccc1bad3aabbd7c89a049` | `73e642be5c5732fe90056de8a1adab7bec0311c2e1090e23c72429e7290cf8c6` |
| [PROD](kifu-event-type123-prod-pending-plan-2026-10-05.json.gz) | `987450d9b205df71dbd6079d1e24a65acf63bee99dbea18a04c1c0417368a811` | `19333439f4fc2d5e092ff85cfbf547446aadfd2ffa29e97b88bbd44a97921c37` |

可执行目录 `/tmp/kifu-event-type123-20261005/` 包含未改动旧决定、精确 scope、有限执行器、两环境完整前像及 dry/apply-pending/verify payload。执行器沿用现有 exact-link 的事务锁、完整前像 CAS、后像核对，仅写 event_id；不更新 raw owner、名字、edition、人物 FK 或 SGF。`apply-payload.pending.json` 没有批准 SHA，须主线程独立审核后填写；本轮没有运行会 UPDATE 的 dry 模式。

现有 name_batch 要求非空名称 members，纯关联批次不应为此重写 15 个已批准名称；因此本包使用有限 exact-link 执行方式，没有改动生产业务代码或增加通用框架。执行器文件 SHA `a0e2764a1bc6c4c8f1fb1e441d2d736d7d3f243fac1c54677a89665d628c8df2`。

注意两环境 evidence ID 不全相同，必须用各自计划。正式执行前按既有路径做真实 PG dry-run 回滚；apply 后做只读 verify 与五语 API 显示/搜索验收。代码语法检查、两库只读 capture/check 已通过，不把这些检查称为正式写入验收。
