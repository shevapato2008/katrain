# 五名中文原名 v3 锚点与 RU/UA 规则修正版（pending）

新受保护目录：~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-anchor-rule-repair-luna/。该目录只含修正后的5条 v3 source anchors、2条 RU/UA rule records、所需来源正文、scope 与校验记录；原 producer packet 保持不变。尚未生成 transliteration batches 或 candidates，按流程等待 anchor/rule 独立签署。

五个 anchor content hash 已用仓库 canonical JSON 函数重算，且与独立审核记录中的实际值逐一相同：唐韦星 b1afe9bcd37e354d414d0f28cec7482e9550ddb8d5c78fcd7035739630132eb6；杨鼎新 e8e8c28e06f16e0648f9af5d5b5ae2edff200a7381903cb35715a745b386d31f；檀啸 64d5a1895f6f1c3a976fdb65198b3a61bbb02fdd2e081e89dcfb01019dd461fd；胡耀宇 fbebcd8dc5667316dd714eb1f35db1af33d78b7925cd4a7c4ef13db0ce2aad3b；连笑 094011419b7868585386f682767e8d27160a9e64891cf7905cf422dc188efc10。

RU/UA 新规则继续使用 Palladius RU 表与 2019 UA 学术表。每个 source record 的 http status、原始 fetched_at、body hash、实际语言、来源说明、身份依据与 excerpt 均从之前保留的真实 source record 复制；excerpt 现覆盖本批精确12-token并已对照原始响应体。token 表和候选形式未扩写。新 canonical rule content hash：ru 9029fe9cdb7942b46abaa16ccacb4562a29ec8fd674fb074d454163ad91e99ee；ua 32c05a5cce16c6aca3ebccba4c28613a1431fd3c9c5b17a715f7685825f849ef。

离线校验通过：5条源身份/日期/读音关系，2条规则来源 metadata 与12-token正文映射。所有7条记录仍 pending。尚未签 anchors/rules，也未访问数据库或克隆；fresh approved-name snapshot 和目标前像按顺序留待独立签署后再做。该材料包不是 bundle validator ready 或写入授权。

manifest.pending.json SHA-256: 0696352d0bcde4ce51bf52866ea42ef78c8f475b2cf2632d70f1d0dee1ac1d89。
