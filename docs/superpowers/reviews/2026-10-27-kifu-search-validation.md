# Galaxy 棋谱搜索验证记录

状态：首轮实施及审核已完成；已发布develop与父仓库指针，并部署TEST和三条索引。TEST正确性通过但200ms预算失败，PROD尚未发布本轮变更；继续聚焦证明编译成本。

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

完整Astra审核通过后，严格依次发布feature、合并develop、父main子模块指针，然后先TEST web-only替换与显式AUTOCOMMIT CONCURRENTLY索引，再新PROD小样本复验。保留唯一TEST collector和两边cron/PG/GPU/MinIO及权限、SSO、媒体配置。

需记录正确列表及首盘的API/浏览器分层实测、网络条件、索引定义及valid/ready、实际发布SHA和运行版本。未达到200ms时报告剩余成本，不能以空/少结果、未审核名称或旧棋盘换取达标。
