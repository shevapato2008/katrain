# 250 盘疑难赛事棋谱列表隐藏

用户决定暂不投入处理剩余 250 盘赛事原文。这批棋谱占全库 173,025 盘的 0.1445%，涉及 238 个精确原文字段。两套数据库已于 2026-10-05 写入 `kifu_albums.list_hidden_reason=unresolved_event_tail_2026_10_05`，记录和 SGF 保留。公共列表、计数、搜索排除此标记，原 ID 的详情和 SGF 仍可访问。

精确计划在 `kifu-hidden-tail-{prod,test}-2026-10-05.json`。同一赛事原文下存在 10 盘已经通过 SGF 核实的中文覆盖棋谱，已从 260 个候选中排除并校验 SGF 哈希；实际只隐藏 250 盘。`scripts/tag_kifu_unresolved_event_tail.py` 在 PostgreSQL 事务内核对环境、ID、原文、日期、赛事关联及保护 SGF，先回滚演练，再按 TEST→PROD 提交。独立审查通过。

TEST 镜像：`katrain-web:kifu-hidden-tail-test-20261005`；PROD 镜像：`katrain-web:kifu-hidden-tail-prod-20261005`。只替换 Web，沿用各自原有部署模型和配置。两端健康正常，真实列表总数均为 172,766（173,025 减 9 条重复记录，再减 250 条隐藏记录）；代表性搜索不含隐藏棋谱，隐藏和保护棋谱的详情仍返回 SGF。新中文展示资产也随本次部署发布。

聚焦 API 与棋手关联测试：19 passed、1 skipped（已有 PostgreSQL 性能测试）。实际 PostgreSQL 两环境的隐藏更新演练和提交均成功；结果见 `kifu-hidden-tail-applied-2026-10-05.json`。解除隐藏可对计划中的 ID 将本次原因设回 NULL，Web 回滚保留此前镜像和 compose override。
