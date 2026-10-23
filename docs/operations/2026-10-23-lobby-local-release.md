# 大厅统一对局与本地标定续开发布

用户已在本地实现审核通过后明确授权集成、推送、Smartbox 子模块更新及 RK3562 部署；本记录取代先前验证文档中“仅本地、未授权部署”的当时交付边界。棋谱同步调查和修复不属于本次范围。

## 发布输入与合并验证

- 功能实现基线 `5016186ed`，大厅本地交付 `d345a45e8`；包含已审核本地对局标定成功续开 `fb19e95c2`。
- 当前 `origin/develop` 为 `ab29b9927ddf7640de68cd1028369462c99422b0`。功能分支合入其 25 个提交；唯一冲突为 `PvpLocalSetupPage.tsx` 两行 imports，合并 `useCallback` 与新版 MUI Dialog 依赖，未改双方业务逻辑。
- 合并后：本地设置页、GeometryContext、PlayInputGuard **46 passed**；大厅/会话/面板等前端范围 **219 passed、1 既有 develop 测试断言失败**；相关后端 **96 passed、3 先前已证实的旧 fixture 失败**；大厅 Playwright **3 passed**；`build:smartbox-kiosk-2d` 通过，严格 SSO/kiosk 边界通过。
- 新发现的 develop 既有失败是 `GameControlPanel.clock.test.tsx` 的“未配置时限的自由对弈忽略继承用时、不调 onTimeExpired”：新版 paired 卡两侧都显示“不限时”，旧 `getByText` 只允许一个。合并树的该组件和该测试与 `origin/develop` 完全一致；没有为本次发布扩改它。
- 保留已证明的 PhysicalBoardGuard 旧文案失败、三个 box MagicMock fixture 失败；没有把它们伪报为通过。
- 合并后真实 1024×600 大厅截图已重新检查，board/rail、四键/显示键尺寸、图标和无溢出断言通过。截图在忽略目录 `output/playwright/lobby-game-unified/`。

## 部署策略

严格按用户顺序先发布功能分支，再将其合入并推送 develop，再更新 Smartbox main 的 `vendor/katrain`，最后部署所需后端及 RK。

两云当前 web server 与功能基线字节一致，缺少领地 helper/route。使用现有运行镜像为基础，只加入已发布 commit 的新 helper 和对应 server；保持既有 compose 环境、挂载与服务身份，只重建 web，不重启 GPU、cron、数据库或对象存储，不运行数据导入。

RK 使用既有 git archive + 精确 gitlink 导出 + 校验和 rsync 的发布机制，限定围棋运行包/静态产物；不执行会更新其他棋类及数据库的四棋全量脚本。先按存储文档恢复根分区至少 2 GiB 余量，备份、上传、解包和回滚文件放 `/mnt/data/smartbox-deployments/`。保留数据、模型、配置、鉴权和硬件标定。实际部署及版本回执在后续记录补齐。
