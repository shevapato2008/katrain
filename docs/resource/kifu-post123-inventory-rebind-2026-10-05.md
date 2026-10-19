# 123 局关联后的 format4 基线刷新（2026-10-05）

仅只读捕获和本地 pending 包重绑；没有数据库写入、没有放松 `_check_snapshot`，没有改动已签 approved 原件。

## 新基线

| 环境 | inventory SHA | capture UTC |
| --- | --- | --- |
| TEST | `b37047f82e6b85a062fa7b85cae036a7d11d16356b372c2a123067e7b7bbbd8b` | 11:59:03 |
| PROD | `9b9c739fc6bc7e2d3f4e0f22606fdbe85d0ac88aed35513f5bd5ffc735f7e5ff` | 11:58:48 |

文件：`/tmp/kifu-post123-inventory-20261005/{TEST,PROD}/inventory.json.gz`。每环境各运行一次既有 `build_inventory(..., inventory_format=4)`，使用现有 player-pages operational importer 镜像和 REPEATABLE READ READ ONLY；连接环境只在内存传递。

同一次扫描额外将123个已批准 event_id 逆置 NULL 重算 base hash，TEST 精确恢复旧 `4098f29f4204d905f382062236d2a3679d650a27bcc5efc679fcbf11f0398ccb`，PROD 精确恢复旧 `6aaaa266fd80e859925ae2b4e57a7d44710f12a60a7ea53effc14a107f365e68`。因此原库存涵盖的全部 album/source 字段，除这123个 event_id 外均相同；没有再次捕获一份全库作对比。

- 两库均173,025局，detail IDs及各scope人数/原始名字统计相同。
- album_associations逐列比较仅123个event_id变化，目标50/73/75分别50/30/43局；人物FK与原字段、来源链接逐项相同。
- event_selection supplement完全相同；此次123条SGF SHA定向只读核对全部匹配旧批准原件。库存本身不哈希全库SGF，本轮未追加全库SGF扫描。
- 完整比较输出保存在各环境 `capture-checks.json`、`association-comparison.json`。

## 待签包重绑

pending JSON仅改顶层 `inventory_sha256`；候选、成员、owner/name前像及research文件不变。各包库存副本、metadata的inventory SHA与snapshot time同步。已签文件字节SHA核对不变，须主线程基于新pending复签；旧approved不移植签名。

| 包 | 环境 | 新 pending 规范SHA |
| --- | --- | --- |
| S | PROD | `7f03b68d2395ca60830cec3533794f64cc5bf1b4f82b6f5c03d01de2a5e206d2` |
| S | TEST | `bf7f4d17bc77764eef1c65e8604627f99bf0ea5efa426cf0e8052f3ccd5a7778` |
| T | PROD | `c119f0b0647bc14b664ca422a4835662f2588db8ecf45f51ee8217626baf80cb` |
| T | TEST | `f2e389a1617120581a9539190f153249aa8bb6b657589a39585ac6089494ce09` |
| U | PROD | `f23276b4c61982b5d2fbc7f0c9f0fba533bdf4684ba3b4b072f5607df6ba59ba` |
| U | TEST | `d002bada4ec533fc1705fa6519f1e765d44fb7ccb2cec50d243c0bd4266d8585` |
| V | PROD | `30b5c19bc58f75762289ef8f6e6c622a9363a2382ad9ec5646b5208d56595dc8` |
| V | TEST | `71dd8fb827dd2efe06ec66e7075acc4bff6e1e732122a5ed0941ce809e3ef878` |
| W | PROD | `d1736555189c5a46abea0e243706408ea60b2f6253d8165ab0a9c160acb0511c` |
| W | TEST | `26c0c7ba82f0e51f24774fb573fe35bd53d0e1d860f8de40ce1fe752ce024c38` |
| X | PROD | `5b1a6930a045dfbb97143a1eaaf200015ed5639b18eb346177b5475f88eeb228` |
| X | TEST | `bc899b421a0bb3a92bd50a064c26c6d0134e2f743155a72d782eafb3fd0292ae` |

S/T/U/V/W/X全部12份pending包已重绑；离线validate均errors=[]、write_errors=[]、missing=0、rejected=0、pending=25。pending包尚未签署，因此ready/write_ready仍false，这是预期状态。

旧→新hash及原approved文件SHA见 `/tmp/kifu-post123-inventory-20261005/pending-rebinds.json`。两个producer已收到新基线；W/X是在其最后业务build冻结后重绑，decision-summary已同步新基线与新pending hash。
