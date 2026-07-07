# 评审需求：P11 棋盘位移在线检测 + 基准灯自动校正（`sbc-baipu-led-guide`）

> 日期：2026-06-26。交给外部评审者（**Codex / Gemini 各自独立评审**）。你们在本仓库内以**只读**方式运行，可直接读文件。
> 评审对象：`superpowers/tracks/sbc-baipu-led-guide/plan.md` 的 **`## P11` 节**（约 **L1865–L2024**），标题「P11. 棋盘位移在线检测 + 基准灯自动校正 + 实时采集中间图（2026-06-26）」。
> 这是一份**新增的、尚未实现**的子计划（状态：计划中）。它引用的设计文档 `2026-06-26-drift-fiducial-recalibration-design.md` **还没写**——所以请直接以 plan.md 的 P11 节为准。
> 区别于本目录下旧的 `review-request.md`（那是评审整份 v2 计划的，已完成）。

---

## 0. 你的任务（一句话）

**独立、对抗式地评审 P11 这份子计划**：找出**正确性 bug、CV/几何上的错误、不可行点、遗漏、以及更优方案**。
**默认去"破坏"它，而不是夸它。** 每条结论都请**对照本仓真实代码核实**，不要只信计划的散文描述。
鼓励挑战既定决策——若你认为方向错了或有更简做法，直说并给理由+证据。

---

## 1. 背景：P11 要解决什么问题（实测驱动）

- **KaTrain** 围棋 AI 教学软件。「**摆谱(baipu)**」采集流程：棋盘下方 361 颗 LED（19×19）逐手点亮"下一手"引导人工摆子，上方 USB 相机**每手带灯拍照**，照片 + SGF + 几何 → 离线自动标注器产 4 类 YOLO 标签（`black/white/led_red/led_green`）训练棋子识别。
- **几何是冻结的**：首帧把 `geometry_lock`（含单应矩阵 `M_0`）固化进 `geometry.npz`，全程复用。
- **触发 P11 的实测故障（2026-06-26，复盘 `kifu_24171`，212 帧）**：摆谱过程中**操作者碰移了棋盘** → 自 `frame_031` 起 warped 网格整体偏移。现有的离线漂移修复（`baipu_autolabel.py` 的 `estimate_global_shift`：对 LED + 孤立棋子锚点取 `中位(检测中心 − 网格点)`，再做**全局平移**并夹在 `±0.6 cell`）在拥挤盘面**失效**：LED 锚点命中率仅 **37%**，`residual>10px` 占 **56%**，中后盘标注框偏约半格~一格，**不可训练**。
- **根因**：单一**全局平移**修不了「碰后 = 平移 + 旋转」；且密集盘上 Hough/棋子锚点噪声大。
- **P11 的方案（一句话）**：采集时**每手**用盘面上**已知的空交叉点**点亮 LED 作为基准点(fiducial)，对该帧**重新解算完整单应矩阵 `M_f`**（平移+旋转+缩放，绝对、不累积），在线检测并自动校正（**不强制清盘、不阻断**），把逐帧几何写进 manifest；离线标注器直接消费 `M_f` 产对齐标注。训练帧保持干净（fiducial 只出现在隔离的标定帧）。

---

## 2. 必读材料

| # | 路径 | 作用 |
|---|---|---|
| 1 | `superpowers/tracks/sbc-baipu-led-guide/plan.md` 的 **P11 节（L1865–L2024）** | **评审主对象**：背景 / 架构 / 范围硬约束 / Task1–6 / 验收 |
| 2 | `plan.md` §4.1（L213-221）、§4.2（L223-248）、§4.4（L253-255） | P11 扩展的**现有采集时序 + manifest schema + 交付契约**（P11 必须向后兼容） |
| 3 | `plan.md` P5 Task4（L392-427）、附录 A（L1137-1148） | 复用的 `GeometryDriftMonitor`；LED (row,col)→链索引 LUT 公式 |

**关键代码（P11 复用/修改，请逐一抽查并据此核实计划声明）**：

- `katrain/vision/geometry_lock.py`
  - `GeometryLock` 字段（L31-45）：`points (19,19,2)`、`xs/ys (19,)`、`M/Minv (3,3)`、`out_size`、`baseline`；npz 持久化 8 字段（`NPZ_FIELDS`，L27）。
  - **请核实 `points` 与 `xs/ys` 各自的坐标空间**（见 §5 攻击面 1）。
- `katrain/vision/geometry_calibrate.py:126-135` — `grid_points_from_corners`：注释自述返回「intersection pixel coords **in the original image**」，经 `Minv`（warp→camera）。
- `katrain/vision/led_geometry_calibrator.py`
  - `detect_led_centroid(dark, lit, *, channel)`（L64-98）：**帧差法**，需要一张 dark 帧和一张 lit 帧。
  - `fit_geometry_from_anchors(...)`（L101-154）：默认 `min_inliers=9`、`max_rms_cells=0.12`、`max_residual_cells=0.25`。
  - `LedGeometryCalibrator.calibrate`（L185-219）：P5 那套**要求空盘**的 13 点标定。
- `katrain/vision/geometry_drift.py:38-62` — `GeometryDriftMonitor.update`：用 `cv2.phaseCorrelate` + `response>=0.05` 阈。
- `katrain/vision/tools/baipu_autolabel.py`
  - `estimate_global_shift`（L165-189，现有的全局平移漂移修复）；`process_game`（L269-345，对**每帧都用同一冻结 `cap.M`** warp）；`frame_boxes`（L217-250，框落在 `grid_point(r,c,xs,ys)=(xs[col],ys[row])` 加 shift）。
- `katrain/web/core/baipu_capture.py:91-217` — `run_capture`：现有每手时序（点下一手灯 → grab → 落盘 → manifest；含幂等/repair/overwrite/首帧固化几何）。
- `katrain/web/core/led_service.py:177/194/209` — `set_points` / `set_rgb_points` / `clear`。

---

## 3. 已知 / 别重复

- 现有 `estimate_global_shift` 全局平移方案的失效数据（37% 命中 / 56% 残差>10px）**已知**，不必复述——P11 就是为修它而生。
- 旧的 `kifu_24171`（212 帧）**没有 fiducial 帧**，无法事后补救，需**重新采集**——这点计划已认。
- 坐标系约定：规范坐标 `row=0` 顶、`col=0` 左（附录 A LUT 已实测锁定）。

---

## 4. 核心设计与关键决策（请逐条审视、可挑战）

源自 brainstorming 三决策 + P11 架构：

1. **绝对 fiducial 重解 取代 帧间比对**：每帧独立解 `M_f`（修全单应），而非帧间差（只修平移且会累积）。`GeometryDriftMonitor` 仅作 DETECT 预检，CORRECT 走 fiducial。
2. **修复时机=在线+离线都要**：在线当场检测/校正/提示；离线标注器消费逐帧 `M_f`。
3. **基准灯=独立标定帧**：fiducial 灯只出现在隔离的 `fiducial/` 标定帧，**训练帧 `frame_NNN.jpg` 保持只含盘面+单个制导灯**，交付契约(§4.4)不变。
4. **每手一次 fiducial 标定帧**（默认 `every-move`）；另给 `drift-gated`（`GeometryDriftMonitor` 预检命中才重解，省一次拍照）与 `off`（回退 P10 行为）。
5. **不强制清盘**：在线只检测+自动校正+提示；与 P5 的 `degraded`（相机/整体失锁→清盘重标定）区分。
6. **fiducial 选点**：从 `board_through_index` 已知**空**交叉点中选 ≥4 个非共线、跨盘分散点；优先 4 角 + 9 星位中为空者；排除制导灯点与四邻有子的点。可用 <4 → `uncorrected`、回退 `M_0`、不阻断。

---

## 5. 重点攻击面（请针对每一条给出结论 + 证据）

> 这些是我们最担心、最希望你独立核实的点。**请给出你自己的判断**，不要默认我们问法里的暗示是对的。

1. **【坐标正确性，最关键】fiducial 的 canonical 目标点取错空间？**
   P11 范围（plan.md **L1886**）写：「fiducial 的 canonical 目标点 = `geometry.npz["points"][row][col]`（直接，无翻转）」。
   但 `grid_points_from_corners`（`geometry_calibrate.py:126-135`）返回的是**原图/相机空间**坐标，而离线 warp 用的是 `(xs[col], ys[row])` 这套 **warped/规范网格**（`baipu_autolabel.frame_boxes` L240、`process_game` L308）。
   - 请判断：要解的 `M_f` 若是「相机 → 规范(warped)」单应，其目标点应当是 `points[row][col]`（相机空间）还是 `(xs[col], ys[row])`（warped 空间）？
   - 若用 `points[row][col]` 当目标解出来的矩阵到底代表什么变换？拿它去 `warpPerspective(训练帧)` 会得到正确的俯视规范图吗？
   - 这条若错，整套 Task1/Task2/Task4 的几何都会错。请给最严谨的结论。

2. **RANSAC 鲁棒性：`≥4` 基准点这个下限够吗？**
   计划（Task1 L1887/L1900）：「≥4 个点」「含 1~2 离群点仍 inlier≥4」。
   - 单应矩阵最少几个对应点可解？要**剔除 1 个外点**最少需几个？剔除 2 个呢？
   - 恰好 4 个点时 RANSAC 还能识别"某个检测是坏的"吗？给一个**真正可用的下限**与建议。
   - 对照 `fit_geometry_from_anchors` 默认 `min_inliers=9`（`led_geometry_calibrator.py:105`）——P11 打算直接 `cv2.findHomography(RANSAC)` 而非复用此函数，那这套残差/inlier 闸门(`max_rms_cells`/`max_residual_cells`)是否也要带上？

3. **帧差检测缺 dark 帧？**
   `detect_led_centroid(dark, lit, channel)`（`led_geometry_calibrator.py:64`）需要**成对的暗/亮帧**。但 P11 Task2 时序（L1924）只描述「点亮 fiducial → grab 标定帧 → 检测」。
   - 这套帧差检测在 P11 序列里有 dark 参考吗？若没有，是要额外多拍一张暗帧（代价？抖动风险？），还是改用单帧（颜色/亮度）检测（如 `baipu_autolabel.detect_led_centroid` L85 那种单帧颜色法）？

4. **中后盘可行性：最需要校正时恰恰最难找空点。**
   fiducial 必须是**空的、非共线、跨盘分散、远离棋子**的交叉点。但漂移随时间累积，中后盘最需要校正——而那时空交叉点最稀缺。
   - 量化这个矛盾：到什么填充度就凑不齐"≥4 分散空点"？4 角 + 9 星位长期为空的概率？
   - 它何时会**静默回退到 `uncorrected`**（即回到 P11 本要消灭的失败态）？这个回退是否被诚实地暴露/告警？

5. **`phaseCorrelate` 看不见旋转，drift-gated 会漏掉 P11 的主因？**
   `GeometryDriftMonitor.update`（`geometry_drift.py:49`）用 `cv2.phaseCorrelate`，只测**平移**。但 P11 的根因是「平移+**旋转**」。
   - `drift-gated` 模式靠它做预检，会不会**漏报纯旋转/绕角旋转**的漂移（平移分量小但旋转大）？
   - 若会，`drift-gated` 是否根本不该作为默认之外的"省拍"路径？对 `every-move` vs `drift-gated` 的取舍有何影响？

6. **SBC 延迟/UX：每手多一次标定帧，"廉价"成立吗？**
   现有每手（`run_capture`）：点灯→settle→grab→写盘。P11 在其前插入：选点→`set_rgb_points`→settle→grab 标定帧→检测→解 `M_f`→`clear`，之后才是制导灯+训练帧，再 warp+3 张叠图。
   - 在 RK3562/3576/3588 上，每手实测**多了几次 LED 往返 + settle 等待 + 抓帧 + 3 次 warp/叠图**？操作者手间隔会明显变长吗？「廉价」这个判断是否站得住？

7. **契约/向后兼容：是"不崩"还是"产出好标签"？**
   P11 给 manifest 每帧加 `geometry_corrected/fiducials/drift/artifacts`（L1947-1953），旧数据无此字段→离线回退 `estimate_global_shift`。
   - 旧 `kifu_24171` 走回退仍是 56% 残差>10px 的坏标签。计划说的"兼容旧数据"是否被诚实区分为"**不崩**"而非"**能用**"？有没有在文档/manifest 里标注旧数据不可训练？

8. **测试计划是否真覆盖关键失败模式？**
   Task1–5 的 RED/GREEN（合成网格、不接相机/i18n）是否真的考了：**旋转恢复**、**外点剔除**、**<4 点回退**、**dark 帧处理**、**artifact 目录隔离不污染训练帧**、**`off` 模式回退 P10**？哪些验收只是 happy-path？

9. **真机 bring-up 还会被什么咬到？**（开放）
   例如：fiducial 灯在空点的反光/串色、曝光锁与 fiducial 亮度、`grab_fresh` 返回内存帧但需显式 `imwrite` 到 `fiducial/`、与 `run_capture` 幂等/repair/overwrite 逻辑的交互、并发与单相机 owner(CameraHub)、阈值 `0.10 cell`(monitor) vs `0.15 cell`(Task3) 不一致……凡你核实过的，都报。

---

## 6. 硬约束（评审时据此判断，不可违反）

- **范围**：只动 katrain 侧；固件已烧好（勿假设要改）；YOLO 训练在 `autoresearch`。
- **训练交付契约不变（§4.4）**：训练样本只有 `frame_NNN.jpg` + `game.sgf` + `geometry.npz` + `manifest.json`；`warped/`、`grid_overlay/`、`warped_boxes/`、`fiducial/` 全是**诊断 artifact，目录隔离，绝不混入训练帧**。
- **规范坐标**：`row=0` 顶、`col=0` 左（附录 A）。
- **离线导出链已是类数无关的**：correctness 取决于 `data.yaml` 与几何，不取决于改导出代码。
- **平台**：采集在 macOS / 部署在 RK35xx；`cv2.VideoCapture`；LED 经串口，主机持 LUT、固件认链索引。

---

## 7. 期望的评审输出格式

```
## 总评 (go / go-with-changes / no-go) + 一句话理由

## Top 3 必改（实现前必须解决）
1. [严重度] 问题 — 证据(plan.md 行号 / 代码 file:line) — 具体修法

## 详细发现（逐条）
- [Critical/Major/Minor] 标题
  - 类型：correctness bug / CV·几何错误 / 不可行 / 遗漏 / 决策异议 / 更优方案
  - 位置：plan.md 行号 和/或 矛盾代码 file:line
  - 计划声称：引用/转述
  - 为何错/会坏：具体，带代码证据
  - 修法：可执行
  - 置信度：high / medium / low

## 对 §5 九个攻击面的逐条结论（尤其 #1 坐标空间，请给最终判断）

## 对 §4 关键决策的判断（同意 / 异议+理由+替代）

## 底线（一段话）：核心架构（绝对逐帧 fiducial 单应）是否成立？实现前 2-3 个 must-fix 是什么？
```

**评审准则**：宁可少而准——只报你**对照计划/代码核实过**的问题；不确定的标「需进一步确认」。优先级以「是否阻断正确实现」为准。不要软化措辞。确实没问题的点，一句带过，把篇幅留给真问题。
