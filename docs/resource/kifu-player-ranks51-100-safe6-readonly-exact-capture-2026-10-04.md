# ranks 51–100 安全子集 6 人：TEST/PROD 只读精确捕获

本次覆盖：赵哲伦, 梅泽由香里, 冈田结美子, 村松大树, 陈嘉锐, 石田笃司。身份来源使用 Wikidata Go-player entities 及对应中文 Wikipedia 搜索入口；身份锚点不等于 FK 批准。

- TEST `katrain_db`：781 NULL slots / 777 albums，DB 时间 `2026-10-04 10:43:48.511828+00:00`。
- PROD `katrain_prod_20260725`：781 NULL slots / 777 albums，DB 时间 `2026-10-04 10:43:07.923617+00:00`。
- exact slot 集合差异：TEST-only 0，PROD-only 0，FK 差异 0；语义 album 差异 0；SGF parse errors TEST/PROD = 0/0。

## 身份与目录线索

| raw | Chinese canonical | identity source | TEST owners | PROD owners | collision |
|---|---|---|---|---|---|
| 赵哲伦 | 赵哲伦 | [Q104726960](https://www.wikidata.org/wiki/Q104726960); [index.php?search=%E8%B5%B5%E5%93%B2%E4%BC%A6](https://zh.wikipedia.org/w/index.php?search=%E8%B5%B5%E5%93%B2%E4%BC%A6) | — | — | medium |
| 梅泽由香里 | 梅泽由香里 | [Q2599301](https://www.wikidata.org/wiki/Q2599301); [index.php?search=%E6%A2%85%E6%B3%BD%E7%94%B1%E9%A6%99%E9%87%8C](https://zh.wikipedia.org/w/index.php?search=%E6%A2%85%E6%B3%BD%E7%94%B1%E9%A6%99%E9%87%8C) | — | — | medium |
| 冈田结美子 | 冈田结美子 | [Q8061124](https://www.wikidata.org/wiki/Q8061124); [index.php?search=%E5%86%88%E7%94%B0%E7%BB%93%E7%BE%8E%E5%AD%90](https://zh.wikipedia.org/w/index.php?search=%E5%86%88%E7%94%B0%E7%BB%93%E7%BE%8E%E5%AD%90) | — | — | medium |
| 村松大树 | 村松大树 | [Q25252528](https://www.wikidata.org/wiki/Q25252528); [index.php?search=%E6%9D%91%E6%9D%BE%E5%A4%A7%E6%A0%91](https://zh.wikipedia.org/w/index.php?search=%E6%9D%91%E6%9D%BE%E5%A4%A7%E6%A0%91) | — | — | medium |
| 陈嘉锐 | 陈嘉锐 | [Q9367031](https://www.wikidata.org/wiki/Q9367031); [index.php?search=%E9%99%88%E5%98%89%E9%94%90](https://zh.wikipedia.org/w/index.php?search=%E9%99%88%E5%98%89%E9%94%90) | — | — | medium |
| 石田笃司 | 石田笃司 | [Q25252691](https://www.wikidata.org/wiki/Q25252691); [index.php?search=%E7%9F%B3%E7%94%B0%E7%AC%83%E5%8F%B8](https://zh.wikipedia.org/w/index.php?search=%E7%9F%B3%E7%94%B0%E7%AC%83%E5%8F%B8) | — | — | medium |

## 捕获内容与限制

压缩 JSON 保留完整 album/SGF/source、两侧 raw/rank/FK、对手 FK、event/event_id/event_edition_id、duplicate、catalog/alias/name、raw staging、赛事与 edition rows。后续必须以逐局 PB/PW/DT、段位、国家/年代、对手及赛事上下文做独立 slot decision。目录 owner 为空表示本次快照没有 normalized exact owner，不代表身份已获准。
