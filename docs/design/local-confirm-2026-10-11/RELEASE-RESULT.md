# 本地逐手确认 · 双云发布结果

2026-10-12 02:10 CST。执行者：独立 `gpt-6-astra / max` 发布代理。**home-ubuntu、ucloud-v100 的 web 发布及必要验收已完成；RK3562 尚未部署，见 [RK 发布记录](./RK-RELEASE.md)。**

## 已发布版本

- KaTrain feature 与 develop：`0b086a7c19a403d5e3a01e86e58e7c42d6a224cf`；实现提交 `26cb632f9`，合并基线 `8bab85ef1`。
- SmartBox main：`a4a21cde7eb01f4e1078c078c37fb9b0fa020d64`，只更新 `vendor/katrain` 至上述 KaTrain SHA；原工作区其他人的改动保留。
- 两云以各自正在运行的 `katrain-kifu-search2:*‑a53f20678d09` 镜像为基础，覆盖已发布提交的 **35 个运行时差量文件与 439 个完整 web 静态文件**。没有传输研究资料、临时工具、凭据或数据库；保留 `a53f2067` 的现役搜索修复。
- 候选归档为 28,916,571 bytes，SHA256 `305ad6753b887faaf52211c33f183a4c9944d002265e16c78e1fc30c3dec8836`。部署驱动的离线导入探针随后调整为按生产顺序先导入 server；应用源码和静态产物未变。

| 目标 | 激活时间（CST） | 当前镜像 | 镜像 ID |
| --- | --- | --- | --- |
| home-ubuntu | 2026-10-12 02:05:02 | `katrain-local-confirm:home-0b086a7c19a4` | `sha256:58ffbfdad8730905a13be2deb3007ecc64f54701bfa6478326dcb1cd0ffd2a6a` |
| ucloud-v100 | 2026-10-12 02:07:45 | `katrain-local-confirm:ucloud-0b086a7c19a4` | `sha256:4734de8afa0b0f2055b399cbe966d0ac6c8986707c0af5fe6ae7a41a106709de` |

按 home → ucloud 顺序，仅执行对应项目的 `compose up -d --no-build --no-deps katrain-web`。两次切换前后均比较实际容器配置：除 `KATRAIN_BUILD_SHA` 更新外，env、命令、用户、工作目录、端口、网络、重启策略与所有挂载完全一致；其他运行容器 ID 全部一致。没有发布 cron/admin、KataGo、MinIO 或数据库，也未运行迁移。

## 在用会话决策

切换前的只读检查要求：实时 PvP 摘要未过期、无人参与/在线、无未保存的升降级本地局、无 cloud-local active/reserved 局、web 已建立连接数为 0。两台主机都通过。

home 有一条 2026-09-25 的非 cloud-local `pending_settlement` 历史记录，与当前进程的活棋无关；未修改它。ucloud 有 3 局无真人、无观众的后台机器人轮转。独立决策允许正常服务关闭回收这些演示局：既有 `PvpLobbyBotRuntime.stop()` 明确以 `Void` 收尾，`finish()` 不为 `Void` 记录棋谱或胜负。没有调用认输、落子、停一手、绑定、重置等棋局接口，也未改机器人配置。该决定已同步主代理；若出现真人活动，部署闸会停止重启。

## 实际服务验收

- 两云 `/api/v1/health` 均为 `status=ok`，本地引擎 `reachable`。ucloud 最后复查为 `running / healthy / RestartCount=0`。
- 两云实际容器内 **38 个文件 SHA256** 与发布候选一致，包括全部 35 个差量文件，以及未改动的 `kifu.py`、`session.py`、`requirements-web.txt`。运行时 `KATRAIN_BUILD_SHA` 均为完整发布 SHA。
- 两云实际 HTTP GET 的 `/galaxy`、`/kiosk`、`/kiosk/play` 都返回发布 index；HTML 引用的入口 JS、运行时 JS、UI/API chunk、CSS 和图标均为 200，字节/hash 匹配候选。
- 两云 `/api/v1/kifu/albums?page_size=2&lang=en` 返回 2 条数据，总数 **171,013**，现役棋谱入口正常。
- 两云对 `/api/local/ready` 各发出一次合法 body、明确不存在的 session 请求，均返回 **404 `{"detail":"Session not found"}`**。该结果来自新 handler 的按需导入之后，验证实际进程能加载确认模块；没有创建任何会话。
- 首次离线自检直接导入确认模块，绕过 Kivy 兼容初始化，在 ucloud 的无 Kivy 镜像失败。查明生产启动会先经 server/interface 初始化兼容层后，修正探针顺序即通过；没有安装 Kivy 或改变生产代码。

下列资源在**两云分别实际 GET**，字节与 hash 一致：

| 资源 | bytes | SHA256 |
| --- | --- | --- |
| `/kiosk` index | 4,593 | `a8b04a66b0f6b896df836163d2489a15620d694ebfb49873fb4823dbd2df5e6d` |
| `/assets/index-C3nN4iqo.js` | 14,647 | `ec25704bc1f8d92cfc37350e29ca6dce7aa44f0b4dcc0878863fff033f8e28af` |
| `/assets/sounds/voice/local_confirm_physical.mp3` | 74,592 | `1ae37d6f4c7b48725c8340ef37187265f877a708e406da1930bf1d5ed26446af` |
| `/assets/sounds/voice/local_confirm_screen.mp3` | 74,160 | `96eaa5d824882e2b79cd62cecbf65b1202daa518d85938bd199b3107e59611e1` |

## 实际浏览器页面

使用独立 Playwright CLI 会话与独立 SSH 转发，只读查看两云 `/galaxy/kifu`（1366×768）和 `/kiosk/play`（1024×600）。两云真实 Galaxy DOM 均显示 171,013 条棋谱及新入口 JS；两云 kiosk 主页均实际显示本地对局入口和诚实的云端相机未连接状态。没有开局、登录或修改已有对局。匿名 `/api/v1/auth/me` 的 401 属于预期；未见致命页面异常。

- [home Galaxy 截图](../../../output/playwright/local-confirm-cloud-home-galaxy.png)
- [home kiosk 截图](../../../output/playwright/local-confirm-cloud-home-kiosk.png)
- [ucloud kiosk 截图](../../../output/playwright/local-confirm-cloud-ucloud-kiosk.png)

上述三张截图已实际查看。ucloud Galaxy 截图等待字体超时，按比例约束收敛为真实浏览器 DOM、实际新脚本和 HTTP/资产证据，没有继续排查截图工具。没有重复已经通过的本地确认行为测试。

## 发布档案与回滚

档案保留在各目标主机：

- home：`/home/fan/Repositories/katrain/deploy/local-confirm-0b086a7c-20261012/`
- ucloud：`/opt/katrain/releases/local-confirm-0b086a7c-20261012/`

目录内的 `<target>-deployment.json` 是去敏的实际验收回执，`<target>-pre-switch-activity.json` 是切换前活动摘要；`release-source.json` 记录发布提交和资源 hash。`<target>-effective.private.json`、`<target>-rollback.private.json`、`<target>-plan.private.json` 权限为 0600，不打印或提交内容。候选目录权限为 0700。

旧镜像仍保留：home `sha256:3427ffc31d1dda4e8ddaf8b5db8fc3a1e36bd2a7d4f5e03f0cde0a3fe8963bd2`；ucloud `sha256:c37cf428020f82bb43028dbf4c3acd0c986a2da5d1a5599d07d7105feb75ab63`。如需回滚，先按相同在用会话原则检查，再在对应目录执行 `python3 cloud_release.py home rollback` 或 `sudo python3 cloud_release.py ucloud rollback`；它们只恢复旧 web 镜像和原有效 Compose，使用 `--no-deps`，不恢复/覆盖数据库。旧资源随旧镜像完整保留。若新服务完全无法启动而活动探针不可运行，应核实没有可服务的在用会话后，直接使用已保存的 rollback Compose 执行同一 web-only 命令，不扩大回滚范围。本次没有触发回滚。

部署产品版本固定为 `0b086a7c19a403d5e3a01e86e58e7c42d6a224cf`；后续纯发布记录提交无需重复构建或重启。
