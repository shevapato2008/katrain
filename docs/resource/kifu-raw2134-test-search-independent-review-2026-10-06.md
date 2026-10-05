# TEST raw 赛事精确搜索独立审查

审查者：`/root/duplicate_executor_review_astra`。本轮仅审 commit `fc533f7082609374e380db475c0e344563f2e271`、实际 TEST 最小 overlay，以及 root 工作区 `scripts/render_kifu_name_progress.py` 的一行脚注调整。

**通过，无阻断问题，无需额外实现或测试框架。**

- `strict_matching_names` 按 player/event/raw-player/raw-event 的 owner 集合总数判断唯一性；总数不为 1 时返回四个空集合。多个 name ID 可以属于同一 raw owner，不会误当多身份。因此新增 `bool(raw_event_name_ids)` 分支只在唯一 approved raw owner 且无其余实体匹配时成立；非 strict 的 legacy 精确匹配也先参与排除。
- 精确 raw 查询采用既有 `strict_raw_event_search_clause`，同时禁止随后中文 provisional fallback 扩大范围。没有精确命中的普通查询继续走原 fuzzy 分支；entity 精确匹配和有歧义的查询分支不变。
- `selected_event_ids` 的计算与最后 OR 追加位置保持不变，原第二 GN 的审核、SGF hash 与选择优先逻辑继续生效。现有已选赛事/SGF 漂移用例覆盖该路径。已查看本次 strict off/on 参数化回归与已有选择测试；复用已报告的 3 项聚焦通过结果，未重复跑测试。root 的 15 项实际 HTTP 验收尚属下一步。
- 实际 TEST `identity.py` 的 `strict_matching_names`、`strict_raw_event_search_clause`、`strict_selected_event_search_ids`、`_approved_raw_event_names` 与被审工作树函数 AST 完全一致。

TEST overlay 核验：`before` 字节等于 `/tmp/kifu-raw2134-20261005/runtime-test/katrain/web/api/v1/endpoints/kifu.py`；before/after/patch 三个 SHA 均与 manifest 一致；独立生成的最小 diff 与 change.patch 完全相同；after 通过 AST 解析。确认不是用整个 main endpoint 替换 TEST。

- before SHA：`0bb70336ed06439aeb900c3d908f8f191f5e6cc0c386944efdb699cb1d6c9d45`
- after SHA：`e45d58ce347dfc22cad1120f51725a8bb85d008df793b456a6c0d4470be480da`
- manifest 文件 SHA：`027cdec2a7c6c371c9d86b6f4a2a5356b76a31e1601295abbf0e249fab195916`

root 写入前应按现有部署说明比对真实 TEST 当前 before SHA，写入后确认 after SHA；不得把本地捕获相符当作真实 runtime 已更新。PROD 不在本次 overlay 范围。

脚注调整通过：只在存在 raw 覆盖量时追加说明，不修改任何实体统计卡片或计算。读取当前实际统计文件确认：raw 赛事五语覆盖 **2134** 盘，其中双方姓名也齐全 **208** 盘；38566 + 208 = **38774** 盘完整展示，22.4095% 格式化为 22.41%；赛事实体完成数仍为 **64**。文案明确说明描述未计作新赛事实体，未混淆 raw 与 entity 完成数。

本轮未 SSH、未连接/写入数据库、未修改代码，也未扩展至旧重复棋手执行器审查。
