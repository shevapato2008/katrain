## 总评: go-with-changes

P11 的核心思路——每手通过 fiducial 绝对重解单应矩阵——方向正确，能从根本上解决“平移+旋转”复合漂移问题。但当前计划在最关键的几何坐标系、RANSAC 鲁棒性和帧差法前置条件上存在严重的设计缺陷，若不修正，实现将完全失败。Task 定义也遗漏了关键的暗帧采集和对 `fit_geometry_from_anchors` 的复用。必须先修正这些核心错误，并补全测试用例，才能进入实现阶段。

---

## Top 3 必改（实现前必须解决）

1.  **[Critical] 坐标系错误**：计划（L1886）为 `findHomography` 指定的目标点 `geometry.npz["points"][row][col]` 位于**相机空间**，而非期望的 **warped 规范空间**。这会导致解出的 `M_f` 是一个无意义的 `camera → camera` 变换，无法正确地将训练帧 `warpPerspective` 到俯视规范图。
    -   **证据**:
        -   `katrain/vision/geometry_calibrate.py:126-135` (`grid_points_from_corners`) 注释和实现都表明其返回 **original image (相机)** 坐标。
        -   `katrain/vision/tools/baipu_autolabel.py:240,308` (`frame_boxes`, `process_game`) 使用 `(xs[col], ys[row])` 作为 **warped 空间**的网格点坐标。
    -   **修法**: 必须将 `findHomography` 的目标点（`dst_pts`）改为 warped 空间的 canonical 坐标，即 `(xs[col], ys[row])`。`source_pts` 则是相机空间中检测到的 fiducial 质心。

2.  **[Critical] 帧差法缺少暗帧 (dark frame)**：P11 Task2 时序（L1924）仅描述了“点亮 fiducial → grab”，但这与复用的 `detect_led_centroid` 函数（`led_geometry_calibrator.py:64`）需要 `dark` 和 `lit` 两张成对帧的前提相矛盾。没有暗帧，帧差法无法工作。
    -   **证据**: `detect_led_centroid(dark: np.ndarray, lit: np.ndarray, ...)` 的函数签名和实现（`delta = lit - dark`）。
    -   **修法**: Task2 采集序列必须修改。在点亮 fiducial 灯之前，**额外采集一张 `dark` 帧**。这意味着每手标定会增加一次抓帧和 settle 延时，其成本必须被重新评估。或者，放弃帧差法，改为 `baipu_autolabel.py:85` 中的单帧颜色检测法，但这需要评估其鲁棒性。

3.  **[Major] RANSAC 鲁棒性不足**: 计划（L1887/L1900）要求的 `≥4` 个基准点是 `findHomography` 的理论下限，**完全没有冗余来剔除外点 (outlier)**。只要有一个点检测出错，几何解算就会失败或产生巨大误差。
    -   **证据**: 单应矩阵需要 4 对点。RANSAC 要从 N 个点中随机选 4 个来拟合模型，并用其余 N-4 个点来验证。如果 N=4，则没有点可供验证，无法识别外点。
    -   `led_geometry_calibrator.py:105` 中复用的 `fit_geometry_from_anchors` 函数已经包含了更鲁棒的 `min_inliers=9` 默认值。
    -   **修法**: 1) 将 fiducial 点的最小数量**提高到 5 个或更多**（例如，至少 5 个才能容忍 1 个外点）。2) Task 2 应**复用 `fit_geometry_from_anchors` 函数**，而不是直接调用 `cv2.findHomography`，这样可以继承其成熟的 `min_inliers`, `max_rms_cells`, `max_residual_cells` 等鲁棒性检查。

---

## 详细发现（逐条）

-   **[Critical] 坐标系错误导致几何变换完全失败**
    -   类型：correctness bug / CV·几何错误
    -   位置：plan.md L1886, L1904
    -   计划声称：`fiducial` 的 `canonical` 目标点 = `geometry.npz["points"][row][col]`。
    -   为何错/会坏：如 Top-1 所述，`points` 数组是相机空间坐标。用相机空间坐标作为 `findHomography` 的目标点，试图求解一个 `camera → warped` 的变换 `M_f`，在数学上是错误的。解出的矩阵 `M_f` 会是将相机平面上的点错误地映射到相机平面上另一个位置，而不是期望的俯视规范平面。使用这样的 `M_f` 对训练帧进行 `warpPerspective` 将产生严重扭曲或无意义的图像。
    -   修法：Task 2 和 Task 4 中，构建 `findHomography` 的 `dst_pts` 参数时，对于每个 `(row, col)` 的 fiducial，其对应的目标点必须是 `(cap.xs[col], cap.ys[row])`。
    -   置信度：high

-   **[Major] `drift-gated` 模式会漏报旋转漂移，使其几乎无用**
    -   类型：决策异议 / CV·几何错误
    -   位置：plan.md L1875, P11 架构决策 #4
    -   计划声称：`drift-gated` 模式使用 `GeometryDriftMonitor` 做预检，可以“省一次拍照”。
    -   为何错/会坏：`GeometryDriftMonitor.update`（`geometry_drift.py:49`）明确使用 `cv2.phaseCorrelate`，该方法**只能检测平移**，对旋转不敏感。而 P11 旨在解决的根本问题就是“平移+**旋转**”。因此，当棋盘发生纯旋转或绕角旋转时（平移分量很小），`drift-gated` 模式的预检会**大概率漏报**，导致不执行 fiducial 重校正，从而让 P11 的核心修正机制失效。
    -   修法：1) 废弃 `drift-gated` 模式，或明确标注其为实验性的、不可靠的。2) 将 `every-move` 作为唯一推荐的在线校正模式。
    -   置信度：high

-   **[Major] 中后盘 fiducial 选点可行性低，易静默失败**
    -   类型：不可行 / 遗漏
    -   位置：plan.md L1900-L1903 (Task 1 选点逻辑)
    -   计划声称：从空的交叉点中选 ≥4 个非共线、跨盘分散的点。
    -   为何错/会坏：中后盘棋局，尤其是在边角定式完成后，棋盘上很难找到足够数量的、满足“跨盘分散”和“四邻无子”条件的空点。4 角和星位很快会被占据。这会导致 `select_fiducial_points` 频繁返回少于所需数量（例如 < 5）的点，从而使 `fit_geometry_from_anchors` 失败并**静默回退**到使用陈旧的 `M_0`，这恰恰是 P11 试图解决的失败模式。计划没有明确如何将这种“无法校正”的状态显式警告给用户。
    -   修法：1) Task 1 必须定义当找不到足够 fiducial 点时的显式失败/警告逻辑，例如在 manifest 中明确标记该帧为 `correction_failed: not_enough_points`。2) 应考虑更激进的选点策略，例如允许使用邻近有子的点，但相应地需要更鲁棒的 RANSAC 参数（更多冗余点）。
    -   置信度：high

-   **[Minor] manifest 字段与实现不一致**
    -   类型：遗漏
    -   位置：plan.md L1947-1953 (Task 3 Manifest Schema)
    -   计划声称：新增 `geometry_corrected`, `fiducials`, `drift`, `artifacts` 字段。
    -   为何错/会坏：`drift` 字段计划存储 `GeometryDriftMonitor` 的输出。但在 `every-move` 模式下，`GeometryDriftMonitor` 可能根本不会运行。此外，`geometry_corrected` 作为一个布尔标志，信息量不足。
    -   修法：建议将 manifest schema 修改得更具信息量，例如：
        ```json
        "geometry_correction": {
          "status": "applied" | "failed" | "skipped" | "off",
          "reason": "not_enough_inliers" | "not_enough_points" | null,
          "source": "fiducial_recalibration",
          "M_f_path": "fiducial/frame_031_M.npy", //
          "rms_residual_cells": 0.08,
          "inlier_count": 7
        }
        ```
        这样既能清晰地记录校正是否成功，也能保留诊断信息，并且与 P10 的数据结构（无此 key）清晰地区分开。
    -   置信度：medium

---

## 对 §5 九个攻击面的逐条结论

1.  **【坐标正确性】结论：计划完全错误。** 目标点必须是 warped 空间的 `(xs[col], ys[row])`，而不是相机空间的 `points[row][col]`。使用后者解出的变换矩阵是错误的。

2.  **【RANSAC 鲁棒性】结论：`≥4` 点的下限不足。** 无法抵御外点。至少需要 5 个点才能剔除 1 个外点。应复用 `fit_geometry_from_anchors` 并要求至少 5-9 个 inliers。

3.  **【帧差检测缺 dark 帧】结论：计划遗漏了暗帧采集。** `detect_led_centroid` 实现需要成对的暗/亮帧。P11 时序必须增加一次抓帧，这会增加延迟。

4.  **【中后盘可行性】结论：风险高，易静默失败。** 中后盘很难找到足够的分散空点。计划必须定义失败时的显式告警/记录机制，而不是静默回退到旧的、有问题的几何。

5.  **【`phaseCorrelate` 看不见旋转】结论：`drift-gated` 模式存在设计缺陷。** 它会漏掉旋转为主的漂移，使其不可靠。应弃用或重新设计预检方法（例如，用 ORB 特征匹配）。

6.  **【SBC 延迟/UX】结论：「廉价」判断过于乐观。** 增加的序列（`clear`→`settle`→`grab dark`→`set fiducial`→`settle`→`grab lit`→`process`）保守估计会增加数百毫秒的延迟。在 `every-move` 模式下，这可能对操作流畅性造成可感知的负面影响，需要真机实测验证。

7.  **【契约/向后兼容】结论：计划对"兼容"的描述不诚实。** 它只是“不崩溃”，但无法修复旧数据的坏标签。Manifest 或相关文档应明确标注，未使用 P11 fiducial 校正的数据在存在漂移时，其标注质量是不可信的。

8.  **【测试计划】结论：覆盖不足。** 计划中的 RED/GREEN 测试多为 happy-path。验收标准必须显式增加**失败模式的测试用例**：如外点剔除、<4 点回退、旋转恢复验证、`off` 模式正确性验证等。

9.  **【真机 bring-up】结论：还有风险。**
    -   **并发/锁**：`run_capture` 持有 `_game_lock`，但 P11 的新校正逻辑在 `run_capture` **之前**发生。如果 `CameraHub` 或 `LedService` 不是线程安全的单例，可能会有并发问题。
    -   **文件 I/O**：新产生的 `fiducial/` 目录、`M_f` 矩阵文件等需要在 `run_capture` 的幂等/repair 逻辑中被正确处理，防止产生孤立或不一致的文件。
    -   **亮度/曝光**：fiducial 点亮时，相机的自动曝光可能会调整，影响 `detect_led_centroid` 的稳定阈值。最好在采集全程锁定曝光。

---

## 对 §4 关键决策的判断

1.  **绝对 fiducial 重解**：**同意**。这是正确的方向。
2.  **修复时机=在线+离线**：**同意**。
3.  **基准灯=独立标定帧**：**同意**。保持训练帧干净是必须的。
4.  **每手一次 fiducial**：**同意 `every-move`**，但**异议 `drift-gated`**。如前述，`drift-gated` 的预检逻辑有缺陷。
5.  **不强制清盘**：**同意**。自动校正对用户体验更好。
6.  **fiducial 选点**：**异议其鲁棒性**。对空点的要求过于严格，在中后盘易失败，且 `≥4` 的下限太低。需要更强的鲁棒性设计。

---

## 底线

P11 的核心架构（每帧独立重解单应矩阵）是成立且正确的。然而，当前计划在实现细节上存在致命的几何错误，如果不加以修正，项目将无法交付预期的功能。

**实现前的 3 个 Must-Fix**:

1.  **修正坐标系**：`findHomography` 的目标点必须是 warped 空间的 `(xs[col], ys[row])`。
2.  **补上暗帧采集**：在 fiducial 标定序列中，必须在 `lit` 帧之前采集 `dark` 帧。
3.  **提升 RANSAC 鲁棒性**：提高 fiducial 点的最小数量（建议至少5个），并复用 `fit_geometry_from_anchors` 函数来处理外点和残差检查。
