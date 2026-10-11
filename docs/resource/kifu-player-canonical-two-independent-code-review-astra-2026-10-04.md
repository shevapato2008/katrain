# 两位棋手简体canonical脚本与冻结计划独立审核

2026-10-04，独立 gpt-6-astra max。**PASS，仅当前批次A和下列冻结计划。** 未改代码、未运行dry/apply、未写数据库。

- 脚本 `scripts/apply_kifu_player_canonical_two.py` SHA256 `0bff0ca6a782528bb3d74cb8168b0b5dbdf38c2df98373d66889ac4edd1e9048`。
- TEST计划内部SHA `48950e9d00be28fd7d55eb23b04879c1686acad1557c7eb25582cb590ebe253d`；文件SHA `e87edd0a13c9e72a9f3dd4f5f99d982b00006aa923432420cfe8cf0e291a529f`。
- PROD计划内部SHA `6b418400b3bf21915ac57edab70446ebcfa2961aaaf64c686c7d8333d2b67ec4`；文件SHA `109b32bebb2725a1ecc0dbb16adde0ef9cf754cbca670d4f5613e0405c697ed0`。

两个计划的catalog、10条旧名称、空alias、FK分布与本次独立只读留存逐项一致。每库工藤366槽（178黑/188白）、赵66槽（33黑/33白）。只批准TEST348/542与PROD347/541保留ID的canonical简体化，以及各自旧准确繁体alias；不涉及周鹤洋批次或新棋谱关联。

代码硬绑定数据库和每个环境的两组ID/旧新canonical；验证冻结摘要与环境；锁表后重新捕获目录／碰撞／名称／FK计数并与计划比较；canonical逐行CAS；改名及alias插入同一事务。capture和verify均在任何SELECT之前设置只读重复读事务。SQL写路径仅两次目录UPDATE及对应aliasINSERT，不修改棋谱FK、SGF、raw metadata、五语名称或审核状态。已作源码逐段审查、无落盘语法编译、两计划摘要重算及与独立证据比对；无新增阻塞。
