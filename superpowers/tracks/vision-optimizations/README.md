# vision-optimizations

实体棋盘落子识别的历次优化，都放在这里。原来的 `vision-stone-parallax` 只讲得了视差一件事，
2026-09-23 改名重组为本目录。

**先看这张图：[`recognition-pipeline.html`](recognition-pipeline.html)**（浏览器直接打开，离线可用）。
它画出一帧画面从摄像头到落进棋谱的全过程，以及新棋谱怎样回流给识别端。每个方框都带源码出处（点开 SRC），
上方的五个「导览」可以一段一段地看。图由 archify 生成，源文件是
[`recognition-pipeline.architecture.json`](recognition-pipeline.architecture.json)；改完图请重新生成：

```
cd ~/.codex/skills/archify
node bin/archify.mjs deliver architecture <本目录>/recognition-pipeline.architecture.json \
  <本目录>/recognition-pipeline.html --quality showcase --repo-root <katrain 仓根目录>
```

## 一帧怎么走（文字版）

| 步 | 做什么 | 代码 | 关键数 |
|---|---|---|---|
| 1 | 取帧；画面有手在动就整帧丢弃，平均器清零 | `worker_inprocess.py` `_motion_is_stable` | 1080p |
| 2 | 按几何锁透视校正成俯视图 | `_warp_frame` | 950 + 两边各 53 = 1056² |
| 3 | 取一份**平均前**的灰度图，留给参照帧比对 | `reference_frame.to_gray` | — |
| 4 | 8 帧平均 + CLAHE，只喂给模型 | `temporal.FrameAverager`、`enhance.py` | n=8，clipLimit 3.0 |
| 5 | YOLO（RKNN）检测 + NMS | `inference/rknn_backend.py` | 黑 / 白 / 红灯 / 绿灯；同框 IoU ≥ 0.5 留一个 |
| 5a | 去重复框：同一颗子被框两次（一紧一松） | `stone_detector.dedup_detections` | 中心距 < 较小框边长的一半，留高分 |
| 5b | 去影子（**规划中**）：侧光下「子 + 影子」被再框一次 | `board_state.py`（规划中） | 与邻框互压 ≥ 0.27、且自己落在两个交叉点之间才去掉 |
| 6 | 视差修正后落到交叉点：占用感知分配、粘滞、三档滞回、颜色保持、亮灯格不新增 | `board_state.py`、`parallax.py` | k≈0.990；0.40 / 0.30 / 0.20；变色 15 帧 |
| 7 | 两帧投票：连续两帧一致才改 | `worker_inprocess.py` | — |
| 8 | 参照帧比对（**影子模式**，只记日志） | `_reference_check` | ZNCC ≥ 0.90；否决 90 / 10 帧 |
| 9 | 落子确认：逐格计连续帧；卡住的弱检测弹确认卡 | `move_detector.py` | 峰值 ≥ 0.70 走 3 帧，否则 5 帧；确认卡 12 帧 |
| 10 | 盘面同步：缺子、多子、盘面不一致 | `sync.py` | 缺子先等 7 s |
| 11 | 提交前复核：子还在（L0a）、轮到谁（L0b），然后落进棋谱 | `server.py` `_handle_confirmed_move` | — |
| 12 | 棋谱把新的期望盘面发回 worker；AI 落子处亮指引灯 | `physical_play_orchestrator.py`、`physical_play.py` | — |
| 13 | 指引灯亮度按实测光斑自动调 | `server.py` `_adjust_led_brightness` | 目标 60000，单步 ×0.5–×2 |

逐帧耗时可以在板上 `touch /tmp/katrain-vision-trace` 打开 `vtrace` 日志查看，`rm` 掉即关闭，不用重启。

## 历次优化

| 日期 | 改了什么 | 为什么 | 状态 | 文档 |
|---|---|---|---|---|
| 09-17 | 标定只认绿灯（13 点）；相机曝光与棋盘几何写入 eMMC，重启后恢复 | 重启、断电后识别条件不一致 | 已上线 | `docs/superpowers/plans/2026-09-17-hardware-vision-state.md` |
| 09-17 | 「棋子没放正」「疑似落子」两个恢复弹窗各播一次中文语音 | 只有屏幕提示，下棋时看不到 | 已上线 | `docs/superpowers/plans/2026-09-17-vision-recovery-voice-prompt.md` |
| 09-20 | 提交前复核（L0a 子还在、L0b 轮次），逐格确认计数，可疑格走确认卡，缺子按时钟等待，已落的子不轻易变色 | 幻影落子、真落子迟迟不确认、已落子变色、短暂遮挡被报成盘面不一致 | 已上线 | `docs/superpowers/plans/2026-09-20-vision-recognition-stability.md`、`docs/2026-09-20-kiosk-device-session.md` |
| 09-20 / 21 | 终局即停止视觉比对（09-20）；没人用摄像头时识别、漂移检测、1080p 解码都停下（09-21） | 78% 的「盘面不一致」弹窗出在终局之后；不下棋时 katrain 仍占约 170% CPU，界面按钮都慢 | 已上线 | `docs/2026-09-20-kiosk-device-session.md` |
| 09-21 | 棋子视差修正 | 摄像头斜拍、棋子有厚度，远端棋子会被判到邻近交点 | 已上线 | [`stone-parallax/`](stone-parallax/README.md) |
| 09-22 | 视差参数从几何锁直接推出，不再需要摆子标定 | 没人会去摆 17 颗子标定，所以此前每台盒子上实际都关着 | 已上线；到交叉点的中位距离 0.224 → 0.150 格 | `docs/2026-09-22-kiosk-device-session.md` §2 |
| 09-22 | 新增 0.20 维持档，只留棋谱里已有的子 | 远端白子在静止局面里掉到 0.30 以下，反复弹「盘面缺子」 | 已上线 | 同上 §1 |
| 09-22 | 逐帧计时日志（vtrace） | 定位「识别变慢」：单帧不慢，慢在要攒 3–5 帧；上盘→确认中位 1.08 s | 已上线 | 同上 |
| 09-22 | 指引灯按实测光斑自动调亮度 | 夜里灯光透过白子，白子认不出 | 已上线，还没在整局里验证过 | 同上 §1 第 6 条 |
| 09-23 | 参照帧比对：逐格与「最近一次确认时的画面」比结构，结构没变就不信检测器的改口 | 白天反光、窗边光照不均造成的漏识别和误识别 | **影子模式**，等白天实测数据定阈值 | [`reference-frame/design.md`](reference-frame/design.md)、`docs/superpowers/plans/2026-09-23-vision-reference-frame.md` |
| 09-23 | 长考时每分钟逐格续期参照帧 | 光影随时间漂移，参照变旧后就不起作用 | 影子模式，同上 | [`reference-frame/design.md`](reference-frame/design.md) §4.1 |
| — | 过曝：白子拍成一片死白 | 像素信息本身丢了，参照帧也救不回 | **未做**，只留档；设想在标定时提示挪棋盘 | `docs/known-issue-overexposure.md` |

## 目录

| 路径 | 内容 |
|---|---|
| `recognition-pipeline.html` | 流程图（archify 生成） |
| `recognition-pipeline.architecture.json` | 流程图源文件 |
| `stone-parallax/` | 视差修正：需求、推导、设计、计划、上板交接、参考实现（原 `vision-stone-parallax/`） |
| `reference-frame/` | 参照帧比对的设计（原 `vision-reference-frame/`） |

上板实测记录仍按日期放在 `docs/`（`2026-09-20-kiosk-device-session.md`、`2026-09-22-kiosk-device-session.md`），
实施计划仍在 `docs/superpowers/plans/`，上表已逐条指过去。
