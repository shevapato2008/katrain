# 五主语言频次 41–60：95 格待审来源候选合并包

2026-10-03。合并 19 名棋手 × `cn/tw/jp/ko/en` 共 95 格。原 62 个来源 PASS 与其候选值保持逐格追溯；四个 `jp` HOLD 由日本棋院 2014 百霊杯表格所载替代值替换；29 个 `cn/tw/ko` 补证均有独立来源审核 PASS，其中江维杰 `tw` 主显示采用 Astra 的 `江維傑` 裁决。新合并包 95 格全部仍为 `approval=pending`，审核者与审核时间为空。

## 完整性与语言来源

每位棋手恰有五个语言格，按 GoRatings 外部 profile ID 与确认生日绑定到输入姓名。语言计数 `cn/tw/jp/ko/en = 19/19/19/19/19`；95 个 `(external profile ID, language)` 键唯一，无缺格、重复格或 HOLD。`cn` 使用中国围棋协会/野狐/体坛等简中正文，`tw` 使用海峰繁中及明确标注香港属性的 HK2 人物正文，`ko` 的高川格用 Cyberoro 韩文正文全名，`jp` 的四个替代项逐字取自日本棋院表格；不从 URL、字符简繁或编码推断正文语种。HK2 的 `zh-Hant-HK` 与 Cyberoro 的 `ko` 使用 `language_basis=reviewed_text`；体坛通用 `zh` 依实读简中正文记 `reviewed_text`。全部发布方 ID 映射到固定 registry `.8`。

## 受保护冻结包

私有 bundle：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-41-60-consolidated-luna`（目录 0700、文件 0600）。候选、来源清单与实际原始响应按 SHA-256 保存在包内；生产原始文件另保留其原始路径和哈希，manifest 记录输入文档和固定 registry `.8` 的不可变哈希。

| 文件 | SHA-256 |
| --- | --- |
| `candidates.pending.json` | `f69ae74059cd547c0615c733c47fb92747a3d4d916481234e4d4ccaa3de6e325` |
| `sources.manifest.json` | `82acefa5b629bc66cfee673b9b33f8dabe4e4062c4bee976e13140fd3b8e968f` |
| `manifest.json` | `b6264f8d4de9045704a5e3f93c896ce577a393d3fe85d869d80b70745fca836c` |
| 固定 registry `.8` | `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |

## 边界

这些是来源显示候选，95/95 保持 pending。材料不声称 raw 槽覆盖、数据库覆盖、本地主键/FK 对应、棋谱或专辑归属，也不授权数据库写入。没有更改代码、数据库或 registry，没有提交更改。
