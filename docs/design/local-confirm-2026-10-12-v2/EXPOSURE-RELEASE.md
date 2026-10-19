# 曝光标定与本地首手确认：发布验收

2026-10-12。用户授权立即更新，保留已保存棋谱和报告。计划两轮审核、独立 Astra max 前端视觉审核及最终代码审核均 GO；实现使用 subagent-driven-development。产品版本 `754c24b2e90233023eacdbf2309b0ca5348480ca` 已合入并推送 develop，SmartBox 产品发布指针为 `bb0f45654`。

## 实际修复

- 曝光准备等待真实收敛与手动模式读回，替代三次缓存帧的提前失败；可取消，失败恢复有独立预算。设置、自由/人机/本地对局、做题、摆谱及对局中重新标定共用五步流程。
- 严重过亮/过暗使用新鲜连续帧证据，弹窗和离线语音提示移开遮挡、持续不合适时换光线合适的位置。曝光控制尚在等待或普通超时不会冒充环境光故障。
- 本地真实参考帧和几何准备完成后，发布正确的 locked/synced 状态，解除首手确认禁用；准备失败提供独立重试。保留完整识别后处理，点击确认才开启窗口，处理后关闭，未确认棋子不入谱。

## 发布边界

| 目标 | 已验证版本与范围 | 保留项 |
| --- | --- | --- |
| home-ubuntu | `754c24b2e` 增量；image `sha256:6b2f56447483571906193a28331c2a97fec5aac1b7b68b03ca48048bdb8c5ec1` | 实际 env、volumes、启动参数；GPU/DB/cron/admin 等其它容器 ID 不变 |
| ucloud-v100 | home 通过后更新；image `sha256:b2255192576649bf71edb921a993ee6a2d6a0d33ea2e44b5fba72d5558af64cd` | 同上 |
| RK3562 | 8 个源码/音频增量文件和 760 个静态文件哈希核验；实际更换 162 个文件，写入 2,175,439 字节 | 服务参数、硬件配置、模型；参考帧检查仍为 on，仅重启围棋服务 |

两云保留后端基线 `0b086a7c19a403d5e3a01e86e58e7c42d6a224cf`，覆盖当前需要的增量；校验 43 个运行时文件和 11 个 HTTP 资源。RK 也为现役基线上的差量，不声称所有板端源码统一为 develop。前端从 `60a8b67c` 构建，核实其 UI 源码与最终产品提交无差异；full 与 strict SmartBox 2D 均通过构建及资源边界检查。

RK 候选与回滚备份位于 `/mnt/data/smartbox-deployments/rk-exposure-754c24b2e/`。源码采用同目录临时文件加 replace，避免历史 hardlink；资源先写、index 最后写，旧 hash 资源保留。切换前唯一 renderer 在 launcher、视觉 unbound、8081 无在用连接。配置指纹前后相同；发布后根分区剩余 690,843,648 字节，未删除历史文件。

## 验证结果

- 聚焦 Python 六文件 **278 passed**；UI 十二文件 **204 passed**，短文案调整后对应两文件 **92 passed**。TypeScript、相关源码 eslint 与两种构建通过；保留既有 passlib 警告和 GamePage hooks 警告，不扩全 GPU 回归。
- 两云 health 均 ok、本地引擎 reachable；Galaxy 和 kiosk 实际浏览器页面正常渲染，无 pageerror。仅 web 容器切换，空闲检查通过。
- RK 唯一 renderer、1024×600：真实显示曝光收敛为第 **2/5** 步，取消按钮可达；随后真实 LED 标定 **13/13 ready**，13 个 inlier，RMS **0.991 px**、最大残差 **1.520 px**。实际 V4L2 `exposure_auto=1`、`exposure_absolute=166`，摄像头/LED/模型全部就绪。预览 layout 在锁暂不可用期间返回 503；未将它当作完成或光照异常。
- 新建实体本地测试局 `da796ddead784464a725e3df08df2f69`：空盘真实 bind 后自动 `pose_locked=true / sync_state=synced`，确认键可点击，**未使用临时 pose override**。点击首手确认实际运行识别，HTTP 200、`accepted=false / reason=no_stone`，仍黑方、第 0 手、空棋谱。实机未由 agent 摆放物理棋子；真实石子提交链由 BIND→worker→API 回归覆盖，实际摆子留给用户检查。
- 屏幕测试局 `7923ceb7a6cb4fff919bb37834e2b1d2`：依次选择 D4、Q16、K10，确认前第 0 手、stones=[]、音效次数 0，画面仅最后预选标记；确认后只提交 K10，HTTP 200、accepted=true、第 1 手、白方。`stone5.wav` 实际 playing/ended，次数 **1**。同尺寸截图显示双方亮度和确认状态正确，坐标/手数/停一手可见。
- 两个测试局均使用“退出不保存”删除，仅删除本轮创建的会话；恢复实体盘偏好、回到 `/kiosk/play`，视觉 unbound，临时音频观测钩子已移除。临时预览 Fixture 已删除。

### 保存数据核验

报告 **22** 更新后 HTTP 200、status=completed；个人棋谱 `53b850c3fc72443ebb420bd0f2a382ac` HTTP 200，结果 **B+49.3**，**101 手**，SGF 长度 5407。更新前后 SGF SHA256 均为 `ef246709dc5fbb69a96616fb052a2719948e7c0ac6c9f5e2e7bf3c85cabeadb5`。退出测试局后报告仍 completed。未删除或覆盖保存的棋谱和报告。

部署 JSON、真实标定记录、音效回执和实机截图保存在 ignored `output/rk-exposure-release/`。代码审核见 [EXPOSURE-FINAL-CODE-REVIEW.md](EXPOSURE-FINAL-CODE-REVIEW.md)，曝光调查见 [LED-ROOT-CAUSE.md](LED-ROOT-CAUSE.md)，首手诊断见 [FIRST-MOVE-DIAGNOSIS.md](FIRST-MOVE-DIAGNOSIS.md)。本记录之后的提交仅补文档，不重新发布产品或扩大测试。
