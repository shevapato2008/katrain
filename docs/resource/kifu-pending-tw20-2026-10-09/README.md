# 20 位棋手 CN→TW 显示：只读恢复包

2026-10-09 恢复。此前 `ready20` / `ret1564` / `ret17116` 的本地及两台服务器 `/tmp` 文件未找到，因此这里**不是旧签核包的副本**。20 个繁体候选来自本次任务给定名单。已对重新冻结的来源锚点、有限规则和每环境一批 20 人审核取得根代理独立批准；最终 bundle 尚无外层执行批准，也未执行 SQL。

## 文件

- `PROD-cn-source-readonly.json`、`TEST-cn-source-readonly.json`：从两台现有 PostgreSQL 分别以 `BEGIN READ ONLY` 捕获的 20 个棋手现行 CN 姓名、来源证据、已应用批次、TW 前像及已关联对局数。`*_at` 按产品 `_image()` 的 `datetime.isoformat()` 格式标准化，保留微秒零位。
- `unsigned-anchor-content.json`：每环境 20 条 `verified_chinese_display` 来源内容及任务指定的 TW 候选。`content` 可供独立来源审核；外层 `candidate_tw_display` 不是来源正文，也不是批准。
- `unsigned-manifest.json`：20 对 PROD/TEST ID 的可读摘要、源行哈希和来源内容哈希。
- `capture-readonly.py`、`prepare-unsigned.py`：只读捕获及纯本地资料生成脚本。后者需在仓库根目录用 `PYTHONPATH=. python docs/resource/kifu-pending-tw20-2026-10-09/prepare-unsigned.py` 运行。
- `Unicode-17.0-scoped-variants.json`、`unsigned-rule-request.json`、`rule.approved.json`：61 个有限输入字符及教育部 PDF 中 14 个变化字的逐页定位、一条规则的生产请求与独立批准。
- `{PROD,TEST}-anchors.approved.json`、`{PROD,TEST}-batch.approved.json`：每环境 20 条来源审批和一份完整 20 人批次审批。
- `{PROD,TEST}-product-snapshots.json.gz`：只读产品库存、catalog、已核姓名及别名快照；独立提取的 `inventory`、`approved-name-snapshot`、`source-registry` 文件供产品 CLI 使用。
- `{PROD,TEST}-preimage-binding-capture.json`、`{PROD,TEST}-preimage-bindings.json`：20 个空 TW 前像及独立绑定的冻结依据。
- `{PROD,TEST}-unsigned-bundle.json.gz`、`{PROD,TEST}-orthographic-evidence.jsonl`、`{PROD,TEST}-unsigned-bundle-summary.json`：待根代理外层执行签核的最终数据包、来源记录与校验结果。最终组装使用 `finalize-unsigned-bundles.py`。

## 已核实的范围

| 环境 | 指定棋手 | CN 来源 | TW 前像为空 | 已关联对局 | 线上 `verified_source_live` |
| --- | ---: | ---: | ---: | ---: | ---: |
| PROD | 20 | 20 个已核准 conventional、批次已应用 | 20 | 1,185 | 20/20 通过 |
| TEST | 20 | 20 个已核准 conventional、批次已应用 | 20 | 1,185 | 20/20 通过 |

验证在当前线上 web 容器中通过 `SET TRANSACTION READ ONLY` 调用部署版本的 `katrain.web.kifu.name_orthographic.verified_source_live`，核对现行源行、批次 bundle、研究哈希和创建变更记录。没有写入数据库。`linked_games` 是按棋手统计的现有外键对局数，本范围两环境合计均为 1,185；此值不表示本包写入了棋谱外键。

## 重新进入签核流程前

来源、规则及完整 20 人名称审核均已独立签核。根代理仍须签核最终 bundle 的外层执行范围，并在执行前对**当前**两库运行数据库 dry-run，重验前像、80 条旧资格范围及产品导入资格。快照取得后若数据库变化，须重新冻结受影响文件。旧审批文件丢失，不能把这里的签核声称为旧签核的复制。根代理负责外层批准、所有 SQL 与提交。

两个最终 bundle 的规范 JSON SHA-256：PROD `f3dd90706ac81fa93cbb24624765ffc3a4420a07fc68fffc8b56b60a879e833b`；TEST `3a1674c16863a0e95dd7782156b0b05cd757afdd429e5b01519d649324bffec0`。本地和线上固定 `7baaea18` 隔离 importer 镜像的 `validate_bundle` 均得到每环境 `ready=true`、`write_ready=true`、20/20 approved、零错误。此为离线数据契约验证，不是数据库 dry-run 或 SQL 执行。

在仓库根目录做只读 CLI 校验（将 `ENV` 设为 `TEST` 或 `PROD`）：

```sh
P=docs/resource/kifu-pending-tw20-2026-10-09
python scripts/kifu_name_batch.py validate \
  --bundle "$P/$ENV-unsigned-bundle.json.gz" \
  --registry "$P/$ENV-source-registry.json" \
  --inventory "$P/$ENV-inventory.json.gz" \
  --evidence "$P/$ENV-orthographic-evidence.jsonl" \
  --approved-name-snapshot "$P/$ENV-approved-name-snapshot.json.gz"
```

## 文件 SHA-256

```text
50529f7d186bad0d77928d64440e0f60dea942d8c8d422da89f970cdd20d6db5  PROD-cn-source-readonly.json
c76ed205ce46dd22cb38f39f5eb6e3d9cbe976fc76886738419a07f8187718e5  TEST-cn-source-readonly.json
afaf2494f5190d1b2dbe4b26a073f6340e8259fcce0a2a392d27b9967be4715a  unsigned-anchor-content.json
b84d57b8834c51dc424d778b869a9c3139b52c4693347ca2d948f79f658dd394  unsigned-manifest.json
```
