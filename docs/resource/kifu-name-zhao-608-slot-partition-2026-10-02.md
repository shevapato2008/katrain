# 赵治勋 2,052 个原始槽位：受控证据分组

2026-10-02，只读审计代理 `/root/closure_decision_astra`。运行时没有暴露可核验的模型标识；本记录不是 Astra-max 受托身份批准，也不批准任何名称或棋谱关联。**有赵治勋棋谱；全部 2,052 个槽位直接关联仍为 NO-GO。**

固定生产 v2 inventory 内容 SHA-256 为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，原 gzip 文件 SHA-256 为 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`。精确 `PB/PW == 赵治勋` 有 2,052 个槽位、2,052 个不同 album ID，黑 1,025、白 1,027，旧棋手 FK 全部为 NULL；全部来自 `19x19`，涉及 413 种对手写法和 1,411 种赛事原文。此范围不包含繁体、附带段位或头衔等其他写法。

生产 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` 的 **player 608 为赵治勋**；测试 `home-ubuntu / katrain-postgres / katrain_db` 中对应 canonical 是 **player 609**。本工件固定生产 ID。生产 608 无别名、无已关联棋局，旧英文 `Cho Hun-hyun` 和韩文 `조훈현` 错指曹薰铉，日文 `チョ・ジフン` 亦待审；这些 `review/legacy_unverified` 名称不能作为身份依据或本批十一语批准。生产另有 350 `趙治勲名誉`，不在本次精确原文范围内，也未批准合并。

## 工件与复现

受控目录为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-608-slot-partition-20261002/`，目录权限 `0700`，全部文件 `0600`。

- [manifest.json](/Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-608-slot-partition-20261002/manifest.json)：SHA-256 `4a5858497f40c925580b943f61e22fe2e1cbfb68bb011532d9bef222ada88684`。
- [partition.jsonl](/Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-608-slot-partition-20261002/partition.jsonl)：2,052 条，SHA-256 `a4c8ae38c9fb96a80a04ae1aa04b60074eb84c9c0eb3f38af93834ad2479be1f`。每条含 album ID、颜色、完整固定上下文、来源和生产 SGF 哈希、分类、全部匹配的 CWI 文件及哈希、最佳现有证据；身份状态全部为 `pending`。
- 同目录保留 `inventory-scope.jsonl.gz`、原始源字节 `source-sgfs.jsonl.gz`、生产全文 `production-rows.jsonl.gz`、`production-catalog.json`、原始 `cho_chikun.tgz`、固定解析器 `sgf_parser.py` 及 `reproduce.py`；各文件哈希由 manifest 列出。生产捕获使用 `REPEATABLE READ READ ONLY` 事务。

离线复现（需要 Python 和解析器依赖 `chardet`，不访问数据库或网络）：

```sh
/Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python /Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-608-slot-partition-20261002/reproduce.py --verify
```

主代理已用上述虚拟环境命令独立复现通过，计数与 manifest 哈希一致；系统 `python3` 可能缺少 `chardet`。manifest 中通用的 `python` 命令应使用这个已具备依赖的解释器。将脚本复制到新建的受控目录后，`reproduce.py --capture` 可执行完整只读获取；脚本包含精确 SSH、SQL、下载 URL 和计算步骤。现有捕获文件采用独占创建，避免覆盖。第一次分类发现 CWI 小棋盘后，仅修正比较范围，并使用同一已保存字节完成分类；manifest 明示捕获结束时间来自最后一个捕获文件的 mtime。

全部 2,052 份测试机源 SGF 经固定仓库解析器 `.sgf()` 规范化后，与本次生产 `sgf_content` **逐字节相等**；原始姓名、日期、双方段位及固定 inventory 的完整棋局上下文也全部核对一致。原始文件与数据库存储的格式字节不同，不能冒称原始文件哈希直接相等。每条另存 `source_sha256`、`source_normalized_sha256` 和 `production_sgf_sha256`，供未来写入前核对使用；本工件本身没有把 SGF 哈希接入现行 v2 导入闸门。

## 比较结果与边界

[CWI Cho Chikun 页面](https://homepages.cwi.nl/~aeb/go/games/games/Cho_Chikun/index.html)所链接的[完整压缩包](https://homepages.cwi.nl/~aeb/go/games/cho_chikun.tgz)共 2,800 份 SGF，包 SHA-256 为 `86ad1163cff485183ad53a0562800e0d094e3a281895727cd757fbe46b4c071e`。其中 2,779 份为 19 路；17 份 9 路、4 份 13 路不进入此次索引。

比较根节点 AB/AW 与第一子分支主线，允许八种棋盘旋转/镜像，**不交换棋子颜色**。完整序列匹配后，再检查全部匹配候选是否都把 `Cho Chikun` 放在原始姓名的同一颜色。日期、段位、胜负、贴目、规则和注释不参与棋步匹配。HA/PL/AE 及其他分支没有被该指纹证明相等，原始 SGF 和根设置摘要供后续审核。CWI 与 19x19 可能共享上游资料，不能把此次交叉匹配称为全部棋谱拥有独立主办方来源。

| 分类 | 数量 | 状态 |
|---|---:|---|
| `full_same_side` | 1,949 | 完整主线与根摆子匹配、人物同色；供单独冻结范围及独立身份审核 |
| `full_opposite_side` | 8 | 完整棋谱匹配但人物执色冲突；禁止自动关联 |
| `prefix60_only` | 69 | 前 60 手匹配，后续有差异或截断；继续待审 |
| `unmatched` | 26 | 此集合内未找到相应完整/前 60 手匹配；补其他来源 |

1,949 项排序后的 `(album_id, side)` 规范 JSON SHA-256 为 `b659a7f7a30b3c1bd4e8144f48a6fe43ee8c9ae2bde70760c5d2255ec875777d`。这是分组核对值，不是 `identity_scope_sha256`，也不是身份批准；未来 v2 工件仍须绑定目标前像、完整上下文、SGF 前像及独立范围审核。

八个执色冲突如下；这里只记录来源冲突，不裁定应修改哪份原记录。

| Album ID | 原始赵治勋槽位 | CWI 压缩包内文件 | CWI 中 Cho 颜色 |
|---:|---|---|---|
| 32643 | 白 | `Cho_Chikun/1977-01-06.sgf` | 黑 |
| 63837 | 白 | `Cho_Chikun/1978-11-16.sgf` | 黑 |
| 73239 | 黑 | `Cho_Chikun/1971-00-00.sgf` | 白 |
| 121287 | 黑 | `Cho_Chikun/2011-08-22.sgf` | 白 |
| 124511 | 白 | `Cho_Chikun/1976-09-05.sgf` | 黑 |
| 139020 | 白 | `Cho_Chikun/2020-03-05.sgf` | 黑 |
| 146243 | 白 | `Cho_Chikun/1992-03-05.sgf` | 黑 |
| 148229 | 黑 | `Cho_Chikun/2018-05-31.sgf` | 白 |

六项 `1900-01-01`（31258、58720、64309、94592、121241、138567）均属于完整同色匹配；不使用占位日期判断身份。CWI 的 DT 分别仅支持 1988、1999-08、1974、1974、1998、1998，不据文件名推造更精确日期，也不改写原始记录。69 项前缀匹配及 26 项未匹配的精确 ID、上下文、来源文件与现有证据已逐条保存在 partition 中。

本次只保存审计材料和本备忘录；未批准候选、生成关联批次、写数据库或部署服务。后续沿用[精确原名关联政策](kifu-name-exact-link-policy-2026-10-02.md)。
