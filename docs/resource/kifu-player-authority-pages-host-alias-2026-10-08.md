# 棋手权威页面漏收修复（2026-10-08）

GoRatings 来源登记使用 `goratings.org`，实际抓取有时使用 `www.goratings.org`。严格主机匹配造成部分已核实名称的页面链接没有追加到 `kifu_players.authoritative_pages`；已保存的译名和研究证据未丢失。

修复显式允许这两个 GoRatings 主机，仍检查来源 ID、语言路径、当前棋手 ID、名称和证据签名。保留抓取时的真实 URL。独立 gpt-6-sol 审查 PASS；先复现一个失败，修复后本文件 25 项测试通过。

已更新测试和正式环境的独立页面同步工具镜像，未重启网页、数据库、引擎或 RK3562。两环境各追加 97 个链接，涉及 37 位棋手；重新只读扫描待更新数为零。既有手工页面信息与证据 ID 均保留。

完整 dry-run、apply、verify、部署回执存于 `kifu-incremental-applied-2026-10-05/kifu-player-authority-pages-goratings-host-alias-20261008.json.gz`。之后每批新增译名继续同步权威页面。本文不代表全库五语言翻译已完成。
