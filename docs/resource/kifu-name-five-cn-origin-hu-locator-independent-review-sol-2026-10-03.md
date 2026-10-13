# 胡耀宇 CWA locator：独立修订签锚 PASS

2026-10-03；reviewer `/root/freq41_60_95_review_sol`，GPT-6 运行时身份（未独立认证子型号），与[修订生产者](kifu-name-five-cn-origin-hu-locator-repair-pending-sol-2026-10-03.md) `/root/anchor_format4_impl_sol` 分离。仅批准 corrected source anchor，不批准六 batch、30 candidate、主五25 candidate、人物 FK 或数据库操作；[旧下游 HOLD](kifu-name-five-cn-origin-primary-five-independent-review-sol-2026-10-03.md)仍未解除。

**PASS：胡锚 content 相对于旧完整签锚仅 `sources[0].record_locator` 变化**：`data.[Z09] roster row playerNo=CWA000025` → `data.Z08[10] roster row playerNo=CWA000025`。新 pending 包 manifest 所有文件 hash 相符，留存 input-* 与旧包各文件逐字节相同。

原 CWA JSON `five-primary-41-60-95-aux-span-corrected-root/sources/weiqi-association-18ba2a04efdc.json` 字节 SHA `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` 重新读取吻合。`data.Z08[10]` 唯一人物行逐字核对：`playerNo=CWA000025`、`playerName=胡耀宇`、`playerBirthday=1982-01-18`、`playerGrade=Z08`；body_excerpt 与完整原对象一致，Z09 无此人物。GoRatings 184 的 retained zh/en 正文 hash、H1、实际 lang 和同 DOB 再核对通过；`Hu Yaoyu` 与 `[[hu],[yao,yu]]` 来源／分词事实保持不变。

其余四锚完整对象及原审批逐值相同；五份 scope/category 输入文件 SHA `fc3bdafda183dc98b493cac2fe9b435f8f383f3abf7fd2734c8d91fe2f26301b` 未变，五 scope 与原已签 records 相同；六 rule 集合 canonical SHA `5a33c96164247852ebece329f30b7d2bdd626ea5302f332bdb5577d165d5b00e` 未变。没有重新签署这些未变依赖或扩大其范围。

新 producer 时间 `2026-10-03T02:30:12.994186+00:00` 原样保留；真实独立签署时间 **`2026-10-03T02:34:15.078986+00:00`**，晚于新生产。实际 `validate_transliteration_anchor` 在签前拒绝 pending；签后胡锚和五锚集合全部通过。该软件结果之外，本次另独立核验真实正文 locator，未仅依赖 hash 校验。

## 新冻结签署与精确哈希

独占目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-hu-locator-independent-review-sol/`，目录0700、文件0400，未覆盖旧包。

| 对象 | SHA-256 |
| --- | --- |
| 新胡锚 content canonical | `77cbe2ba871f3f2e77a3389e92dc602d265f1507108879056f993494b7fbe117` |
| **新胡锚完整已签 record canonical（下游绑定用）** | **`c4a9f2341449c7d4586718e30dcc4895c0ebf809645a50e7868df49bd2a63172`** |
| `hu-anchor.approved.json` 字节 | `c63dbc40738b705fb242683d07bba230da0f5363b3e5ddf881501fd633744c6c` |
| `raw-anchors-v3.approved.json` 字节 | `f2349f4c9b3c435c9203c25981ad9393627d523bd9e72b38707576143e4fee6c` |
| `anchor-record-bindings.approved.json` 字节 | `e3d7b51025df4ad4045cd7ea9b8199e6873331a975138efb900c16d040f8e1b6` |
| `review-record.json` 字节 | `c8d485046353008ac936a02f6aee760c510de267cbd25e4332a2781da3d9c7c1` |

下一生产版本应引用上述**完整已签 record canonical SHA**，不能继续使用旧 `511c54…` 或 pending `59d21c…`。随后六 batch 重绑／独立签署、30 candidate 新批次绑定、主五依赖更新及实际目标前像／最终审批仍为独立待办；本次不为其预先背书。原始来源相对路径均以同日 `china-professional-roster/` 为根。

本次 DB 连接／写入、克隆操作、应用代码或生产者文件修改、旧签名修改及 Git 提交均0。
