# Review Feedback: Go Board Visual Recognition Plan

## 总体评价

这份开发计划（`superpowers/tracks/visual-recognition/plan.md`）非常出色。它不仅结构清晰、模块划分合理，而且采用了测试驱动开发（TDD）的最佳实践。将 Fe-Fool 的五子棋逻辑迁移到围棋（19x19）的思路是可行的，特别是采用了 YOLO11 替换旧版检测器，这是一个非常现代化的技术选型。

代码片段质量很高，几乎可以直接运行。对 `MoveDetector` 巧妙地利用"忽略移除，只关注新增"来处理提子（Capture）场景的逻辑表示赞赏。

尽管如此，针对围棋 19x19 的特殊性，仍有几个关键的技术风险点需要补充处理，特别是**镜头畸变**和**检测分辨率**问题。

---

## 关键改进建议 (Must Fix / High Priority)

### 1. 增加镜头畸变矫正 (Camera Calibration)
**风险**：围棋棋盘（19路）比五子棋（13/15路）更密集。普通的广角或网络摄像头通常存在**桶形畸变（Barrel Distortion）**，导致棋盘边缘的直线在图像中变弯。
- `cv2.getPerspectiveTransform` 只能处理透视变形（梯形变矩形），**无法处理径向畸变**。
- 如果不进行矫正，棋盘边缘或角落的棋子坐标映射会产生偏差，落入错误的网格坐标。
- **建议**：
    - 在 `BoardFinder` 或 `pipeline` 中增加 `cv2.undistort` 步骤。
    - 增加一个工具脚本 `tools/calibrate_camera.py`，使用棋盘格（Checkerboard）打印纸拍摄几张照片来计算相机内参（Camera Matrix）和畸变系数（Distortion Coefficients）。
    - 在 `BoardConfig` 或新的 `CameraConfig` 中存储这些参数。

### 2. 提高输入分辨率 (Image Resolution)
**风险**：YOLO11n 默认 `imgsz=640`。
- 围棋棋盘充满画面时，每条线间距约为 `640 / 19 ≈ 33` 像素。
- 棋子直径略小于线间距。虽然 30px 对 YOLO 来说通常足够，但如果摄像头视场（FOV）较大，棋盘只占画面一部分（例如 70%），则棋子可能只有 20px 左右，容易导致误检或漏检，特别是密集的棋形。
- **建议**：
    - 在 `train_model.py` 和 `pipeline.py` 中，建议默认将 `imgsz` 提升至 **960** 或 **1280**（取决于树莓派/PC 的推理速度承受力）。
    - 确保数据采集时保存原始分辨率图片，不要过早 resize。

---

## 优化建议 (Should Fix / Medium Priority)

### 3. MoveDetector 的提子与死子处理
**分析**：目前的 `MoveDetector` 逻辑是：`if board[r][c] != prev[r][c] and board[r][c] != EMPTY`。
- 这意味着它**只检测“新增”的棋子**，而忽略“消失”的棋子。
- **优点**：自动兼容了“提子”场景（下一手棋导致对方N颗子消失，代码只返回那一手新棋，完美）。
- **盲点**：无法检测“拿走死子”（Game End）或“悔棋”（拿走最后一手）。
    - 如果用户悔棋（拿走刚下的子），`diff_positions` 为空（没有新增），`detect_new_move` 返回 `None`，`prev_board` **不会更新**。
    - 此时 `prev_board` 仍保留着被拿走的那颗子。这在逻辑上是“安全”的（因为视觉系统认为那颗子还在），但如果 UI 需要实时反馈“棋子被拿走了”，这个模块无法提供信号。
- **建议**：目前作为“落子检测器”是合格的。如果未来需要支持“悔棋”或“形势判断后的清理”，可能需要暴露一个 `force_update()` 方法或让 `prev_board` 在稳定N帧后强制同步（即使没有新落子）。

### 4. 棋盘定位的鲁棒性 (BoardFinder)
**风险**：Fe-Fool 的逻辑依赖 Canny 边缘检测。
- 木纹棋盘上的黑色边框线可能因为反光或磨损而不连续。
- 棋盘周边的杂物（棋罐、线缆）可能形成更强的边缘轮廓。
- **建议**：
    - 在 `find_focus` 失败时，保留上一帧的变换矩阵（假设相机和棋盘相对静止）。
    - 仅在 `is_stable` 且 `find_focus` 成功时更新变换矩阵，避免画面闪烁。

---

## 代码层面微调

1.  **Task 7 (Data Collection)**: 建议在保存文件名中包含 `timestamp` 而不仅仅是 `count`，防止覆盖或多机采集时重名。
2.  **Task 4 (StoneDetector)**: YOLO推理时建议开启 `agnostic_nms=True`（类别无关的 NMS）。
    - **原因**：围棋中黑白子紧贴的情况很多。默认 NMS 可能允许黑子和白子的框高度重叠（因为类别不同）。开启 `agnostic_nms` 可以防止在一个位置同时检测出黑子和白子（虽然这种情况较少，但在模糊时可能发生）。

## 总结

计划非常扎实，可以直接开始执行。建议在 **Task 9 (Pipeline)** 之前或之中插入**相机畸变矫正**的步骤，这对于 19路棋盘的精确识别至关重要。
