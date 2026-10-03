# Hoensha 17 条来源路径独立决策（2026-10-03）

**PASS：这 17 条可与 578 条直接 Hoensha 路径一并纳入固定的 595 条 `archive_source_description` 展示范围。** 本结论仅批准精确原文 `Hoensha game`、规则 `archive-description-v1` 下的有限来源说明范围。原生产者候选包仍未取得分类、十一语和前像绑定的最终批准。

审查者：`/root/hoensha_17_scope_decision_astra`；时间 `2026-10-02T23:59:39.570675+00:00`。运行时标识 GPT-6；任务要求 gpt-6-astra/max，任务名不作为子型号认证。本次无数据库连接、数据库写入、应用代码修改或提交。初读时生产者列出的 28 个保护哈希全部通过；其后父任务修改了路径/解码实现及测试，最终冻结时通过生产者提交 `cf22621dfeaa497330c1e40dd7dfa3ba972d66d0` 复核对应旧文件。新实现不在本次来源审查的签署范围内。

## 来源核对

[生产者记录](kifu-name-hoensha-archive-description-v1-bundle-producer-luna-2026-10-03.md)中的 595 个 inventory association、basis 行、owner 成员和来源上下文逐项一致；595 个 ID 唯一且有序，均为 `event_id=NULL`，各有一个 `CWI` / `source_path` 链接。17 条差异文件恰好等于完整上下文中的 `ancient/Honinbo_Shuho` 子集；库存无 selected event。旧分流记录“595 条全在直接 Hoensha 目录”应由本次 **578 + 17** 实测结果替代。

另独立读取留存的 [CWI 完整棋谱包](https://homepages.cwi.nl/~aeb/go/games/games.tgz)：本机 `/Users/fan/Data/go-kifu/cwi/games.tgz`，46,236,709 字节，SHA-256 `ae6126bfd7da3908f3fdb07eb4ad31741e5ee039767788266b88b37abde926fb`，与 [资源记录](go-kifu-resources.md) 中该本机包一致。本次没有重新下载。将来源路径前缀 `data/kifu-album/CWI_History_Full/` 映射为包内 `games/` 后，**17/17 精确文件存在，解析后的根 EV、PB、PW、DT 全部匹配冻结库存**。

按 [导入脚本](../../scripts/import_kifu.py:97) 的 `root.sgf()` 约定序列化，再以 UTF-8 计算完整谱哈希，**17/17 哈希和字节数均匹配生产者捕获的副本数据库 SGF 负载**。原始 member 字节哈希不同；对这 17 份文件，序列化恰好只删除 LF 字节。受控 `verification.json` 分别保存原始 member、序列化结果和数据库捕获的 SHA-256、字节数与根属性，并留存 17 份原始 SGF；未将这些哈希混称为同一字节来源。

[CWI Hoensha 历史页](https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/)和[日本棋院历史页](https://archive.nihonkiin.or.jp/history/06.html)的留存内容支持方円社组织与历史棋谱语境。逐谱证据进一步说明：存放在棋士个人目录不构成排除这 17 条的理由。这里的 archive 延续[既定协议](kifu-name-generic-three-event-protocol-decision-astra-2026-10-03.md)，指已核对的 CWI 历史棋谱来源语境，不推定特定月会、届次、正式赛事 ID、现存档案机构或官方各语名称。

## 精确附加路径及最小规则

共同完整前缀为 `data/kifu-album/CWI_History_Full/ancient/Honinbo_Shuho/`：

| Album ID | 文件 |
|---:|---|
| 154830 | `206.sgf` |
| 154831 | `208.sgf` |
| 154833 | `211.sgf` |
| 154834 | `212.sgf` |
| 154835 | `214.sgf` |
| 154836 | `215.sgf` |
| 154838 | `218.sgf` |
| 154839 | `219.sgf` |
| 154842 | `221.sgf` |
| 154843 | `222.sgf` |
| 154844 | `223.sgf` |
| 154848 | `238.sgf` |
| 154851 | `252.sgf` |
| 154860 | `275.sgf` |
| 154862 | `283.sgf` |
| 154868 | `300.sgf` |
| 154882 | `328.sgf` |

保留现有直接 `CWI_History_Full/Hoensha/<单文件名>.sgf` 分支，仅增加以下 `re.fullmatch` 分支，或等价的 17 个完整路径 allowlist：

```python
r"data/kifu-album/CWI_History_Full/ancient/Honinbo_Shuho/(?:206|208|211|212|214|215|218|219|221|222|223|238|252|275|283|300|328)\.sgf"
```

所有现有门槛继续同时成立：精确 raw/category/version、CWI 来源、NULL event ID、没有 selected event、签署完整来源行与 pinned inventory 完全相同、单一 `occurrence_album_ids` 清单及其哈希、独立分类和语言审批。路径匹配不能新增成员。无需第二套 album ID 成员表；不得放开整个 `ancient`、`Honinbo_Shuho` 或 CWI 目录。显示、搜索和 coverage 继续使用同一有限范围。

## 原始实现的 Shift_JIS 阻塞

`nihonkiin_history.body` 是有效的 **Shift_JIS 原始响应**，HTML 声明 `charset=Shift_JIS`，原始 SHA-256 验证通过。包内日文摘录在严格 Shift_JIS 解码后精确存在，没有来源内容冲突。但是生产者基线 `name_candidates.py` 使用 `body.decode("utf-8", errors="replace")` 检查摘录，实际结果为 false；在此前审批、路径阻塞解除后，这仍会导致 `check_files=True` 拒绝该来源。此发现由原始字节和基线解码表达式直接核实；本次未伪造审批运行导入器。

最小修复建议：保留原始响应字节及其哈希，在签署 source check 中明确 `body_encoding="shift_jis"`，旧来源默认 `utf-8`，仅允许明确支持的编码并严格解码；或采用等价、限定到该精确来源的 Shift_JIS 分支。未知编码、解码错误仍拒绝，不以替换字符解码放行，不将转码正文冒称为新抓取原始响应。父任务已告知正在落实有限路径及严格解码修改；本决定不替代其代码验证。

生产者更新 basis、scope 或其他签署内容后，须重新计算依赖哈希并交后续审批。本次 `scope-review.approved.json` 是范围决定，明确不作为 importer 的 `category_review` 或数据库写入批准。

## 固定哈希与限制

下表区分文件字节 SHA-256 与 canonical JSON SHA-256：

| 对象 | SHA-256 |
|---|---|
| 原生产者候选包文件 | `c64379e014a2c7d3958812d29e7133ad6642fc3c810101101df46d2f32b45076` |
| `scope-difference.17.json` 文件 | `72db8f89631c7f51cace1fc6cdd53acf7689433a966abcb3ed939aa98f37c888` |
| `occurrence-source-contexts.595.json` 文件 | `8da688912058bbace9e3a7854d529f8be2b9c2ea9c1ef4919995b669ce9ab29a` |
| 库存内容标识 | `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1` |
| 完整 595 IDs canonical | `f7dcbc724298e33907624876c23c694743f472de44827bdb1ee61c018ec01f69` |
| 完整 595 occurrence rows canonical | `d45bfe9fb29395145ca276ed9f16cf41a87ce06fa84b5b8c8cceac68e9791313` |
| 完整来源上下文 records canonical | `1199c3a3e3d1f42deb6ca2755e091e357a8c09eb76cb0722e0fe0cdf27280621` |
| 17 IDs canonical | `0105ee36f67926b511eebd4562117a81200bb05a9f9f4e0065083bc20640a733` |
| 原 basis canonical（未改） | `73b981cb23e5255b7d8d21da6e3fe9ad0df8ed8adc1ece9023839a5d6fe50c36` |
| CWI Hoensha 留存原始正文 | `abeb516b8b69c606d1bf246191416aa6ef4a1db14b5b171aac505cafd22c417e` |
| 日本棋院留存原始正文 | `813b6092377b2808f5dc91574fee2ea2c38673f84351ca72dd3c83fd9b74289f` |
| 本次 `verification.json` 文件 | `ac7952d02e2b34a7d22aed3eccfc75e2c4d5955088ef4af4072e084403ab938b` |
| 本次 `scope-review.approved.json` 文件 | `6f21176f27fd2564c63dbb6fca8b6b29c1b4e4ef5916e044103c3fd39dc8301f` |

受控输出：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/hoensha-17-scope-independent-review-astra/`，目录 0700、文件 0600，含逐谱证据、17 份原始来源文件、署名范围决定和 manifest。“签署”是 reviewer 身份、时间及内容哈希绑定的审核元数据，不声称存在密码学签名。

本次未重抓网页、未连接副本或生产数据库；数据库端依据是生产者已捕获的副本负载哈希。578 条直接路径做了库存/来源上下文一致性检查，未逐谱重查原始 SGF。album 154851 的多日期 `1881-12-10,11,1882-04-20` 原样保留。范围 PASS 不代表当前生产状态、十一语批准、前像绑定、实际新增覆盖或导入成功；原生产者 packet 未由本审查改动。
