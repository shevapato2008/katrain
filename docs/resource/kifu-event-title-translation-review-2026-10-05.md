# 赛事原文直译入口审查与部署

2026-10-05。用户已授权赛事名称直接翻译；仅为现有赛事 ID 的五主语新增 `translated` 决策，使用现有名称及证据表。

## 独立审查

审核者 `/root/link407_review_astra`，配置模型 `gpt-6-astra`，max；基线 `f9f8243a`。先确认需求符合，再审代码质量；结果通过，无阻塞项。

- 仅既有 event ID，cn/tw/jp/ko/en；禁止 player、raw owner、新实体引用。
- 原文标题、实际原语言、已登记来源、正文捕获 SHA、HTTP 200 和同赛事身份保留；不声称直译是惯用译名。
- 译名、方法和版本绑定，独立生产者/审核者、完整前像、锁内事务及碰撞检查保留。
- 主线 reader 只给赛事名称接受 translated；正式环境 legacy reader 增加证据匹配的赛事译名精确搜索。

## 聚焦验证

实现者已有相关回归 378 passed；独立审核抽选 4 passed / 18 deselected。主线程重新执行 `python -m pytest -q tests/web_ui/test_kifu_event_translation.py`：22 passed，0.47s。两个 reader 与导入器镜像均已通过真实镜像模块导入检查。

## 发布范围

- TEST reader/importer：`katrain-web:kifu-event-translation-test-20261005`。
- PROD importer：`katrain-kifu-importer:event-translation-20261005`。
- PROD legacy reader：`katrain-web:kifu-event-translation-prod-20261005`。
- 不新增数据库 schema，服务更新只重建 Web；数据库、引擎和 cron 保持运行。
- 两个 reader 已重建，PROD 真实 API 验收通过：吴清源/Go Seigen 搜索同 IDs、韩文 `한국 명인전` 返回 926 局并展示已批准译名、俄语展示与英文一致。
- TEST 的带届数赛事缺 raw 译名时回退原中文问题已最小修正，独立审核新增 4 个参数用例全部通过；严格覆盖率、精确 raw 优先和 Oteai/GN 保护保持。更新 TEST 镜像 `katrain-web:kifu-progressive-display-test-20261005` 后真实 API 同样通过：吴清源/Go Seigen 返回同 1,023 个结果、韩文赛事 926 局展示正确、俄语与英文显示一致。
- 两环境结果数量不同反映实际关联数据差异；不把搜索验收等同于全库五语完成。
