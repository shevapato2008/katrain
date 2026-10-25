# 棋手等级 foundation：独立规范审核

**Verdict: Spec Approved**

审核范围：`2680a3617..946c67a895962f87c2d59ab4eb4dc2f078ac0ca8` 的 7 个文件，仅计划 Task 1/2 的库内 foundation。已阅读 `AGENTS.md`、实施计划及 Astra Round 1/2 中相关要求，并检查实际实现。producer、API 接入、v2 publisher/receiver、journal/undo、纠正与部署属于后续单元，本报告不把尚未接入列为 foundation 缺项。未修改业务代码、抓取外部来源或访问生产写接口。

没有本范围内的 must-fix。

- 两张独立表与迁移保持现有 player/album 列和原 SGF 不变；current 部分唯一索引覆盖 qualified/conflict，snapshot 到 fact 的 FK 为 RESTRICT。已有库与空库的应用启动均排除 rank 建表，新增表须显式迁移。004 与 ORM 的字段、值域、唯一性及索引对应。
- 纯解析区分 9p/6d/6k；中文裸“段”保留 unspecified，不默认业余，3002 无效。grade 来自准确 SGF slot；职业身份来自同一已绑定人物的 approved 原 capture，独立保存确切 subject、字段、路径和 hash。日本资料取目标“棋士段位”，CWA 唐奕取精确 CWA000149 professional roster membership，韩国资料取精确人物 header；不使用邻人、父亲/老师、错人 wiki 或 review 评语来补职业身份。
- lookup 仅接受有界已解析 ID/canonical/status，核当地 owner，不把 i18n 当身份搜索索引；current 批量读，无 current 时走现有两侧 player FK 的 UNION，最多三份原始候选/人。最高日冲突的标量聚合不会被三候选限制吞掉；原始 SGF 单份 256 KiB、总读取 8 MiB，PG 设置只读事务及 5 秒 statement timeout。snapshot helper 为最多 200 个 album 的一次查询。库内 discovery 不写 history，不读取 fallback overlay 当原始等级。
- fact 为不带当地裸 ID 的便携内容；SHA 排除 retry 时间/current 状态。apply 要求 caller transaction 并锁既有 player 行，覆盖尚无 current 的首次写入；固定事实去重且保留首 observed_at。较新同值观察推进依据日，旧事实不回退，同日异值、职业降段及跨系统冲突形成唯一 conflict current，之后 fallback 返回 conflict。普通比赛日期不会冒充 valid_from。
- native helper 除 JSON 自洽检查外，会重核当地 canonical owner、approved 原 capture、来源路径、准确 SGF/slot、已存在 album 的人物 FK/原 rank 与依据日；新来源无 DT 时通过完整 source_games 的 SGF、source_metadata、metadata 和 derive_metadata 重核日期。source_games 来自完整已验证 manifest 的调用边界留给下一发布单元，不将该 helper 宣称为完整 publisher 门禁。

本轮实际验证：

1. `python -m pytest -q tests/test_kifu_player_ranks.py tests/test_kifu_rank_sources.py tests/web_ui/test_auth_persistence.py`：**58 passed**（54 项新 rank + 4 项 auth）。
2. `python -m pytest -q tests/web_ui/test_kifu_name_schema.py tests/web_ui/test_kifu_catalog_schema.py`：**36 passed**。合计 90 项 rank/schema 与 4 项 auth 检查通过。
3. 原 capture 缓存 `/private/tmp/codex-golaxy-six-rank-captures-20261025.json` 的六份 research_payload 中，实际解析的官方 capture body/hash 与公开最小 fixture 逐份一致；未以 inventory 摘录代替原 capture。
4. 在独立临时内存 SQLite 中保留上述完整原 payload，结合 `/private/tmp/codex-golaxy-six-rank-sgf-dates-20261025.json` 的六份完整原 SGF，实际运行 lookup 与 native verifier：藤泽里菜 7、上野梨纱 4、高星 5、王爽 5、唐奕 5、周泓余 7，均 professional_dan。91664767/91284570/91116424 使用 album_date_sort；其余使用准确 SGF DT。lookup 后 history 行数仍为零。

验证限度：本轮没有临时 PostgreSQL 运行环境，未实测 004 PostgreSQL DDL 或双连接首次 current 并发；已检查 player 行锁与部分唯一索引的实现，但不把 SQLite 结果当作 PG 并发/迁移证据。发布前仍须完成计划内临时 PG 演练以及后续 publisher/API/undo 与实际 TEST→PROD 验收。本批准仅覆盖当前 foundation 规范符合性，代码质量另审。
