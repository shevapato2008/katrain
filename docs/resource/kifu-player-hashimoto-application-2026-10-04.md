# 桥本宇太郎 exact 姓名关联执行记录

2026-10-04，独立身份审核 PASS 后，按 TEST → PROD 将精确原文 `桥本宇太郎` 的 805 个 NULL 棋手槽关联到已有棋手 ID：TEST 12341、PROD 6577。没有新建、合并或重命名棋手；原始棋谱和姓名保持不变。

[日本棋院殿堂](https://www.nihonkiin.or.jp/profile/sisetsu/dendou/list11.html)和 [CWI 人物目录](https://homepages.cwi.nl/~aeb/go/misc/progression.html)支持与已有 `Hashimoto Utaro`／`HashimotoUtaro` 关联为同一人，并与桥本昌二区分。六条 1900 占位日期通过棋局上下文审核；40 个段位后缀、2 个繁体写法和 5 个混合 `HashimotoShoji` 原值均不在本批。

两库 capture、真实事务回滚演练与提交后完整 exact 范围复查通过。每库更新黑方 358 槽、白方 447 槽；无既有保护槽或身份 hold。提交后全库棋手 FK 槽：TEST **285,765／346,050**，PROD **287,370／346,050**。

| 环境 | 冻结计划 SHA-256 | 审核结果 | 提交后范围 |
| --- | --- | --- | --- |
| TEST | `ba315bd7ccd4964f0344096dd42790c7ab3d261939b936ee90e2c6c1b3eed401` | PASS | 805／805 |
| PROD | `5def7e16e869867e0880d1f6b5e59e62add049ce4a97a0048a53296ea629e065` | PASS | 805／805 |

范围、计划、目录只读捕获、演练及提交记录见同目录 `kifu-player-hashimoto-{exact-review,plan,catalog,target,dry,apply}-{test,prod}-2026-10-04.*`。
