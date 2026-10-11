# RK3562 候选交付记录

2026-10-12。**候选包已准备；设备未部署，实际摄像头与物理摆盘未验收。**

- KaTrain 已发布 feature/develop：`0b086a7c19a403d5e3a01e86e58e7c42d6a224cf`。
- SmartBox 已发布 main：`a4a21cde7eb01f4e1078c078c37fb9b0fa020d64`，只修改 `vendor/katrain`；gitlink 和干净发布工作树的子模块 checkout 均指向上述 KaTrain SHA。
- 同源完整 web 与 `build:smartbox-kiosk-2d` 已成功。严格 manifest 为 `{"box_sso_strict":true,"schema":1}`，Box SSO 和 2D 构建边界检查通过。
- KaTrain-only 包：[katrain-local-confirm-rk3562.tar.gz](../../../output/local-confirm-release/katrain-local-confirm-rk3562.tar.gz)，224,240,252 bytes；SHA256 `7c21daf298c27c860d24fd93459c6cd53fbaac7d6a1cce01e29b6b346864870c`。
- 本地 [release.json](../../../output/local-confirm-release/release.json) 记录双仓提交、入口与 14 个资产/语音 hash。包由已提交源码和同 SHA 构建的两套静态资源生成，核对确认代码、视觉 worker、严格 manifest 和两段引导语均存在。

包和 receipt 是被 Git 忽略的本地交付物，不含 `.env`、数据库、硬件标定或研究档案。SmartBox 主工作区原有未提交修改未动；干净发布工作树在 `/private/tmp/smartbox-local-confirm-release-20261012`。

## 尚未执行的设备步骤

本机没有 `en10`，到 `10.0.0.3` 的路由落在 `utun4`，直接 SSH 被 reset；备用 `192.168.0.104` 也超时。独立发布代理已确认这是连接阻塞；没有把 ping/端口响应当作设备上线证据，也未修改网络。

独立代理另核实 home-ubuntu 到备用地址为同 LAN 直连路由（`dev wlp68s0 src 192.168.0.106`），批准仅一次通过该跳板读取设备身份。`ssh -J home-ubuntu -o ConnectTimeout=8 -o ConnectionAttempts=1 -o BatchMode=yes rk3562-local` 在 banner exchange 超时，exit 255；仍未得到 hostname/model。凭据未复制，未扫描或修改网络，到此停止连接尝试。

设备真实可达后，按 [发布决策](./RELEASE-DECISION.md)继续：读取设备身份和当前对局；仅在设备安全空闲时备份、staging 校验、KaTrain-only checksum dry-run 和切换。保留实际 `--vision-reference-check on`、标定、曝光、模型与其它棋种配置；不使用四棋整包 provisioning，不结束既有对局。

激活后需实际核对入口资产、服务/相机就绪，验收屏幕反复改选后单次确认与音效，以及实体按确认开启完整识别、成功后关闭和一个可重试失败场景。本地软件测试与候选包校验不能替代这些设备证据。
