# 本地对局 v2 发布决策

2026-10-12，独立 `gpt-6-astra / max` 用户代理决策。已重新读取本仓库及 SmartBox 的实际 `AGENTS.md`、v2 设计/审核/计划和前次发布记录。**此文批准发布范围与方法，不代表当前实现、审核或部署已经完成。** 本轮没有操作生产环境。

## 决定与依据

**完成 feature → develop → SmartBox 精确 gitlink → home-ubuntu → ucloud-v100 的发布链，并将同源严格 2D 前端部署至 RK3562。** 前次仅一行标题修正的两云暂缓决定不适用于本轮。

用户已明确升级为重新设计、真实前后端接入、代码与视觉审核、重新部署并交用户检查。[本仓库发布规则](../../../AGENTS.md)要求集成到 develop、更新父仓引用并部署两云；这是一次包含双侧真实显示开关及文案/布局调整的完整界面发布。全局比例原则用于限制改动、检查和重启的范围，不据此默默省略明确的发布目标。

当前实际实现只改 `LocalConfirmGame.tsx`、对应 CSS 和组件测试；复用已部署的确认接口、双钟、视觉窗口与幂等。**无需为了“前后端实现”另改 Python、数据库或设备配置。** 若审核或最新 develop 合并带来实际契约变化，再单独处理真实差异；不将无关后端升级混入静态发布。

## 最小集成与产物

1. 完成已经开展的聚焦组件测试、同尺寸运行时视觉核对、独立代码/视觉审核与必要修正。复用已有确认行为验证，不再跑全量 Python/AI 测试或全状态截图。
2. fetch 最新 develop，合入 feature 并核对结果；正常推送 feature，再合入/推送 develop。最新合并若没有改变已验证代码，不重复整套审核。记录最后的产品发布 SHA。
3. 从最新 SmartBox main 的干净发布 worktree 更新唯一 `vendor/katrain` gitlink 至该 SHA，提交并推送；保留主工作区他人的修改。核对提交的 gitlink、实际子模块 checkout 与产物源版本一致。
4. 从最终产品源码生成一次完整 web 和 `build:smartbox-kiosk-2d`，记录文件清单、index/入口 JS/CSS hash。strict manifest 继续精确为 `{"box_sso_strict":true,"schema":1}`。不传 Fixture、设计稿、研究档案、测试工具或数据库；不因随后纯记录提交重建产品。

## 两云：只替换 web 镜像中的静态资源

前次已发布的运行时基础为 `0b086a7c1` 的确认后端及现役棋谱修复。此前只读检查发现当前两云均**没有 static bind mount**；较早部署文档中的宿主静态挂载不能直接假定仍有效。执行前重新核对实际容器、image digest、挂载和 Compose 链，防止覆盖并行发布。

- 在每台主机的**实际现役 image digest**上构建仅含新完整 web 静态资源的薄镜像。保留 Python、依赖和旧 hash 资产；不删原静态树，不用较旧通用基础镜像重建，不修改 cron/admin、引擎、MinIO 或数据库。
- 保存旧 image、旧有效 Compose 和实际 index/hash。沿用当前完整 Compose 配置，仅选择新 web image，保留环境、命令、端口、网络、用户、挂载和所有 overrides。不新增静态挂载架构，不依赖只复制到容器可写层、下次重建即丢失的临时补丁。
- 复用前次的在用会话判据，在切换前重新读取真人参与/在线、实时对局、未保存的升降级局及已建立连接。**有在用真人局就不重启、不替其结束，不把 SGF 备份当成恢复整个会话的保证。** 允许先备妥镜像与回滚配置，待安全空闲继续。仅无真人/观众的后台机器人轮转，可按前次已核实的正常 `Void` 关闭行为处理，不记用户胜负、不另调棋局写接口。
- home 通过后才切换 ucloud。使用当前项目的 `compose up -d --no-build --no-deps katrain-web`；不执行整栈 `up`。发布后确认 web 之外的容器未改变。
- 每云只核对 health、实际 index 及所引用的新入口/修改 chunk 的 HTTP hash，并只读打开一个实际 Galaxy 页面和一个 kiosk 入口。v2 的互动与视觉在 RK/本地真实运行时验收，不为云验收再开棋局、改写正式数据或重做后端回归。

若云端有在用局而暂时无法切换，继续无依赖的 RK 交付，并明确报告该云“候选已准备、待安全窗口”；不能把整条发布链记为全部完成。用户当前授权已足够执行空闲后的切换，无需再要求一次笼统发布许可。

两云回滚使用保存的旧 image 与原有效 Compose，仍仅切换 web，并遵守同一真人会话保护规则。静态发布不需要数据库恢复；旧镜像及旧资源保留。若 home 失败，先处理/回滚 home，不继续 ucloud。

## RK3562：静态切换，不重启后台

RK 当前服务端口为 **8081**，Python 后端仍为已验收的 `0b086a7c1` 本地确认增量，其余板端源码基线保留。v2 只更新 full/strict 静态，不重启 `smartbox-katrain.service`，不写 Python、unit、venv、模型、视觉标定、reference 配置或其他棋种。

- 候选和独立回滚副本放 `/mnt/data/smartbox-deployments/`；确认数据盘已挂载。根盘只写实际新增/变更的静态文件，不上传整包，不清理历史文件来腾空间。
- 保留旧 hash 资产。先写齐并校验新资产，再切换 index；同名变化文件使用**目标目录内的临时文件 + `os.replace`**，避免原位改写历史硬链接。跨 `/mnt/data` 到 rootfs 的移动不是原子替换。备份使用独立副本，不新增共享写入 inode。
- 静态文件发布不终止现有会话；实际浏览器刷新/验收前仍须确认没有新的在用局。前次用户允许结束的是指定临时验收局，不是今后所有局的通用清除授权。
- 复用唯一 renderer，在 1024×600 查看真实页面：标题为正常路数、按钮为“停一手”、精简文案、双侧坐标/手数控制同一真实棋盘显示状态，确认键保持获批大小；聚焦验证一次反复预选后仅最后一点提交。已足够的本地错误状态证据不在设备上反复重拍。
- 核对真实 8081 index/入口 hash、strict manifest、health 和后台进程未重启。相机/LED 在此前及当前基础版本均未连接；保持诚实状态，不重装或重新标定，也不将本次前端验收写成实体摆盘识别通过。

RK 回滚只原子恢复保存的旧 index 及确实变化的非 hash 静态文件；旧 hash 资产仍在，因此无需重启后台或回退 Python。新资产暂留即可，不因回滚清理其他版本。

## 版本记录必须表达实际覆盖范围

最终回执分别记录：发布到 feature/develop 的完整 SHA、SmartBox 父提交与精确 gitlink、两套产物的源 SHA/hash、两云实际 image ID/基镜像与 HTTP hash、RK 实际 index/hash及无重启证据。

**Git 源版本与部署范围分开写。** 新前端来源于最终发布 SHA；两云仍保留既有 Python/配置，RK 仍为 `0b086a7c1` 确认后端增量加原板端基线。可使用独立的 frontend revision/发布回执表达新 UI 版本，不把整个设备源码树或保留的运行时都标成新 checkout。健康接口的通用应用版本不能替代资源 hash。

依据：[v2 设计](./DESIGN.md)、[独立视觉决定](./REVIEW.md)、[实施计划](../../superpowers/plans/2026-10-12-local-confirm-v2.md)、[前次双云实际发布](../local-confirm-2026-10-11/RELEASE-RESULT.md)、[RK 基础版本与硬链接修正](../local-confirm-2026-10-11/RK-RELEASE.md)、[只读磁盘检查](../local-confirm-2026-10-11/DISK-REVIEW.md)、[SmartBox AGENTS.md](/Users/fan/Repositories/smartbox-software/AGENTS.md)。
