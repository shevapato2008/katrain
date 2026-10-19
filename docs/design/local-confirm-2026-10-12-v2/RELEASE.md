# v2 发布与设备验收

2026-10-12。**代码、后端契约和最终 RK 实机视觉均已获独立 GPT-6-astra max GO；第二版已发布，交用户检查。**

- 产品源码：`17562ff2c0b7ac2e1cc866461ac7c30ff595da0a`，feature 与 develop 已正常推送；合入最新 `516249704` 无冲突，新增的 admin provider 变更未影响本切片。
- SmartBox main：`9afc7fe3d`，在最新 `419d2c7cb` 基础上只更新 `vendor/katrain`，提交 gitlink 与实际子模块 checkout 均指向上述产品 SHA；主工作区他人修改保留。
- 同源码 full 与严格 SmartBox 2D 构建通过；TypeScript 和 strict SSO / 2D 边界通过，manifest 为 `{"box_sso_strict":true,"schema":1}`。构建的已知大 chunk 提醒不影响本次验收。

## 发布范围和回滚

两云基于各自现役镜像做 static-only 薄镜像，只在真人/在线/未保存局/已建立连接为零且实时证据新鲜时切换 web。home 验收成功后才切换 ucloud，原有 Python、有效环境、挂载、网络及其它容器均保持。前端版本使用 `KATRAIN_FRONTEND_SHA` 独立标记，不改旧 `KATRAIN_BUILD_SHA`、不声称后台源码已整体升至新 SHA。

| 目标 | 实际镜像 / 前端入口 | 验收 |
| --- | --- | --- |
| home-ubuntu | `sha256:d77e508c535f418639cb08fe14daa974c32ca91d1c3471b08be581088354ba33` | 06:49:55 切换；health ok / local reachable，index与两个GamePage chunk等8个HTTP资产符合候选；38个原后台文件hash保持，环境/挂载及其它容器不变。 |
| ucloud-v100 | `sha256:338a2476b633b52115c35112b172e5d063b2575f311bc342d998372cf3c94153` | 06:50:14 切换；同项HTTP及后台、运行参数检查通过。 |
| RK3562 :8081 | strict index `7f70b7082446f827bca7ed5bf8c7bd7ec14c82826136d676a9d355211604eecd` | 761个候选静态文件全部hash匹配；143个新增/变更文件，共1,781,026bytes；PID108071及服务启动时间未变。 |

两云 full index SHA256 为 `a47ba5b9c6cdacdad7348d7af32cd7e1669fd54f2e40431ca1fa231714deac30`，实际只读 Galaxy 与 kiosk 入口预览通过。没有在云上新建棋局或改写正式数据。

RK 保留旧 hash 资产；同名文件用目标目录临时文件再原子replace，所有资产就绪后才切 index，没有原位覆盖历史 hardlink。后台仍为已发布 `0b086a7c1` 的本地确认增量和原板端其它基线，未改Python、unit、模型、reference、标定或其它棋种。根盘最后约678MiB可用，本次只增加约1.7MB；数据盘约24GiB可用。

RK候选、独立回滚文件、前后回执与助手在 `/mnt/data/smartbox-deployments/local-confirm-v2-17562ff2c/`。两云旧镜像/有效Compose保留，回滚材料在各主机 `/tmp/local-confirm-v2-17562ff2c/`；回滚也只切web且需保护在用局。相关无敏感回执及构建产物留在 ignored `output/local-confirm-v2-release/`，不提交环境或凭据。

## RK 实际操作

复用唯一 1024×600 / DPR1 Chromium，无Fixture。真实10分+3×30秒临时屏幕局，落子音开：

- 开局 `local_confirm_screen.mp3` 实际播放一次。
- 等待方切坐标 / 手数，两侧状态和实际坐标同步；最终坐标、手数均开。
- 先 E5，再 F6；确认前节点0、确认请求0、落子音0。一次确认只提交[5,5]，实际第1手、last_move=[5,5]、白方回合、status idle，预选清除。
- 一次 stone1.wav 调用时画面已显示第1手，未有预选标记；没有重复落子音。
- 双侧224×516，大确认190×108，顶部正常“第1手 · 19路”、双方“停一手”、精简文案和可触达的显示按钮。最终画面 [rk-final.png](./rk-final.png) 已获 [独立最终视觉 GO](./REVIEW.md)。

临时验收局通过“退出不保存”结束，未保存正式棋谱；设备停在新版对弈首页供用户开局检查。预览的Fixture壳、健康/钟路由、隔离DB及凭据均已删除，测试server/Vite及本地预览浏览器已关闭，生产无模拟业务数据。

相机、标定、recognition 与LED发布前后仍未连接/未就绪，model ready；最后 vision unbound、bound_session_id=null。**屏幕操作与软件流程验收通过，不代表实体摆盘识别已通过设备验收。** 本轮不扩成硬件接线/标定任务。

磁盘只读检查发现约166MiB低风险冗余，清单见 [DISK-REVIEW.md](../local-confirm-2026-10-11/DISK-REVIEW.md)。历史备份、棋谱和模型未删除；1.4GiB旧树有hardlink，不能把du大小当作可释放容量。
