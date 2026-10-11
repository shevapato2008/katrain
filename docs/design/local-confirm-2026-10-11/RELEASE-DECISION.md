# 本地逐手确认发布决策

决策时间：2026-10-12 01:27 CST。按用户授权，由独立 `gpt-6-astra / max` 决策代理核对。此文是发布前决策，**不是已发布或设备验收通过的记录**。调查只读；本次仅新增此文，没有提交、推送、部署、重启或操作棋局。

## 决定

完整发布顺序为：**完成真实后端和针对性验证 → 同步并发布 KaTrain feature/develop → 发布 SmartBox 的精确 submodule pointer → home-ubuntu → ucloud-v100 → RK3562 安全切换及验收**。

- RK3562 是此次产品验收的主要目标。两云更新仍属于完成条件：[仓库 AGENTS.md](../../../AGENTS.md) 明确要求功能集成发布时部署两云；用户强调 RK3562，没有撤销此要求。该功能本身不依赖更新云端 KataGo，但规则要求发布的一致性不能默默省略。
- 两云只更新本次相关的 KaTrain web 代码与前端。没有 cron、admin、引擎或存储变化时不重建这些服务，不迁库、不换环境、不调整 MinIO。遵循 [server-deploy](../../../.agents/skills/server-deploy/SKILL.md) 的选择性部署原则，并保留每台主机实际生效的 Compose overrides、挂载和运行时配置。
- RK3562 采用 **KaTrain-only** 交付。现成 `scripts/deploy-main-to-rk3562.sh push` 会同步四棋、安装五子棋运行时、检查/迁移其数据库并启停多个模式，明显超过本次范围；不直接执行整包 `push`。复用它的精确提交归档、checksum dry-run、严格 kiosk 构建和视觉就绪判据，不扩大为部署工具改造。
- 当前网络阻塞不阻止完成代码集成与两云发布，但它阻止声称“RK3562 已部署/整项已完成”。保留可恢复的候选产物和剩余步骤，诚实报告此项未完成。

## 已确认的目标与阻塞

以下是本次只读快照；实际发布前重新读取一次版本，避免覆盖并行发布。

| 目标 | 已读到的事实 | 决策 |
| --- | --- | --- |
| KaTrain feature worktree | `feature/kiosk-local-play`，HEAD `9a36555a9bc9cc6bdb16d77fe8fb71f6b177a1c8`；本次前端尚有未提交文件；后端仍在开发 | 不是可发布版本；先完成实现和审核 |
| develop refs | 本地 `develop=56f53fa4d29ee041faa39f00d5b27a12613ee0e5`，已有 `origin/develop=a53f20678d099ae7304e425a0b944802a7890186` | 发布前 fetch，以最新远端为准，不以陈旧主工作树打包 |
| SmartBox | `main=b7212f753`；gitlink 和实际 `vendor/katrain` 都是 `a53f20678d099ae7304e425a0b944802a7890186` | 另建干净发布 worktree，仅提交新的 gitlink |
| home-ubuntu | SSH 可用；`katrain-web` 为 `katrain-kifu-search2:test-a53f20678d09`；`/api/v1/health` 为 `status=ok`、本地引擎 reachable | 可部署；保留当前版本新增的棋谱搜索修复 |
| ucloud-v100 | SSH 可用；`katrain-ucloud-katrain-web-1` 为 `katrain-kifu-search2:prod-a53f20678d09`，Docker healthy；同一 health 检查正常 | home 验证后再部署；保留当前修复和有效配置 |
| rk3562-direct | 主代理 SSH 遇到 key exchange reset；本机 `en10` 不存在，`route -n get 10.0.0.3` 显示 `utun4` | 是部署脚本已记录的 VPN 假连通形态；不能据端口或 ping 宣称设备在线 |
| rk3562-local | 主代理对 `192.168.0.104` 的 SSH 8 秒超时；本机路由为 `en0` | 备用入口也未得到设备身份 |
| 现成隧道 | 未找到 SSH/autossh 本地 TCP 监听；SSH 配置只有上述两个 RK3562 alias | 本次有限 fallback 已用尽；停止泛化网络排障，不改 VPN、路由或设备网络 |

两云当时运行的 web 镜像 ID 分别为 `sha256:3427ffc31d1dda4e8ddaf8b5db8fc3a1e36bd2a7d4f5e03f0cde0a3fe8963bd2` 和 `sha256:c37cf428020f82bb43028dbf4c3acd0c986a2da5d1a5599d07d7105feb75ab63`。Compose 工作目录分别为 `/home/fan/Repositories/katrain/deploy/kifu-search2-a53f2067-20261012` 和 `/opt/katrain/releases/kifu-search2-a53f2067-20261012`。有效配置文件包含私密值，不打印或提交其内容。健康接口的 `version=1.17.1` 不能证明代码提交一致，须另核对提交、镜像和实际资源 hash。

SmartBox 主工作区已有他人的 `provisioning/provision.sh`、`vendor/hermes-agent`、`docs/demos/`、`docs/gomoku-web-lessons-outline.md` 及 power-gate 文件变化。本次不 stash、清理、提交或同步它们。

## 最小执行步骤

1. **关掉开发缺口。** 按[实施计划](../../superpowers/plans/2026-10-12-local-turn-confirmation.md)完成真实 `/api/local/confirm`、服务端计时与幂等、实体盘识别启停及 reference 后处理、屏幕预选与一次音效。运行受影响前后端测试、完整 web build 和 `build:smartbox-kiosk-2d`；独立审核只覆盖本次实际风险。前端视觉已获用户确认，无需重复全套设计验收。
2. **按新 develop 集成。** fetch 最新远端，merge 到 feature，处理真实冲突并核对合并后的改动，再提交和推送 feature。随后将其合入以最新远端为基线的 develop，正常推送，不 force。develop 在其他 worktree 被占用或有他人改动时，用独立 integration worktree 完成合并，不切换/清理他人的目录。记录发布后的完整 SHA。
3. **更新 SmartBox 精确引用。** 从最新 `origin/main` 建干净临时 worktree，将 `vendor/katrain` 指向已发布 develop SHA，仅提交此 gitlink，正常推送父仓。核对父提交的 gitlink、子模块 checkout 与打包 SHA 三者一致；主工作区其余变化保持原样。
4. **生成同源产物。** 从上述已提交版本导出 KaTrain 源码，按需生成完整 web 和严格 SmartBox 2D kiosk。后者必须含 `.smartbox-build.json` 且为 `{"box_sso_strict":true,"schema":1}`；不能用普通 `build:kiosk-2d` 代替。包括新增逐手确认语音。记录源码 SHA、父仓 SHA、index/入口资产 SHA256，不带 `.env`、凭据、数据库、硬件标定和未跟踪杂物。
5. **两云顺序发布。** 先重新记录现役 image/config/index 并准备回滚；核对已合入当前 `a53f2067` 系列修复。用各自当前有效 Compose 配置，仅替换 web 候选镜像/相关资源，保留部署特有覆盖。home 通过 health、实际 Galaxy/kiosk 页面和资源核验后再发布 ucloud。不得只更新前端而遗漏新确认后端。若候选会丢掉现役必要修复，先解决差异，不盲目覆盖。回滚只恢复本次 web/image/index，不碰数据库。
6. **RK3562 仅在真实可达且安全空闲后切换。** 读到设备自身 hostname/model 才确认身份；读取当前 launcher 模式、当前浏览器 URL、`vision/status` 绑定会话和已有对局状态。先保留旧源码、静态目录、有效 unit/视觉配置的回滚副本；在独立 staging 目录核对候选和 dry-run。仅同步 KaTrain 必要文件与两个静态产物；源码根不 `--delete`，静态目录才按既有配方原子替换或精确清理。有效配置已满足要求时不重跑 provisioning、不重装 venv、不改 systemd。安全空闲条件满足后才重启 `smartbox-katrain.service`，保持模式与棋盘配置，随后进行下面的设备验收。

## 已有设备局的处置决定

**保留，不代下、不代停、不代认输、不重置、不解绑、不做 SGF 重新导入。** `SessionManager` 的普通会话保存在进程内 `_sessions`；现有实现没有证明本地局可跨重启完整恢复。SGF 导出只能保留棋谱，不能证明保住 session、节点身份、双钟和剩余读秒，因此“先导 SGF 再重启”不是安全等价替代。

- 若发现尚未结束的既有局，允许只读保存必要的 state/SGF 到受限临时证据目录，**不能据此重启服务或替换活跃运行目录**。候选可在独立目录准备，保持现役进程和棋局。待真实对局结束/设备安全空闲后继续；无需用户再次批准已授权发布，但不能替用户决定旧局结果。
- 不将“用户睡着了”“页面无人触碰”“棋钟仍在走”推断成可以结束对局。不能为消除旧局阻塞新增持久化框架。
- 实体识别是共享硬件服务；另开隐身窗口或新 session 仍可能重绑定同一相机/物理棋盘。旧局在用时不以“隔离测试”名义绑定视觉。也不启动第二个摄像头 worker/第二套 renderer 来绕过 RK3562 的 2GB 约束。
- 没有真实设备连接、没有可操作的实体盘或没有安全测试局时，硬件逐手确认验收留待继续；本地真实代码测试和帧重放可以证明软件边界，不能冒充实体盘验收。

## 代表性验收与停止条件

发布前已在测试中覆盖复杂失败/并发边界；现场只做以下最小代表性检查，不重新铺全量回归。

| 检查 | 实际证据与通过条件 |
| --- | --- |
| 运行版本与资源 | 读实际服务的 `/kiosk` HTML，解析其引用并 GET 至少入口 JS/CSS，核对候选 SHA256；页面请求无 404、运行无致命异常。RK 还核对严格 manifest、两段开局语音能取到。`git HEAD` 或静态目录存在不足以通过。 |
| 两云代表页 | 通过真实服务各开一页 Galaxy 和一页 kiosk，1024×600 检查 kiosk，确认仍可加载现有棋谱/对局入口。只读代表页即可，不触碰真实用户对局。 |
| RK 服务/相机 | `smartbox-katrain.service` active，`/api/v1/health` 正常；配置视觉时 `/api/v1/vision/status` 的 `enabled`、`camera_connected`、`camera_ready` 全 true。仅 HTTP 200 不足。部署可达检查不强迫重新标定；实体功能测试前再要求 geometry/model/recognition 对该局就绪。 |
| reference 真生效 | 读取有效 `ExecStart`，保留 `--vision-reference-check on`、RKNN 模型、固定曝光和 `/var/lib/smartbox/hardware/vision`。仓库 `20-vision-led.conf` 已是 `on`，Python 默认为 `shadow`；后者不拦假阳性。再以运行态配置/限定的诊断日志或确认路径已有诊断核对实际 worker 生效，不能只看文件。不得打印整套 environment 或清空参考/标定状态来“通过”。 |
| 屏幕真实提交 | 在安全的专用验收局，先点 A 再点 B：只有最后预选标记，确认前手数/真实棋盘不变、无落子音；确认后恰好落 B、换方、短音一次。重复同一请求不得再次入谱或响音；下一手可继续。用实际后端响应确认 `local_confirmation.enabled`，不能因旧服务降级布局而误判通过。 |
| 实体真实提交 | 安全测试局中，等手时相机采集保持就绪而确认识别未运行；一手实体落子后点击本方确认才开始识别，双钟暂停、动作锁定；点击后的稳定画面通过同一自由对弈识别和 reference 链路，成功只入一手、换方、音效一次，识别关闭。再选无子/多子/提子未拿净中的一个可复现失败，确认不入谱不换方、恢复本方计时、可整理重试。无法真实摆盘时明确记为未验，不制造通过记录。 |
| 既有局保护 | 切换前若存在进行中旧局则停止 RK 激活；不要调用 new-game、move、pass、resign、vision bind/reset、SGF load 等写接口。“SGF 已备份”不解除此条件。 |
| 现场失败 | 相机就绪、真实资产或基本确认行为失败时，只回滚本次版本及确实改过的配置。保留硬件状态、棋谱库和其他模式；不扩大重装、联网或校准排障。 |

最终发布报告分别写明 feature/develop/SmartBox 完整提交、两云镜像与实际资产 hash、RK 已激活版本及现场证据。当前决定允许继续所有无依赖的已授权工作；**没有 RK 真证据时最终状态仍是“集成/云端已完成，RK 受设备连接或既有局阻塞，待继续”**。

## 依据

- [KaTrain AGENTS.md](../../../AGENTS.md)：明确 integration/deployment 顺序。
- [SmartBox AGENTS.md](/Users/fan/Repositories/smartbox-software/AGENTS.md)：2GB、native systemd、范围隔离。
- [RK3562 既有部署脚本](/Users/fan/Repositories/smartbox-software/scripts/deploy-main-to-rk3562.sh)：直连真假判断、提交一致性、strict build、相机可读性判据及全栈 push 的范围。
- [视觉 drop-in](/Users/fan/Repositories/smartbox-software/provisioning/systemd/smartbox-katrain.service.d/20-vision-led.conf)：reference `on`、RKNN/曝光/设备状态路径。
- [SessionManager](../../../katrain/web/session.py)、[vision status](../../../katrain/web/api/v1/endpoints/vision.py)、[确认契约](../../../katrain/web/ui/src/api.ts)：当前会话与验收接口边界。
- [近期云端发布记录](../../operations/report-polish-2026-10-08.md)：保留有效配置/覆盖和实际资源核验的既有做法；具体基线以上述本次实时读取为准。
