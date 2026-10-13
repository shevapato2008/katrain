# 大手合五语增量批次：2026-10-04

已关联的赛事 `Oteai` 在 TEST（`katrain_db`，事件 ID 1）和 PROD（`katrain_prod_20260725`，事件 ID 22）更新为五个已核实名称：`cn/tw/jp/ko` 为「大手合」，`en` 为 `Oteai`。韩语名称沿用韩国棋院正文实际写出的汉字专名；括号中的 `승단대회` 是说明，不当作专名，也没有推断 `오테아이`。

来源为[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/)、[日本棋院英文报道](https://www.nihonkiin.or.jp/english/topics/03/topics2003_01.htm)、[韩国棋院报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=1376)及中文、英文、日文维基百科的固定修订版本。原始响应体、版本号、SHA-256 与最终 bundle 存于受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-04/oteai-five-applied/`，来源 manifest SHA-256 为 `1fbd83159b5c68fe8cafed94467a4e51b6d4c00caf30b78eec6e683aacfc8b42`。本批只更新既有且已关联的事件实体，没有把其他带 `Oteai` 的年份、赛季、关西棋院或说明性原文批量归并。

两个环境的五个候选均经独立正文与哈希复核、离线验证和目标库只读 dry-run。TEST bundle 的规范 SHA-256 为 `d8679f535c0acc4e5724b2135aa30bd477bfb466027e6769f2c73214df565f2b`，PROD 为 `bfc737cbf106c657a664192bc2305f96f5cd7d51b9e16c82cb2a41a99067cfb6`。事务写入分别产生名称批次 ID 5，各改动 10 行（五个姓名行及证据行），确认五个显示名均为 `verified`。TEST 有 575 盘、PROD 有 1,057 盘已关联该事件；它们的棋局归属不是本次更改。

| 环境 | 棋手五语完整 | 赛事五语完整 | 三槽五语完整棋局 |
| --- | ---: | ---: | ---: |
| TEST | 6 / 1,088（0.55%） | 1 / 22（4.55%） | 24 / 173,025（0.0139%） |
| PROD | 6 / 876（0.68%） | 1 / 22（4.55%） | 24 / 173,025（0.0139%） |

本批使两个环境的完整棋局各由 10 增至 24。只读复算报告位于 TEST `/home/fan/kifu-name-incremental-wu-20261003/reports/test-progress-batch5.json`、PROD `/home/ubuntu/kifu-name-incremental-wu-20261003/reports/kifu-five-progress-prod-batch5.json`。其余 21 项赛事仍未达到五语完整。
