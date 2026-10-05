# 1117赛事关联后库存刷新

两库各使用现有 `build_inventory(inventory_format=4)` 在READ ONLY、REPEATABLE READ事务捕获一次；生产/TEST数据写入0，原1117包未修改。

| 环境 | 新 inventory SHA | 新 base SHA |
|---|---|---|
| TEST | `ee0de4a21460b509172eb23129eeae225275fc372d242aadd062397f4290567d` | `93e9aab1d7ef2e306fd539b4876a8e28c24b1df203f7d63849ddcc3f0638751e` |
| PROD | `65ba1b36f5747165900803bef297711ce26e1704281878a24937a48bbfa8c6da` | `6abcc94e6e3e6eb279fb2bfd1e7859e02b95534f02bfbef822bed3af09b1564c` |

路径：`/tmp/kifu-post1117-inventory-20261005/{TEST,PROD}/inventory.json.gz`，时间2026-10-05 12:32:37 UTC。两库总数173025不变，inventory visible173016（仅排重，公开列表另排隐藏250）。

与各自post123库存逐行对比，只有指定1117行的event_id由NULL变为40/53/34/49，分布424/328/253/112。其余association字段、sources、棋手槽及selection supplement相同；在同一次扫描中将这1117个event_id逆置NULL，准确恢复原post123 base SHA。另仅查询这1117份SGF SHA，均与已审scope一致；未再扫描全库SGF。

具体证据位于每环境`capture-checks.json`、`association-comparison.json`。两名source producer已收到新基线；AC/AD/AE/AF业务内容冻结后才重绑pending的顶层inventory_sha256并用现有validator复核，不改owner/name/evidence前像或已批准历史。

## 已完成pending重绑

AC/AD/AE/AF均已由各producer明确业务冻结后重绑，8份bundle均为25 pending、0 missing、errors/write_errors为空。仅bundle顶层inventory_sha256改变；owner/name/member/source evidence不变，metadata和decision-summary已同步，approved历史未动。新旧pending SHA及逐包验证结果见 `/tmp/kifu-post1117-inventory-20261005/pending-rebinds.json`。
