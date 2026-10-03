# 胡耀宇修锚后新最终包：隔离执行验收完成

2026-10-03；executor `/root/anchor_format4_impl_sol`。这是执行回执，未自作独立审核。[独立终审新包](kifu-name-five-cn-origin-hu-final-independent-review-sol-2026-10-03.md) canonical SHA **`3c8574328afd4e1220de331ebe70a0507b110c9d2bfcaf8ae64739d57240ee9b`** 为唯一输入；签包及五锚、五scope/category、六rule、六batch等依赖全部原字节核验，未修改签名或inventory依赖。执行七模块字节hash与独立终审相同，结束再核验实现文件未变。

**实际 dry-run／apply／replay／conditional undo 及恢复显示验收完成。** 五人858／864／911／868／857，共4,358精确raw槽（4,238盘）。人物FK、alias、SGF、原姓名、metadata增量0。

| 实际检查 | 结果 |
| --- | --- |
| validator／dry-run | ready=true，write_ready=true；30 approved、0错误，预计65变更 |
| apply | 新批次ID6，实际65变更：5 raw owner、30 name、30 research evidence |
| 运行时显示／资格 | 4,358×6＝26,148槽语格逐一等于精确候选、资格为transliterated |
| 跨语言搜索 | 30候选对应12个不同显示串；每串全库搜索盘集合恰等于该已签raw范围，无范围外扩展 |
| 主五 | 21,790显示格与导入前逐格相同；主五name新建0 |
| replay | already_applied，change_count=0；实际业务SQL写入0，状态与apply后相同 |
| conditional undo | 65 reverted，0 skipped，0 already_reverted |
| 恢复 | 业务表hash全部恢复；目标完整album行metadata hash相同；173,025盘全SGF／FK hash相同；全部11语目标运行时格与baseline相同 |
| 结束 | 独占clone停止，Running=false；生产／活动测试连接0，代码改动／Git提交／部署0 |

全库SGF／FK前后SHA：`18d4ff1a39aaeaa60280ace733c643c665fa2c3772d08c012195f35c8643817a`。SQL mutation观察器禁止任何album或非许可表写入；没有album metadata写语句。撤销保留正常audit ledger：batch5→6、change318→383，业务数据恢复不等于删除审计历史。

## 独占克隆及工具边界

只读复制已停止的 `kifu-hu-final-pending-sol-20261003` volume到新独占volume／container `kifu-hu-corrected-rehearsal-sol-20261003`。使用原已签inventory的精确endpoint `127.0.0.1:55439/kifu_raw31_clone_20261003`；旧容器始终停止且不连接。它是历史撤销恢复快照的独立副本，不证明当前production前像相同。

最初新port55440 dry-run因旧inventory目标标识而被拒绝，写入0；随后fresh-target-inventory尝试在DB连接前因文档commit导致HEAD断言退出，没有使用再生成signed依赖。改用精确endpoint后输入依赖完全不变，完成全部真实业务操作。收尾脚本新增的可选全metadata统计字段缺失，使原收尾回执标HOLD；原记录保留，已做一次只读补充，验证恢复runtime／preflight／batch状态及既有baseline hash，没有重复apply。不能把该不存在的全metadata字段当作验收证据；metadata结论依据目标完整行hash、全库SGF/FK hash及禁止album写入的实际SQL记录。

## 受保护产物

目录 `~/.local/share/kifu-name-audit/2026-10-03/five-cn-origin-hu-corrected-clone-rehearsal-sol-exact-endpoint/`，目录0700、文件0400。manifest固定全部执行／补充回执和脚本hash。主要文件字节SHA：

| 文件 | SHA-256 |
| --- | --- |
| `manifest.json` | `ab08b624ddfbbf7710693f3ac9395190df9f9f9796319c349041befb039bf212` |
| `readonly-completion/completion-receipt.json` | `c6ce9e7f8a4e172686756bf51852d53935fcd01670ed62692b9d5a72d4b8eea3` |
| `dry-run.actual.json` | `e23af4c905df2cbf882a25e8d9f3c30baa18fb7a77833b19f406b735d821f7c4` |
| `apply.actual.json` | `ddb660a002fa92fb6f1031a493c278283a8056a182264ff1caff833f8ecbfe5b` |
| `replay.actual.json` | `031de7b952cd00b32ee7b69730d65f93719b4f7edb40e641a563182d7e534552` |
| `undo.actual.json` | `55cd840fdc8c029368afb459a5885ba3e8609253c14632c032abf9a3df75477a` |
| `runtime-applied.json` | `2ef07bc32ea46f4bfd690be9217e5e95a3551ab898c760b515a3449c901ce0f5` |
| `readonly-completion/clone-stop-receipt.json` | `d9d3121b5d0641322f4f9c3837e3540ae617b84a50b689a7ab1425f40305a290` |

主五25candidate仍不在六语执行包内，本次不新增其审批、不扩大raw范围、不放行人物FK或解除其他HOLD；也不证明全库十一语发布门槛达成。
