# Kiosk 棋手卡片发布回执

2026-10-24 完成：摆谱及 GameControlPanel 遗留矩形名片统一为现有交错梯形，独立 Astra Max 代码/真实视觉/交互审核 Approved，随后集成到 develop、更新 Smartbox main 子模块并部署 RK3562。此次未发布云端、未改 Galaxy。

## 版本与验证

| 项目 | 发布值 |
| --- | --- |
| 实现提交 | `8aacfe518` |
| 已推送功能分支 | `fix/baipu-player-cards-20261024` |
| 功能分支及 `origin/develop` | `db32efe06878f37786d0cd58d1785fd8747fb419` |
| 合并前最新 develop | `495d0284c05cb7c9e8b388ded49a82f2959bfdf7`，无冲突合入 |
| Smartbox `origin/main` | `0ebec02f7b625db9499a116fe44027f550748bd2` |
| `vendor/katrain` gitlink | 同上述发布 develop |
| RK 进程 `KATRAIN_BUILD_SHA` / source marker | 同上述发布 develop，PID `276356` |
| strict 主入口 | `index-Dg5sY7DI.js` |
| 摆谱入口 / 共享轮廓 | `BaipuSessionRoute-Cl5x8POZ.js` / `PlayerCardSurface-B0zHjN-u.js` |

实现方与独立审核方各重跑现有聚焦测试 **83 passed**；合入最新 develop 后再次 **83 passed**。合并树 full build 与 `build:smartbox-kiosk-2d` 均通过，strict Box SSO / Kiosk 边界通过。Astra 未发现必须修复项，并实际点击确认，核实手数、高亮、坐标和撤回状态。

[原因、范围及验证说明](../../2026-10-24-kiosk-player-cards.md) · [独立 Astra Max 审核](../../../superpowers/reviews/2026-10-24-kiosk-player-cards-astra.md) · [摆谱前后同尺寸对照](../../../design/kiosk-player-cards-before-after-2026-10-24.png)

## RK 发布范围

从干净的已发布 develop 导出 **388** 个受控运行 Python 文件，并复制同源构建的完整 full/strict static；共 **1184** 文件在设备逐项哈希通过。新旧运行 Python 对照保留了其他已发布视觉、课程、棋谱同步等补丁，没有回退它们。仅停起 `smartbox-katrain.service`；kiosk 与围棋 target 的 PID/启动状态不变，其他棋类、身份、配置、模型、硬件状态不操作。

发布前在线备份 SQLite，备份旧运行文件及两套静态到数据盘。**449** 个既有配置/身份/模型/标定相关文件哈希在发布后保持一致。没有重置数据库、重新标定、创建真实棋局或触发付费分析。

设备 health、API health、Kiosk 入口与摆谱路由静态入口均 200；本地引擎 reachable，相机/识别/LED 正常。served 摆谱 chunk 确认包含 paired classes，独立共享 SVG chunk 包含原批准的圆角斜接缝路径。完整清单和检查见 [manifest](manifest.json) 与 [verification](verification.json)。

设备原本停在 `/kiosk/tutorial`、vision unbound。服务重启导致既有应用 SSO cookie 失效；通过登录墙“去盒子主页”→真实围棋 tile 正常重进，恢复既有 `fan` 登录并回到原 URL。没有读取/注入 cookie 或伪造 generation。实际 1024×600 页面加载新入口并显示完整 OGS 课程内容，[设备截图](screenshots/rk-current-tutorial.png) 与 [浏览器记录](browser-verification.json) 可核对。

本次没有为了验收强行进入用户摆谱页或操作实体盘。摆谱/OGS/本地回退等真实 React 布局及交互由本机同尺寸浏览器 fixture 验证，见 [自由对弈参照](screenshots/ai-reference.png) 与 [Astra 独立点击后的白方](screenshots/astra-manual-white.png)；不将这些截图称作 RK 实体盘端到端验收。用户可在设备打开任一棋谱的摆谱页检查新名片。

## 回滚与清理

设备记录及旧版本保存在：

```text
/mnt/data/smartbox-deployments/20261024-kiosk-player-cards-db32efe06/
  manifest.json
  verification.json
  browser-verification.json
  rollback.sh
  rollback/  # 旧源码、两套静态、SQLite 快照、旧版本标记及保留状态哈希
/root/smartbox-software/vendor/katrain/.smartbox-release.json
/root/smartbox-software/.smartbox-deploy-revisions
```

只需回滚时，使用设备发布目录 `rollback.sh` 恢复原运行文件/静态/版本标记并重启围棋服务；不覆盖当前数据库、模型或标定。回滚脚本未执行。上传压缩包和解包候选已删除，回滚材料留在数据盘；最终根分区可用约 **2.05 GiB**，数据盘约 **15 GiB**。

Smartbox 指针准备时曾填错完整 hash，校验发现后追加纠正；第一次 push 网络超时未发布，最终远端 main 已核实正确。没有将错误指针部署到设备。证据记录独立提交，未为纯记录移动已部署的 develop revision。
