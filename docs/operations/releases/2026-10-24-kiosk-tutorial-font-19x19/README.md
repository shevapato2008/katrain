# Kiosk 教程字体与十九路派生发布回执

2026-10-24 已完成独立 Astra Max 审核、合入 develop、Smartbox main 子模块更新及 RK3562 定向发布。设备原账号与原课程章节页已恢复，实际中文字体为已保存的楷体 `TW-Kai`。

| 项目 | 已核实版本 |
| --- | --- |
| Published develop / 功能分支 / debug 分支 | `09ee7f59faf40e4908e70d6c201aebd25257d33c` |
| Smartbox origin/main | `8c29181163542d6e53cecfc52e33850c16254807` |
| vendor/katrain gitlink | 同上述 published develop |
| RK 实际进程 KATRAIN_BUILD_SHA | 同上述 published develop，PID `300462` |
| Kiosk 实际入口 | `index-D4KBMil6.js` |
| Policy SHA-256 | `9be33d67384a1d04f56f80d970d65589b0e55cfe85c96a525e0a1c42ad7ed3dd` |

## 修复范围

教程根节点、来源卡片和许可弹层的固定字体覆盖了围棋全局选择；它们现在使用已有字体变量。正文、按钮、标题、加载/错误状态及 SVG 中文标记均继承保存的中文字体。数字沿用现有等宽字体，品牌字体保持原样。字号继续使用公共机制，大/中/小为 `28/22/18`、`26/20/16`、`24/18/14`；棋盘坐标固定 `16px`，棋盘与触控几何保持原设计。

小盘版本在读取时从原始内容派生，不写入或覆盖源数据库、原 SGF、答案、下载与进度身份。Kiosk 做题与选中题预览均请求同一已审核版本；Galaxy 默认读取保持原尺寸。盒端在取得云端原始数据后执行派生，本次没有云端发布依赖。

派生只做有边界约束的统一平移，同时处理初始棋子、所有正确/失败分支、标记及答案。每个来源固定原文/结构摘要，并要求局部目标证书和逐分支棋规等价；未获证书的题完整保留原盘并显示原因。原生十九路继续使用原内容。题目撤回同时修复了提子后丢失被提棋子，以及等待自动应手期间撤回、连续点击和进入试下的半回合竞态。

## 内容覆盖与保留原因

| 来源 | 原生十九路 | 新增十九路派生 | 小盘保留 |
| --- | ---: | ---: | ---: |
| 训练题，共 21,072 | 20,193 | **163** | **716** |
| OGS，共 3,551 步 | 2,860 | **112** | **579** |

共新增 **275** 个派生版本。训练证书包含 162 个固定目标提吃和 1 个解除打吃；OGS 包含 44 个直接计数/判断、40 个提吃、18 个解除打吃、4 个连接、4 个切断及 2 个填气目标。

| 小盘保留主因 | 训练 | OGS |
| --- | ---: | ---: |
| 全盘、计目或长程目标 | 59 | 79 |
| 无法同时保持参与的原盘边界 | 276 | 10 |
| 本次尚未确认完整局部目标 | 356 | 469 |
| 源叶未明确区分正确/失败 | 25 | 0 |
| 中英题面颜色冲突 | 0 | 21 |

“目标尚未确认”与“必须保留原盘”分别记录，不把前者称作永久不可适配。两眼、封闭角空、对杀和枷等仍需专项目标证明；有限源树等价也不等于穷尽所有下法或证明永活。当前中文、英文来源经过审核，其余语言保留原题。

逐项 ID、来源摘要、目标证书、派生摘要及保留理由见 [简中 JSON](content-audit/kiosk19-audit-20261024.json)、[简中 CSV](content-audit/kiosk19-audit-20261024.csv) 与同目录英文/语言检查记录。两种已审语言均批准但验证失败 **0**，未审语言误接受 **0**。

## 独立审核与验证

[计划第二轮 Approved](../../../superpowers/reviews/2026-10-24-kiosk-tutorial-19x19-plan-astra-r2.md)；[代码第一轮](../../../superpowers/reviews/2026-10-24-kiosk-tutorial-19x19-code-astra-r1.md) 指出 4 个真实 GC 附加目标未被提吃证书覆盖。`66104 / 81717 / 81740 / 82153` 已留原，并增加完整 GC、全部注释与目标审核摘要校验。[代码第二轮最终 Approved](../../../superpowers/reviews/2026-10-24-kiosk-tutorial-19x19-code-astra-r2.md)，无剩余 must-fix。

负责人最终后端聚焦 **119 passed**；前端聚焦 **171 passed**；full 和 strict 构建通过，strict SSO/Kiosk 边界通过。审核者独立运行 **57** 项核心测试及全源审计，并实际检查字体 face、字号、主要屏幕操作、提子、应手、撤回、重摆和下一题。普通四路保留题及五手、两次应手、最终提六子的教程均有覆盖。

题目列表完整旧套件在原组件/原测试的基线上已有 13 项旧布局断言失败；新增同版本预览契约通过。本次只修本旅程，不宣称全量仓库测试通过。

## RK 实际验收

从干净的 published develop 导出 **391** 个受控 Python、新 policy JSON 和同源 full/strict static，**1188** 文件逐项哈希通过。发布前在线备份 SQLite 与旧代码/静态/标记；**458** 个配置、身份、模型、标定相关文件发布后哈希保持一致，字体偏好仍为 `kaiti/large`。仅停起 `smartbox-katrain.service`，Kiosk 和围棋 target 服务状态未变。

发布前实际运行代码是 `68db3ba5e`，旧 marker 仍为 `db32efe06`；以进程与受控文件哈希识别真实基线后备份，没有用旧 marker 回退代码。视觉绑定虽然显示 synced，但对应 session 在身份校验前即返回明确 404，确认是孤立残留；没有解绑活跃棋局或操作实体盘。

重启后通过真实“盒子主页 → 围棋 tile”恢复既有 `fan` 登录并回到原章节 URL；没有读取/注入 cookie 或伪造 generation。实际 1024×600 章节页完整加载 37 课，CDP 读取到 `TW-Kai` 真实字形与 `22px`。**11** 组真实设备 API 覆盖中央/边角/多分支训练派生、四边/附加目标留原、OGS 派生/留原及原生十九路，默认响应保持原盘。进程、资源、接口与服务记录见 [verification](verification.json) 和 [browser-final](browser-final.json)。

设备 board 模式选择 strict 入口；完整 full 产物也在同源 manifest 中逐项校验。本次未发布 TEST/PROD，也未更改 Galaxy 品牌。

设备原页一直保留。只读后台教程页未完成渲染，已关闭；十九路视觉对照来自已审核的本机真实 React → 真实 FastAPI endpoint 及设备真实接口/静态校验。没有将此称作设备十九路截图或实体摆盘端到端验收，未重新采集、标定、摆盘、创建对局或调用付费分析。

## 截图与回滚

- [RK 原页真实前后](screenshots/rk-font-before-after.png)、[叠加](screenshots/rk-font-overlay.png)、[差异](screenshots/rk-font-difference.png)
- [真实接口下的训练原九路/十九路对照](screenshots/local-training-source9-derived19.png)
- [OGS 原九路/十九路对照](screenshots/local-ogs-source9-derived19.png)
- [四路完整保留及原因](screenshots/local-original4-retained.png)
- [长题干字体前后](screenshots/local-font-long-before-after.png)、[来源弹层字体前后](screenshots/local-font-notice-before-after.png)

设备备份与可执行回滚材料保存在：

```text
/mnt/data/smartbox-deployments/20261024-kiosk-tutorial-19x19-09ee7f59f/
  manifest.json / verification.json / browser-final.json
  rollback.sh
  rollback/  # 旧受控源码、full/strict static、SQLite快照及保护文件哈希
```

[回滚脚本](rollback.sh) 仅恢复发布范围源码、静态与版本标记并重启围棋，不覆盖当前数据库、模型或标定。该脚本未执行。发布上传包与解包候选已清理，回滚材料保留；最终根分区约2.1 GiB可用，数据盘约15 GiB可用。
