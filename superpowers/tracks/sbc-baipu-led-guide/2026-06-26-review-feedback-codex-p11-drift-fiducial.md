# P11 棋盘位移在线检测 + 基准灯自动校正评审反馈（Codex）

评审对象：`plan.md` 的 P11 节（L1865-L2024）。  
结论基于 P11 计划文本和本仓现有代码核实，不假设尚未写出的设计文档。

## 总评 (no-go) + 一句话理由

**no-go。** “逐帧绝对 fiducial 重解相机到规范棋盘单应”的核心方向成立，但 Claude/P11 当前方案在 canonical 坐标空间、多点基准灯检测时序、RANSAC 接受门限和失败回退上都有阻断级错误，按原文实现会得到错误 `M_f` 或在最需要校正时静默回到坏几何。

## Top 3 必改（实现前必须解决）

1. **[Critical] `geometry.npz["points"][row][col]` 不是 `M_f` 的 canonical 目标点**
   - 证据：P11 L1886 声称 canonical 目标点等于 `points[row][col]`；但 `GeometryLock.M` 是原图到 warp 的矩阵，`points` 是原图/相机空间交叉点（`geometry_lock.py:31-37`, `geometry_lock.py:68-74`, `geometry_calibrate.py:126-135`）；现有 LED 13 点标定用 `[[col * spacing, row * spacing]]` 作为 canonical 目标（`led_geometry_calibrator.py:101-119`）；离线标注也在 warped 空间用 `(xs[col], ys[row])` 放框（`baipu_autolabel.py:64-71`, `baipu_autolabel.py:308`）。
   - 修法：`solve_frame_homography` 的最终输出必须是“当前相机帧 -> 规范 warp 空间”的 `M_f`，目标点应为 `[[xs[col], ys[row]]]` 或等价的 `[[col * spacing, row * spacing]]`。如果坚持用 `points`，那只能先解 `H_cur_to_cam0`，再组合 `M_f = M_0 @ H_cur_to_cam0`，manifest 里存组合后的最终 `M_f`。

2. **[Critical] 当前“复用 LED 光斑检测 + 一张 lit fiducial 帧”的时序不成立**
   - 证据：P11 L1876/L1909 说复用 `LedGeometryCalibrator` 的帧差光斑检测，L1924 只描述 `set_rgb_points(F)` 后抓一张标定帧；但 `detect_led_centroid(dark, lit, channel)` 明确需要 dark/lit 成对帧且只返回一个主连通域中心（`led_geometry_calibrator.py:64-98`）。现有 `_locate_anchor` 是每个 anchor 执行 `clear -> grab dark -> set_rgb_points(单点) -> grab lit -> detect_led_centroid`（`led_geometry_calibrator.py:221-240`），并没有“多点同时点亮后检测 K 个中心”的实现。
   - 修法：二选一。推荐新增 `detect_led_centroids(dark, lit, expected_points, channel)`，先 `clear(strict) -> grab dark`，再 `set_rgb_points(F) -> grab lit`，在 raw delta 图上按 `M_0`/last-good 投影的 ROI 分配多个 blob，并输出每个 fiducial 的 centroid、peak、area、margin、reason。或者顺序闪烁每个 fiducial 复用现有单点检测，但必须接受每手多 K 次 LED 往返和抓帧成本。

3. **[Major] `>=4` 点 + `inlier>=4` 不是可用的鲁棒下限，且失败回退 `M_0` 会重新污染数据**
   - 证据：P11 L1887/L1900 接受 `>=4` 点并要求“含 1~2 离群点仍 inlier>=4”；单应最少 4 个对应点，恰好 4 点时任何一个坏点都无法被识别。现有 `fit_geometry_from_anchors` 默认 `min_inliers=9`，并有 `max_rms_cells=0.12`、`max_residual_cells=0.25` 两道残差门（`led_geometry_calibrator.py:101-154`）。P11 L1887/L1924/L1969 失败时回退 `M_0`，如果棋盘已经被碰移，这会把后续帧直接拉回 P11 要消灭的坏状态。
   - 修法：目标仍按 9-13 个 fiducial 设计，最低接受建议为 `detected>=8` 且 `inliers>=6`，更保守可沿用 `min_inliers=9`；必须保留 RMS/max residual cell 门。失败时优先使用 `last_good_M_f` 并标 `status="stale_uncorrected"`/告警，只有没有 last-good 时才可用 `M_0`。离线导出遇到 drift 后 `uncorrected` 或 stale 过久，应默认隔离/拒绝训练标签，而不是静默产出。

## 详细发现（逐条）

- **[Critical] canonical 坐标空间写反**
  - 类型：CV·几何错误 / correctness bug
  - 位置：`plan.md:1886`; `geometry_lock.py:31-37`, `geometry_lock.py:68-74`; `geometry_calibrate.py:126-135`; `led_geometry_calibrator.py:101-119`; `baipu_autolabel.py:64-71`, `baipu_autolabel.py:308`
  - 计划声称：fiducial canonical 目标点等于 `geometry.npz["points"][row][col]`。
  - 为何错/会坏：`points` 是旧几何下的原图相机坐标；`xs/ys` 才是 warped/规范棋盘坐标。用 `detected_current_camera -> points_old_camera` 解出的矩阵是“当前相机帧到旧相机帧”的 homography，不是当前帧到 950x950 规范棋盘的 `M_f`。直接拿它 `warpPerspective(frame, M_f, (950,950))` 会输出错误坐标系。
  - 修法：目标点改为 `(xs[col], ys[row])`。若需要利用 `points`，必须显式组合 `M_0 @ H_cur_to_cam0`，并测试两条路径等价。
  - 置信度：high

- **[Critical] 多 fiducial 同时点亮检测没有现成可复用函数**
  - 类型：correctness bug / 遗漏
  - 位置：`plan.md:1876`, `plan.md:1909`, `plan.md:1924`; `led_geometry_calibrator.py:64-98`, `led_geometry_calibrator.py:221-240`
  - 计划声称：复用 `LedGeometryCalibrator` 的帧差检测，`set_rgb_points(F)` 后检测 K 中心。
  - 为何错/会坏：现有检测器从整张 delta 图找一个 dominant blob，设计上适配“单点闪烁”。多点同时亮时，它只会返回最亮的一个或因多 blob margin 不足而失败。P11 还没有描述 blob 到 `(row,col)` 的 assignment。
  - 修法：实现多 blob 检测和 assignment，或改为顺序闪烁单点。多 blob 版本应使用 `M_0` 或 `last_good_M_f` 的 raw-space 预测窗口搜索，避免远处反光抢占。
  - 置信度：high

- **[Critical] 帧差检测缺 dark 帧**
  - 类型：correctness bug / 时序遗漏
  - 位置：`plan.md:1924`; `led_geometry_calibrator.py:64-72`, `led_geometry_calibrator.py:225-236`; `capture_service.py:75-77`
  - 计划声称：点亮 fiducial 后 grab 标定帧即可检测。
  - 为何错/会坏：`detect_led_centroid` 的信号是 `lit[channel] - dark[channel]`，没有 dark 帧就不是复用该检测器。当前 `run_capture()` 也没有无灯 QA 帧，P7 后已经改成操作者确认直接点下一手灯（`baipu_capture.py:150-179`）。
  - 修法：采集时序必须写成 `led.clear(strict) -> grab_fresh dark -> set_rgb_points(F, strict) -> grab_fresh lit -> detect -> led.clear(strict) -> set_points(next) -> capture_to training`。若改用单帧颜色法，则不要声称复用帧差检测，并要补 raw-space 单帧检测测试。
  - 置信度：high

- **[Major] RANSAC 下限和质量门太弱**
  - 类型：CV·几何错误 / 不可行
  - 位置：`plan.md:1887`, `plan.md:1900`, `plan.md:1909`; `led_geometry_calibrator.py:101-154`; `tests/test_led_geometry_calibrator.py:37-65`
  - 计划声称：`>=4` fiducial，含 1-2 离群点仍 `inlier>=4`。
  - 为何错/会坏：4 点是单应最小解，不是鲁棒解。恰好 4 点时，RANSAC 没有冗余识别坏点；5 点含 1 外点时理论上可找到 4 个 inlier，但仍无多余 inlier 评估稳定性；6 点含 2 外点同理仍只有 4 个 inlier。现有 13 点标定已经用 `min_inliers=9` 和 residual gate，P11 放宽到 4 会让偶然错误 blob 也产出貌似合法的 `M_f`。
  - 修法：目标点数保持 9-13，最低接受不低于 `detected>=8`、`inliers>=6`，并继承 `max_rms_cells`/`max_residual_cells`。测试必须包含“4 点 + 1 外点应失败”“6 点 + 2 外点仅 4 inlier 应失败”。
  - 置信度：high

- **[Major] late-game `M_0` 回退会把已经校正过的对局重新打坏**
  - 类型：决策异议 / correctness bug
  - 位置：`plan.md:1887`, `plan.md:1924`, `plan.md:1969`, `plan.md:2021`
  - 计划声称：可用 fiducial `<4` 或失败时回退 `M_0`，不阻断。
  - 为何错/会坏：如果 frame_031 后棋盘已经移动，`M_0` 正是错误几何。后续中后盘一旦 fiducial 不足，标签会突然回到旧错位，且 P11 计划还允许离线旧回退继续产标签。
  - 修法：维护 `last_good_M_f`。失败状态分为 `ok/corrected/stale_uncorrected/frozen_uncorrected`；只有 `frozen_uncorrected` 且无 drift 证据时可继续训练。离线标注默认跳过或隔离 drift 后未校正帧。
  - 置信度：high

- **[Major] 中后盘空点约束会在最需要校正时失败**
  - 类型：不可行 / 决策异议
  - 位置：`plan.md:1887`, `plan.md:2019`
  - 计划声称：从空交叉点选 `>=4` 个非共线、跨盘分散点，排除四邻有子的点，失败不阻断。
  - 为何错/会坏：排除“自身 + 四邻”后，随机填充率为 `p` 时，一个内点可用概率约 `(1-p)^5`。全盘期望可用点数约 `361*(1-p)^5`：`p=0.50` 时约 11 个，`p=0.55` 时约 6.7 个，`p=0.60` 时约 3.7 个。若还要求跨盘分散，真实可用数更低。4 角 + 9 星位的期望可用数在 `p=0.50` 只有 `13*(0.5^5)=0.41`，不能作为长期主力。
  - 修法：选点器要以 9-13 个为目标，同时支持分层降级：优先安全空点，其次允许邻子附近但提高检测/残差门，最后用 last-good。UI 和 manifest 必须诚实显示“当前帧未重新校正，仅沿用 last-good”。
  - 置信度：medium

- **[Major] `drift-gated` 用 phase correlation 会漏掉旋转**
  - 类型：CV·几何错误 / 决策异议
  - 位置：`plan.md:1889`, `plan.md:1969`; `geometry_drift.py:38-62`; `tests/test_geometry_drift.py:22-44`
  - 计划声称：`drift-gated` 用 `GeometryDriftMonitor` 预检命中才重解。
  - 为何错/会坏：`GeometryDriftMonitor.update()` 只调用 `cv2.phaseCorrelate` 得到 `(dx,dy)` 和响应，阈值判断也是 `shift_cells`。P11 的根因包含旋转；纯旋转或绕角小平移大旋转可能 response 低或平移量低，从而不触发重解。
  - 修法：`every-move` 保持默认且作为唯一质量模式。`drift-gated` 只能作为实验/省电模式，并至少加“每 N 手强制 fiducial”和旋转感知检测；否则不应宣称可修 P11 主因。
  - 置信度：high

- **[Major] SBC 成本被低估**
  - 类型：遗漏 / 可行性风险
  - 位置：`plan.md:1891`, `plan.md:1924-1926`; `baipu_capture.py:154-179`; `capture_service.py:94-111`
  - 计划声称：每手多一次拍照 + 一次 warp/叠图，廉价。
  - 为何错/会坏：若按帧差正确实现，每手至少新增 `clear+SHOW ACK`、dark grab、`set_rgb_points+SHOW ACK`、lit grab、detect/solve、`clear+SHOW ACK`，之后才是原本制导灯 `set_points` 和训练帧 `capture_to`。再加 `fiducial`、`warped`、`grid_overlay`、`warped_boxes` 多个 `imwrite`。这不是“一次拍照 + 一次 warp/叠图”。
  - 修法：Task6 前移一个 RK35xx micro-benchmark：记录 LED roundtrip、settle、grab、solve、3-4 次 imwrite、总阻塞时间；根据结果决定 `every-move` 是否仍默认，或是否异步写 artifact。
  - 置信度：medium

- **[Major] artifact 与 overwrite/repair 清理逻辑未覆盖**
  - 类型：遗漏 / 数据一致性
  - 位置：`plan.md:1931`, `plan.md:1940`, `plan.md:1952`; `baipu_capture.py:78-88`, `baipu_capture.py:128-148`, `baipu_capture.py:202-206`
  - 计划声称：artifact 目录隔离并按帧落盘，`off` 回退 P10。
  - 为何错/会坏：现有 `_unlink_manifest_frame` 只删除 `frame["file"]`，overwrite 时也只裁掉 manifest tail 和训练帧。P11 若新增 `fiducial/warped/grid_overlay/warped_boxes`，覆盖/repair 后旧 artifact 会残留，可能让人工复核看到过期图。
  - 修法：manifest entry 的 artifact 路径也要纳入安全 resolved-path 删除；overwrite 裁尾时删除训练帧和 artifact；repair 同一 ordinal 前先清理旧 artifact。
  - 置信度：high

- **[Major] 旧数据“兼容”没有区分不崩和可训练**
  - 类型：遗漏 / 数据质量风险
  - 位置：`plan.md:1978`, `plan.md:2021`; `baipu_autolabel.py:269-345`
  - 计划声称：无 `geometry_corrected` 字段时回退旧 `estimate_global_shift`，兼容旧 `kifu_24171`。
  - 为何错/会坏：评审请求给出的旧数据已知 56% 帧 `residual>10px`，回退只是不崩，不是能产出好标签。继续默认导出会让坏数据混入训练。
  - 修法：`baipu_autolabel` 对 legacy/frozen fallback 输出 `label_quality` 或 summary warning；对已知 drift 失败数据默认跳过，提供显式 `--allow-legacy-drift` 才导出。
  - 置信度：high

- **[Minor] drift 阈值和状态语义不一致**
  - 类型：遗漏
  - 位置：`plan.md:1969`; `geometry_drift.py:20-25`; `geometry_calibration_service.py:219-222`
  - 计划声称：Task3 阈值默认 `0.15 cell`。
  - 为何会坏：现有 `GeometryDriftMonitor` 默认 `0.10 cell`，服务初始化没有覆盖阈值。P11 如果新增 0.15，需要明确配置来源和 API/status 使用哪个阈值。
  - 修法：统一配置项，例如 `baipu_drift_threshold_cells`，同时记录到 manifest/status。
  - 置信度：high

## 对 §5 九个攻击面的逐条结论

1. **坐标正确性：P11 当前写法是错的。**  
   要解“相机 -> 规范 warped”的 `M_f`，目标点必须是 `(xs[col], ys[row])`。`points[row][col]` 是原图相机空间。用 `points` 解出的只是当前相机到旧相机的 `H_cur_to_cam0`；只有再组合 `M_0 @ H_cur_to_cam0` 才可能变成可用于 `warpPerspective` 的最终 `M_f`。

2. **RANSAC 鲁棒性：`>=4` 不够。**  
   单应最少 4 点。剔除 1 个外点至少要 5 个总点才有 4 个 inlier，但 4 inlier 没有冗余评估；剔除 2 个外点至少 6 点总点，但仍只有最小解。真正可用下限建议 `detected>=8`、`inliers>=6`，目标沿用现有 13 点思路和 `min_inliers=9` 更稳。残差门必须保留。

3. **帧差检测缺 dark 帧：是实质遗漏。**  
   现有 `detect_led_centroid` 不能只用 lit 帧。P11 要么多拍 dark 帧，要么另写单帧检测。若多点同时亮，还必须新增多 blob assignment。

4. **中后盘可行性：会在 50%-60% 填充附近变脆。**  
   四邻排除后，随机估算 `p=0.55` 只剩约 6.7 个可用点，`p=0.60` 约 3.7 个，且未计“跨盘分散”要求。4 角 + 9 星位不能指望长期为空。回退必须用 last-good 并明确告警，不能静默 `M_0`。

5. **`phaseCorrelate` 看不见旋转：drift-gated 会漏主因。**  
   当前 monitor 只输出平移量，测试也只覆盖亮度变化和大平移。`drift-gated` 不应作为质量路径；最多是带周期强制校正的省拍优化。

6. **SBC 延迟：廉价结论未被证明且被低估。**  
   正确帧差方案每手至少多 dark+lit 两次 grab、多个 LED strict ACK、额外清灯和多个 artifact 写盘。必须在 RK35xx 上实测阻塞时间。

7. **契约/向后兼容：目前只是“不崩”，不是“产出好标签”。**  
   旧无 fiducial 数据回退旧平移估计，已知对 `kifu_24171` 不可训练。需要在文档、manifest 或 autolabel summary 中标出 legacy/fallback 标签质量，默认不把 bad drift 旧数据进入训练。

8. **测试计划覆盖不足。**  
   P11 提到旋转恢复、外点、`<4` 回退、artifact 隔离和 `off`，但缺少关键负例：坐标空间误用、4 点含外点应失败、dark/lit 时序、多点 blob assignment、last-good 回退、pure rotation drift-gated 漏报、overwrite 清理 artifact、legacy/frozen 数据默认隔离。

9. **真机 bring-up 额外风险：多点亮灯 assignment、曝光和串色会先咬人。**  
   低亮度绿在锁曝光下可能低信噪比；多个 LED 同时亮会产生反光和串色，现有单 blob detector 不适用；`grab_fresh` 返回内存帧，fiducial 帧需要显式 `imwrite`；artifact 与幂等/repair/overwrite 必须同步；相机 owner 和 LED strict ACK 的阻塞时间要量化。

## 对 §4 关键决策的判断

1. **绝对 fiducial 重解取代帧间比对：同意，但目标矩阵必须定义为相机到 warped。**  
   这是正确方向。修正 canonical 坐标和残差门后，能解决平移+旋转问题。

2. **在线 + 离线都修：同意。**  
   在线负责现场提示和 artifact，离线必须消费最终 `M_f`。但离线还要有质量门，不能对 `uncorrected` 默认产训练标签。

3. **fiducial 独立标定帧，训练帧保持干净：同意。**  
   但标定帧若采用帧差，必须包含 dark/lit 成对采集；artifact 目录要参与清理和 overwrite。

4. **每手一次 fiducial 默认，drift-gated/off 可选：部分同意。**  
   `every-move` 应保留默认。`drift-gated` 在现有 `phaseCorrelate` 下会漏旋转，只能作为带周期强制校正的实验模式；`off` 是兼容模式，不是质量模式。

5. **不强制清盘：同意，但不能静默坏标签。**  
   采集可不阻断；训练导出不能不加区分地接受 drift 后 `uncorrected` 帧。UI 也应把 stale/frozen fallback 说清楚。

6. **fiducial 选点策略：需要重写接受标准。**  
   “4 角 + 9 星位优先”可作为排序，但不能作为可用性保证。目标应是尽量 9-13 点，接受阈值不低于 6 inliers，并按空间分布打分；不足时沿用 last-good 而不是 `M_0`。

## 建议补充的 RED 测试

1. **坐标空间测试**：构造旧 `M_0`、当前相机帧发生旋转+平移；用 `(xs,ys)` 解出的 `M_f` 应把 raw fiducial 投到规范网格，误用 `points` 的路径应失败，组合 `M_0 @ H_cur_to_cam0` 应通过。
2. **多点检测测试**：一张 dark、一张 lit，5-9 个 fiducial 同时亮，含一个反光 blob，检测应按 expected ROI 返回每个 `(row,col)` 的中心并拒绝 ambiguous。
3. **RANSAC 负例**：4 点中 1 个坏点必须失败；6 点中 2 个坏点且只剩 4 inlier 必须失败；9 点中 2 个坏点应成功且 residual 过门。
4. **late-game fallback 测试**：当前帧 fiducial 不足时沿用 `last_good_M_f`，manifest/status 标 stale；无 last-good 才 frozen fallback。
5. **drift-gated 旋转漏报测试**：纯旋转或绕中心小平移大旋转不得被当作“无需重解”的质量保证。
6. **artifact 幂等测试**：overwrite/repair 删除训练帧和所有 artifact；`off` 模式不生成 artifact 且旧 manifest 不崩。
7. **离线导出质量测试**：manifest 中 `geometry_corrected.source="fiducial"` 时不用 `estimate_global_shift`；`source="frozen"` 且 drift 后 `uncorrected` 默认跳过或警告。

## 底线

核心架构“每帧用 fiducial 解绝对 homography，并让离线标注消费逐帧 `M_f`”是成立的，值得做。但实现前必须先修三件事：第一，把 `M_f` 的目标空间改成 warped canonical `(xs[col], ys[row])` 或显式组合 `M_0 @ H_cur_to_cam0`；第二，补齐 dark/lit 多 fiducial 检测和 assignment，不能直接复用单 blob 函数；第三，把 RANSAC 和失败回退改成有冗余、有残差门、优先 last-good、离线有质量隔离的方案。未修这些就开工，P11 很可能把错误矩阵写进 manifest，并把不可训练标签伪装成已校正数据。
