# 已核中文名的繁体显示：云端部署记录

2026-10-08：TEST 与 PROD 的最小兼容覆盖包已实际部署。独立 code review 通过，覆盖包保留两环境现有识别、名称查询及既有资格分支。

| 环境 | 实际 web image | 健康与代码文件核对 | 既有数据实际 HTTP |
| --- | --- | --- | --- |
| TEST | `katrain-web:verified-cn-display-test-20261008-r1` | healthy，4 个文件 SHA 相符 | 6 项通过 |
| PROD | `katrain-web:verified-cn-display-prod-20261008-r1` | healthy，3 个文件 SHA 相符 | 6 项通过 |

只重建 web 服务；GPU、数据库和 cron 服务未重启。既有译名及俄语界面的英语回退查询通过。两个隔离 importer 已构建，并验证 4 个源文件 SHA 与五个模块导入；构建不写数据库。

实际 image ID、经审核的兼容源代码、审核全文和构建/部署/HTTP 回执见 [归档](kifu-verified-cn-display-deployment-2026-10-08.json.gz)。仓库功能提交为 `7baaea18`；线上存在较旧依赖，因此使用归档中的最小 backport，不能把两套线上文件声称为整个仓库 HEAD。

## 待完成的数据验收

首批四位的繁体显示规则、来源锚点、批次和产品导入资格已在本地签核验证通过。按用户最新“每 20 个棋手集中入库”的节奏，尚未写入 TEST/PROD，不计入当前完成数。实际新增繁体显示、PostgreSQL 源证据校验及查询耗时需在集中入库后核验。不会把原名保留或字形生成描述为当地既有刊载译名。
