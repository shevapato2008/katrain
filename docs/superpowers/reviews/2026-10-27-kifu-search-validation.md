# Galaxy 棋谱搜索验证记录

状态：两轮受控实现均已审核并发布到develop及父仓库指针，仅部署TEST。正确性通过，最小SHA缓存后的完整paint仍349–3693ms，200ms门禁未过，PROD未发布本轮变更。已停止扩样及新机制，向主session报告实际界限等待下一步决定。

## 新机只读基线

新PROD为`ucloud-v100` / `117.50.177.254`，当前代码`e9b4d3ecc`，176884 albums，王星昊结果504条。未访问已退役的旧183入口。

| 测量 | 样本 | 实际结果 |
|---|---:|---|
| 新PROD loopback完整HTTP棋手搜索 | 5 | p50 2137.712ms，最大2203.463ms，20条、15651B |
| 新PROD隔离只读helper | 1 | 2604.198ms；matching741.213ms、strict_display1525.634ms |
| 新PROD无条件页完整HTTP | 3 | p50 4028.592ms，最大4090.069ms，单列不混入棋手搜索 |
| TEST隔离只读helper | 1 | matching282.708ms、strict_display600.433ms；完整原始记录见证据 |

以上helper与完整HTTP是不同测量，均不包括真实浏览器绘制；小样本最大值不作为全球p99承诺。原始证据在[evidence目录](evidence/2026-10-27-kifu-search/)。

## 实施检查

- 并行实现按后端候选/worker、identity证明、前端一致性三个文件边界隔离。独立规格审核已逐项通过。
- 首轮规格审核发现切语言丢失第二张手选卡，已修复并补两条先红后绿回归（`80bdd8886`）。
- 证明缓存审核发现Python相等把17/17.0等JSON变化当作相同内容，已恢复逐条canonical candidate SHA，并使用类型严格的artifact内容比较；补整数/浮点数、布尔值/整数、正负零四项回归（`ca3810747`）。没有跨请求缓存。
- 负责人独立集成验证：新候选/worker/索引/context与现有list/name API/first-pass/selected/rank合计 **284 passed, 1 skipped**；skip为既有SQLite无法验证的实际PG计划检查，留待部署阶段。
- 前端focused **29 passed**，`npm run build`通过。真实1280×720预览使用新前端及TEST只读API：搜索王星昊后504条，首条/标题为申真谞vs王星昊219手，左侧棋盘已绘制。仅既有未登录`auth/me`401，搜索无新增控制台错误。
- Astra Max整体审核未留下Critical/Important；Minor失败提示复用了已有全语言翻译key（`ca7393960`），最终前端29例及构建再次通过。生产operator经实际只读inspect核对挂载/别名可重建性，TEST/PROD均未执行apply。
- 旧e9调查worktree独立复证14项既有失败（迁移保护表集合、CWI旧hint、历史俄语断言）；本次不扩修这些旧契约。旧SQL数量阈值3项也在e9原样失败，新增保守候选增加固定1次查询，已保留随页尺寸不增长的N+1断言。另9项旧evidence错误文案正则不符，相关生产源码未改。

## 部署验收待办

首轮实际发布：feature `ce010cddf4ff9c77a1baa0c174dafaae0ab74019`，develop `dc17489e2269926b34da5f040a74990d2f4db3c9`，smartbox-software/main `f44676aeb94e3e9baa9333ebdb616b5eadc2e0d8`。TEST image `sha256:8754652a8d475d65d2671573683553ec940f0380590f206da0262691a120768c`，web `6b9dda84a8e4`；137个非web容器ID/start/restart/state全部相同，唯一collector未重启。3条索引定义、valid、ready均通过；没有启动时DDL。

TEST首轮实测已停止扩量：16项API检查通过、11项旧新契约完全等价；27次真实棋盘paint全部正确，但563–3804ms（中位1429.8ms），均超200ms。未进入4客户端/40ms组，未做PROD变更。详见[test-after-summary](evidence/2026-10-27-kifu-search/test-after-summary.md)。一次隔离暖profile647ms中display586ms，11次batch snapshot deepcopy341ms、bundle/member canonical编译120ms，SQL合计82ms。下一刀只按这些实际成本收敛，不继续无目的压测。

第二轮为最小同SQL完整artifact SHA + first-pass纯compiled缓存，无MVCC协议、预热hook或全扫描。第二轮计划及代码独立Astra Approved；Important旧ORM artifact导致raw scope误拒由`fec348cae`闭环。实现focused363 passed（9个已确认旧文案用例排除），独立spec/代码审核及合并后30 passed。

第二轮实际发布：feature `1db3162c16e87dc587a042a60810943d5c4dda8b`，develop `06d8e732f2c9cb956c76d9c9806f3f3584adcd43`，父main `2abc47d6f2e5b6d2647b6122e027bb34f2fe7e87`。TEST image `sha256:80be16d9e88e2d754c3d646944c0569ed4db9be82dd0c02226327be4eadf8987`、web `7266e0c60af6`，health200，137个非web状态再次完全相同；保留唯一collector、全部索引与原配置。

第二轮限定17公开GET：11项旧新契约完全等价；新进程首个观测API781.89ms，后续王五语166–249ms，page2首次660.75ms，柯首次1935.27ms。5次正确paint：王507.3、柯539.7、一力辽3693.3、王repeat349.0、page2 530.3ms；全部超200ms。王repeat fetch237.8ms含display134.3/candidate79.5，暖response→paint约97–133ms；未进入并发/40ms，未将成功退出的`budget_stop`当作性能通过。详见[test-sha-cache-summary](evidence/2026-10-27-kifu-search/test-sha-cache-summary.md)。

复用原4条只读EXPLAIN的实际索引验证：history 0.102/0.252ms用`ix_kifu_name_changes_target_row`，raw零匹配0.126ms用两个名称索引，player COUNT4.405ms用黑白索引。业务结果没有靠空/少返回或旧棋盘缩短时间。

完整Astra审核通过后，严格依次发布feature、合并develop、父main子模块指针，然后先TEST web-only替换与显式AUTOCOMMIT CONCURRENTLY索引，再新PROD小样本复验。保留唯一TEST collector和两边cron/PG/GPU/MinIO及权限、SSO、媒体配置。

需记录正确列表及首盘的API/浏览器分层实测、网络条件、索引定义及valid/ready、实际发布SHA和运行版本。未达到200ms时报告剩余成本，不能以空/少结果、未审核名称或旧棋盘换取达标。
