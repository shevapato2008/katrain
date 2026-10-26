# 对弈首页五图标接入发布

旧修复 f37f7ea7f1b259b4ae2e54a166defd4228fbd9fe 留在独立分支，未合入 develop。主调试分支曾仅加入对比 PNG；图片并非产品代码。2026-10-26 的最新 develop93f2038a0 及 RK 同源实际页仍只有五个右箭头，没有前导图标。不能将此归因为缓存或已上线代码遭后续回退。

沿用已批准的 2026-10-23 Play Home Icons 计划和既定 Kiosk 设计，按最新源码最小接入七个产品/测试文件：五入口分别使用机器人、奖杯、双人、地球、带钟针的历史图标。按钮尺寸、标题字号、文案、无障碍名称、导航、禁用和平台品牌标记保持。新增 Phosphor v2 clock-counter-clockwise regular/fill 与 manifest；Smartbox canonical 资产包同步相同字节，避免下次共享资产同步丢失。

## 验证

- 产品候选 277b09e17808b956468a9227c8f0d7e115fe6b34；基线及修改后现有三组测试均 34/34，diff check 通过。
- 完整构建与 strict Smartbox 2D 构建通过；strict SSO/2D资源边界通过。
- 代表真实 Chromium 使用 strict 打包静态产物，1024×600、楷体最大，与设备一致。五前导 SVG 均可见24×24，五右箭头20×20，五按钮219×63，标题22px，无标题截断或页面溢出。[实机修改前 / 本机实际产物预览](screenshots/before-preview.png)、[预览几何](preview-dom.json)。右图使用仅浏览器中的只读固定输入，时钟及问候为当时时间；不是设备已部署凭证。
- 设备修改前截图为真实 `/kiosk/play`，只读捕获，没有导航、修改偏好或操作盘面。设备当时 source93f、PID825578，vision unbound。

独立 fresh Astra Max（gpt-6-astra/max）已审核七文件产品差异、Smartbox canonical 两SVG/manifest，并实际查看RK修改前及strict产物截图：Approved，无must-fix。未重复构建；沿用本轮34测试及full/strict日志。最终发布回执在操作完成后追加，未完成部署前不得以预览替代实机验收。

## 发布回执

| 项目 | 本次已核实版本 |
| --- | --- |
| feature / published develop | 4691484225b47fca7c6c7f8c8faa6edf6426a23d |
| Smartbox origin/main | f35db81b14f0713b02961cbf102509a842d9685f |
| vendor/katrain gitlink | 同上述 published develop |
| RK 实际进程 KATRAIN_BUILD_SHA | 同上述 published develop，PID834517 |
| 实际 strict 首页入口 | index-DgXSZku2.js |

按顺序完成 feature 追最新 develop（无冲突）及推送、develop 快进推送、Smartbox main 的 gitlink 与 canonical SVG/manifest 推送，最后才部署 RK。GitHub直连临时不可达时，仅该命令使用既有SSH隧道代理，没有改全局Git配置。部署来源是已发布develop，不是未合入的独立feature。

[真实 RK 前后图](screenshots/rk-before-after.png)左前右后，同1024×600；已实际看图，五个前导图标清楚可见。实际DOM的SVG path逐一与对应项目源资产一致，均24×24且有非零矢量边界；五个箭头20×20、文字22px、按钮219×63，无文字溢出。[真实浏览器校验](browser-verification.json)、[进程/文件/资源/保护校验](verification.json)。

393个受控Python、19路policy及同源full/strict共1191文件hash通过；462项配置、身份、硬件模型、相机标定、字体保护状态不变。原688个实际Python均先记录hash，并于备份/激活前检查未被并发修改。在线SQLite快照及旧源码/静态回滚材料留在数据盘。没有运行整机provision，没有云服务或棋谱数据写入，没有新建对局、付费报告或实体盘操作；仅重启围棋服务，Kiosk服务与围棋模式target不变。

服务重启后认证需要恢复，使用真实主页→围棋入口完成正常SSO，未读取/注入cookie。fan账号及原唯一标签 `/kiosk/play` 保持，最终认证HTTP200。设备相机、LED、模型与本地引擎健康，先前19路policy的原始、适配及保留例外只读校验通过。

回滚目录 `/mnt/data/smartbox-deployments/20261026-play-home-icons-469148422/`，含rollback脚本、394个旧受控运行文件、双static、标记与SQLite在线备份；没有执行回滚。上传tar及解包候选于收尾时清理，回执、manifest、前后截图和rollback保留。

该回执后续提交只保存在独立evidence分支，不改变实际部署source469148422，也不再推develop/main或重启RK；后续其他负责人的新发布不得被本回执回退。
