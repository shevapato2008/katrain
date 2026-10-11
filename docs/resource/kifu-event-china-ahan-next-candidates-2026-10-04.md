# 中国阿含桐山杯：下一批 exact 赛事候选（只读）

PROD 捕获：2026-10-04，ucloud-v100 / katrain_prod_20260725，仅 SELECT。Chinese-tagged Ahan 谓词返回 **801 盘／154 个 raw**；日期 1999-07-09–2025-09-17。JSON 逐行保留 album ID、event/date、双方、结果/轮次、source/source_path 和 SGF md5。

## 结论

建议创建独立规范类型 **中国阿含桐山杯**，不要并入现有日本阿含桐山杯 event ID 39。届次、预选/网选/本选/快棋等保留在原始 event，event_edition_id 暂不推断。

## TEST 对照

TEST 同一谓词有 801 个 event_id NULL 槽位；PROD 集合缺 0 个 TEST 对照 ID。执行前须重新捕获并按 exact ID 集冻结两环境计划。

## 边界与 HOLD

- 仅纳入明确含“中国”的阿含家族 raw；无“中国”限定、日本阿含桐山杯、赞助/特别/中日冠军对抗及训练/选拔 raw 保持 HOLD。
- 不批准届期。日期/届次冲突、缺日期/1900、SGF EV/GN 不一致、重复主线或 FK 漂移均逐 ID HOLD。
- 本包未与已扫描 candidate/HOLD ID 相交，也未按相似文本扩展。

若全部批准，PROD 赛事关联由 101,998 增至 102799（59.41%）。

Astra 需确认：新建中国阿含桐山杯类型，并明确与日本 ID 39 的边界。
