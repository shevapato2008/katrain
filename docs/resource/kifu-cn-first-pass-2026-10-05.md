# 棋谱库中文展示第一遍（2026-10-05）

本轮按用户确认的“先完成中文展示”验收。保留 SGF、原始棋手/赛事字段、身份 ID 和已有核实名；没有把展示候选写成已核实译名。其他四种主流语言留待后续翻译。

|环境|总棋局|黑白棋手位含中文|有赛事字段且显示含中文|黑白棋手及赛事同时含中文|
|---|---:|---:|---:|---:|
|TEST|173,025|329,910 / 346,050（95.34%）|164,558 / 170,214（96.68%）|155,919 / 173,025（90.11%）|
|PROD|173,025|329,910 / 346,050（95.34%）|164,560 / 170,214（96.68%）|155,921 / 173,025（90.12%）|

以上是只读全库核算的**显示覆盖率**：以字段包含汉字为第一遍可展示代理指标，不代表所有姓名/赛事身份均已逐项核实。未填赛事的 2,811 局仍保持空值；不为覆盖率编造赛事。实际列表接口排除 9 条重复记录，返回 173,016 条。

实现使用已关联棋手、赛事在数据库中的中文规范名；8 个常见罗马字棋手拼写使用明确来源的中文名；赛事使用原有中文文字、已有目录和少量确切英文核心译名；6,339 局从原 SGF 取到的中文赛事名按 `album_id + 原 EV + 未关联赛事 + 实时 SGF SHA-256` 守卫。日文假名、损坏文本、长英文拼接和含糊目录别名保持原文。两环境共用同一份压缩展示资产，运行时按精确原文和关联赛事规范名查找，并在进程内缓存。

可复现输入是 `kifu-event-display-weighted-{prod,test}-candidates-2026-10-05.jsonl.gz` 与 `kifu-cn-first-pass-event-canonical-{prod,test}-2026-10-05.json`；构建脚本为 `scripts/build_kifu_cn_first_pass_asset.py`。候选研究见 `kifu-event-display-weighted-plan-2026-10-05.md`、`kifu-player-cn-top20-2026-10-05.json`。例如[日本棋院对大手合的说明](https://www.nihonkiin.or.jp/profile/faq/)和[CWI 的 Oteai 页面](https://homepages.cwi.nl/~aeb/go/games/games/Oteai/)支持“大手合”的显示名。

部署：TEST 使用 `katrain-web:kifu-cn-first-pass-20261005-r3`，PROD 在其原镜像上使用兼容覆盖镜像 `katrain-web:kifu-cn-first-pass-legacy-20261005-r2`。两个环境只替换 Web 容器；数据库与 cron 未重启。旧镜像分别保留为 `katrain-web:kifu-name-five-978491a2` 和 `katrain-web:kifu-ea2f9a67-wu-five-978491a2`，撤掉最后一层 compose override 即可回滚。PROD 的兼容代码位于 `deploy/ucloud/kifu_cn_first_pass_legacy/`，待基础发布追上新棋谱阅读器后可删除。

验证：65 项聚焦 API 测试通过；TEST 和 PROD 的真实详情均显示 `1934年秋季大手合` 与 SGF 补名 `台湾中环碁圣赛`，中文搜索命中同一棋局；PROD `/api/v1/health` 正常。TEST、PROD 分别进行了只读全库核算，PROD 还在旧基础镜像上进行了独立的只读影子请求。翻译事件的精确搜索在旧 PROD 阅读器上约需 2–4 秒，页面普通列表约 0.6 秒；该查询仍需后续优化。
