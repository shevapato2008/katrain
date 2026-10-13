# RK3562 候选交付记录

2026-10-12。**本地逐手确认软件增量已于 06:10 部署到 RK3562；实际摄像头与物理摆盘未验收。** 下方保留早期候选包记录；实际部署采用末节的小范围差量。

- KaTrain 已发布 feature/develop：`0b086a7c19a403d5e3a01e86e58e7c42d6a224cf`。
- SmartBox 已发布 main：`a4a21cde7eb01f4e1078c078c37fb9b0fa020d64`，只修改 `vendor/katrain`；gitlink 和干净发布工作树的子模块 checkout 均指向上述 KaTrain SHA。
- 同源完整 web 与 `build:smartbox-kiosk-2d` 已成功。严格 manifest 为 `{"box_sso_strict":true,"schema":1}`，Box SSO 和 2D 构建边界检查通过。
- KaTrain-only 包：[katrain-local-confirm-rk3562.tar.gz](../../../output/local-confirm-release/katrain-local-confirm-rk3562.tar.gz)，224,240,252 bytes；SHA256 `7c21daf298c27c860d24fd93459c6cd53fbaac7d6a1cce01e29b6b346864870c`。
- 本地 [release.json](../../../output/local-confirm-release/release.json) 记录双仓提交、入口与 14 个资产/语音 hash。包由已提交源码和同 SHA 构建的两套静态资源生成，核对确认代码、视觉 worker、严格 manifest 和两段引导语均存在。

包和 receipt 是被 Git 忽略的本地交付物，不含 `.env`、数据库、硬件标定或研究档案。SmartBox 主工作区原有未提交修改未动；干净发布工作树在 `/private/tmp/smartbox-local-confirm-release-20261012`。

## 早期连接阻塞记录

本机没有 `en10`，到 `10.0.0.3` 的路由落在 `utun4`，直接 SSH 被 reset；备用 `192.168.0.104` 也超时。独立发布代理已确认这是连接阻塞；没有把 ping/端口响应当作设备上线证据，也未修改网络。

独立代理另核实 home-ubuntu 到备用地址为同 LAN 直连路由（`dev wlp68s0 src 192.168.0.106`），批准仅一次通过该跳板读取设备身份。`ssh -J home-ubuntu -o ConnectTimeout=8 -o ConnectionAttempts=1 -o BatchMode=yes rk3562-local` 在 banner exchange 超时，exit 255；仍未得到 hostname/model。凭据未复制，未扫描或修改网络，到此停止连接尝试。

设备真实可达后，按 [发布决策](./RELEASE-DECISION.md)继续：读取设备身份和当前对局；仅在设备安全空闲时备份、staging 校验、KaTrain-only checksum dry-run 和切换。保留实际 `--vision-reference-check on`、标定、曝光、模型与其它棋种配置；不使用四棋整包 provisioning，不结束既有对局。

激活后需实际核对入口资产、服务/相机就绪，验收屏幕反复改选后单次确认与音效，以及实体按确认开启完整识别、成功后关闭和一个可重试失败场景。本地软件测试与候选包校验不能替代这些设备证据。

## 连接恢复后的实际发布

用户于 2026-10-12 确认 `rk3562-local` 可用并要求部署。读取设备身份为 `gzpeite / GZPEITE RK3562 P04 Board`，服务实际端口 **8081**。独立 Astra max 确认小范围增量 GO，详见 [发布决策](./RELEASE-DECISION.md)末节。

- 06:10:43 激活 `0b086a7c1` 的 **9 个 Python 文件、2 段语音和同源 full/strict 静态**，保留板端其余基线；没有声称整棵源码等于该提交。
- 切换前复核唯一 renderer 在 launcher、vision unbound、无 8081 游戏连接。只重启 `smartbox-katrain.service`，unit/Environment/实际 argv 指纹保持一致，包含 reference `on`。
- 当前发布档案和完整回滚副本在 `/mnt/data/smartbox-deployments/local-confirm-0b086a7c-20261012-0605/`；数据盘有约 24GiB 空闲。本次自行创建的根盘 staging 已移到数据盘，没有清理历史文件。
- 实际 772 个源码/静态文件 SHA256 全部匹配候选；实际 `/kiosk` 返回严格 2D index（`6ef277ed…`），入口 JS/CSS 与两段新语音 hash/字节一致。health 为 `ok`，本地引擎 reachable、RKNN model ready。
- camera_connected、camera_ready、geometry、recognition、LED 在发布前后均为 false。软件发布成功，不能据此宣称实体识别验收通过。
- 复用设备唯一的 1024×600 Chromium，经 launcher 正常进入新版 kiosk 和本地对局。用户同时在临时验收局操作两手，真实媒体观察记录到各一次画面后 stone 音效；自动化预选检查受同时操作影响终止，不将其计为自动化 PASS。用户随后明确允许不保留该局，已通过“退出不保存”结束，未存为正式棋谱。

## 硬链接修正与新版界面

磁盘核对发现 vision 的 `ipc.py`、`service.py`、`worker_inprocess.py` 与两处历史树共享 inode。本次初始原位写入连带改了旧副本；已用独立的 before-source 备份拆开运行 inode并恢复历史版本，逐项核对当前新 hash 和历史旧 hash，三份运行文件现在均为单链接。部署/恢复助手已改为同目录临时文件再 `os.replace`，避免未来原位改写共享 inode。

现场还发现旧通用 Pass 文案显示“虚着”、路数标题遗漏翻译参数，以及常驻说明过多。用户已要求重新设计、直接展示坐标/手数，并授权独立 gpt-6-astra max 代理进行视觉审核和决策。第二版 Artifact、实现及再次部署记录见 `docs/design/local-confirm-2026-10-12-v2/`；此节记录的是第二版之前已发布的软件基础。
