# 共享USB Hub自动恢复代码审核

新的独立 `gpt-6-astra` / `max` 对产品 `cddc52fa6..dfbe00dae` 和本次发布工具完成审核，最终 **Approved**，无剩余 Critical / Important。A/B/C/D在质量审核前均已通过独立规格核对。

首轮四项问题均已补充red→green并修正：停机与最终复核/launch的竞态；发布器坏episode记录误放行；第二次瞬断未作废旧确认；固定5秒owner等待使8秒复位期限拖到10秒。复位现在按deadline唤醒，普通状态仍5秒，无常驻高频线程。

## 验证边界

- 控制器相关Python分组234+182+28，共444通过；前端三个直接测试文件165通过；full/strict按锁文件`npm ci`后构建通过，strict SSO/Galaxy/three/live边界通过。没有声称全量pytest或全量UI通过。
- 独立Astra复验37项Python、2项UI、26项RK工具、10项云工具通过，最终工具hash全匹配。控制器也复跑36项发布工具用例。
- 两个旧UI断言失败（Board渲染次数、旧标定5步）已在原HEAD复现；web_ui全局Mock interface造成旧Local组合失败亦已用旧HEAD archive复现，新测试未修改该全局夹具，新增32项能同进程通过。
- 1920×1080本地真实strict浏览器、隔离假身份/3手局fixture：10项检查通过，瞬断保持同DOM/URL/局面/身份/语言、禁确认且无标定弹窗；恢复后显式一次确认使用新请求，仅推进一手。浏览器/server已关闭；未调用生产/设备API。证据在控制器 `output/diagnostics/typec-camera-20261109/ui-preview/`。
- 16:52人工Hub恢复已实机成功；本自动功能的板上异常恢复与物理拔插仍由发布阶段另验，不能用本地或旧人工试验替代。

## 已审核发布工具

控制器目录 `output/releases/usb-hub-recovery-20261109/` 的 `REVIEW-HASHES.sha256` 固定精确工具字节。

| 工具 | SHA256 |
| --- | --- |
| rk-release.py | `976b27e67601daea0c9d448db369e49804957c678538c3c210896bcc8c20e62b` |
| cloud-release.py | `953eaba6e467f01949774dcdd17aa074f22e6ab51e32c0fdab4801ab8fa8f179` |
| native-release.py | `92769832dc735ceacb73eba79337bf3d6a066d429e0d8ae2e3594738feb5881c` |

本任务native副本相对原审核reference `98e816ac...` 的精确差异已保存并复核：只允许code-only构建SHA环境补丁，fresh商业配置（paused/disabled或enabled/live）、微信参数和只读secret bind原样保留；prepare/apply同函数重建一致。原reference未修改。本次不会将其他授权会话新启用的会员/支付回退。
