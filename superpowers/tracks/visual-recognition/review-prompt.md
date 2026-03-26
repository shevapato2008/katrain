# 围棋棋盘视觉识别开发计划 — 审核请求

## 审核目标

请审核以下开发计划的合理性、完整性和潜在风险。重点关注：
1. 技术方案选型是否合理
2. 任务拆分和实施顺序是否有遗漏或依赖错误
3. 代码架构和模块划分是否清晰
4. 从 Fe-Fool 五子棋项目移植的代码是否适用于围棋场景
5. 有没有更好的替代方案或你认为需要注意的坑

---

## 一、需求背景

### 项目目标

制作一个**围棋下棋机器人**，需要通过摄像头实时识别棋盘上的黑白棋子位置，输出 19×19 的棋盘状态矩阵，供后端 AI 引擎（KataGo）决策下一步。

### 参考项目

[Fe-Fool](https://github.com/)（`/Users/fan/Repositories/Fe-Fool/`）是一个五子棋/象棋机器人开源项目，包含：
- **FocusFinder**：基于 OpenCV 的棋盘定位 + 透视变换（Canny 边缘检测 → 找最大轮廓 → 4 角点 → 透视矫正）
- **YOLOv5 棋子检测**：使用嵌入式 YOLOv5 仓库识别棋子
- **坐标映射**：像素坐标 → 物理坐标(mm) → 棋盘格位置的线性映射
- **合成数据生成**：从少量棋子抠图 + 空棋盘背景自动合成大量训练数据

### 围棋 vs 五子棋的关键差异

| 维度 | 五子棋 (Fe-Fool) | 围棋 (本项目) |
|------|-----------------|--------------|
| 棋盘格数 | 13×13 | **19×19** |
| 最大棋子数 | ~100 | **~361** |
| 棋子类别 | 1 类 (`heizi`) | **2 类 (`black`, `white`)** |
| 棋子尺寸 | 较大 | **较小（直径 ~22mm，线间距 ~24mm）** |
| 棋盘材质 | 深色棋盘 vs 浅色桌面 | **木棋盘 vs 木桌面（低对比度）** |
| AI 引擎 | 内置 minimax | **外部 KataGo (GTP 协议)** |
| YOLO 版本 | YOLOv5 (嵌入仓库) | **YOLO11 (ultralytics pip 包)** |

---

## 二、技术方案

### 总体流程

```
摄像头采集 (BGR)
    → BoardFinder.find_focus()         # 棋盘定位 + 透视变换 (纯 OpenCV，无需训练)
    → MotionFilter.is_stable()         # 帧间差异检测，手移动时跳过
    → StoneDetector.detect()           # YOLO11 推理 (需要微调训练)
    → BoardStateExtractor              # 像素 → 物理(mm) → 19×19 格位
    → MoveDetector                     # 连续 3 帧一致才确认落子
    → 输出: 19×19 矩阵 (0=空, 1=黑, 2=白)
```

### 技术选型

| 组件 | 技术 | 需要训练？ | 理由 |
|------|------|-----------|------|
| 棋盘定位 | OpenCV Canny + 透视变换 | 否 | 从 Fe-Fool 直接移植，增加 CLAHE 处理木质棋盘低对比度 |
| 棋子识别 | YOLO11 (ultralytics) | **是** | 从 YOLOv5 升级，API 更简洁，不需要单独 clone 仓库 |
| 坐标映射 | 线性比例换算 | 否 | 公式简单直接，从 Fe-Fool 移植 |
| 落子检测 | 帧间集合差异 | 否 | Fe-Fool 验证过的方案 |
| 运动滤波 | cv2.absdiff 帧差法 | 否 | 避免手部遮挡时误检 |

### 训练数据策略

Fe-Fool 的现有训练数据（880 张五子棋/象棋棋子抠图 + 48 张棋盘背景）**不能用于围棋**，需要重新采集：

1. 拍摄围棋棋子抠图（黑子、白子各若干张）
2. 拍摄空围棋棋盘背景（不同光照）
3. 可复用 Fe-Fool 的合成数据生成管道代码自动合成训练集
4. 或直接拍摄 200-300 张实际棋局照片手动标注

---

## 三、模块设计

### 代码结构

```
katrain/vision/
├── __init__.py
├── config.py           # BoardConfig 数据类（围棋物理尺寸参数）
├── board_finder.py     # 棋盘定位 (FocusFinder 移植 + CLAHE 增强)
├── stone_detector.py   # YOLO11 推理封装
├── coordinates.py      # 像素 ↔ 物理坐标 ↔ 棋盘格位 映射
├── board_state.py      # 检测结果 → 19×19 矩阵
├── motion_filter.py    # 帧间运动检测
├── move_detector.py    # 多帧一致性落子检测
├── pipeline.py         # 全流程整合
├── gtp_bridge.py       # GTP/SGF 坐标转换（对接 KataGo）
└── tools/
    ├── collect_data.py    # 训练数据采集脚本
    ├── train_model.py     # YOLO11 训练脚本
    ├── data_template.yaml # 数据集配置模板
    └── live_demo.py       # 实时摄像头演示
```

### 从 Fe-Fool 移植的代码

| 本项目模块 | Fe-Fool 源文件 | 移植内容 | 修改点 |
|-----------|---------------|---------|--------|
| `board_finder.py` | `code/robot/image_find_focus.py` | `FocusFinder` 全部逻辑 | 增加 CLAHE 预处理、可配置阈值 |
| `coordinates.py` | `code/robot/tools.py:104` | `coordinate_mapping()` | 参数化为 `BoardConfig` |
| `coordinates.py` | `code/robot/robot_master.py:330-357` | `coordinate_to_pos()` / `pos_to_coordinate()` | 从 13×13 改为 19×19 |
| `motion_filter.py` | `code/robot/window_detection.py` | `cv2.absdiff` + 阈值 120 | 独立为模块 |
| `move_detector.py` | `code/robot/robot_master.py:341-352` | 集合差异 + 3帧一致 | 独立为模块 |

---

## 四、实施计划（14 个任务）

每个任务遵循 TDD：写失败测试 → 实现 → 验证通过 → 提交。

| # | 任务 | 核心交付物 | 测试数 |
|---|------|-----------|--------|
| 1 | 项目脚手架 + 配置 | `BoardConfig` (围棋物理尺寸) | 4 |
| 2 | 坐标映射 | `pixel_to_physical()`, `physical_to_grid()`, `grid_to_physical()` + 往返一致性验证 | 9 |
| 3 | 棋盘定位 | `BoardFinder` (合成图像测试) | 5 |
| 4 | YOLO 封装 | `StoneDetector` + `Detection` 数据类 | 3 |
| 5 | 棋盘状态 | `BoardStateExtractor.detections_to_board()` | 6 |
| 6 | 运动滤波 | `MotionFilter.is_stable()` | 5 |
| 7 | 数据采集工具 | `collect_data.py` (摄像头交互) | — |
| 8 | 训练管道 | `train_model.py` + `data_template.yaml` | — |
| 9 | 检测管道 | `DetectionPipeline.process_frame()` (mock 测试) | 4 |
| 10 | 实时演示 | `live_demo.py` (可视化) | — |
| 11 | 落子检测 | `MoveDetector.detect_new_move()` (3帧一致) | 4 |
| 12 | GTP/SGF 桥接 | `grid_to_gtp()`, `grid_to_sgf()`, `gtp_to_grid()` | 10 |
| 13 | 依赖管理 | `pyproject.toml` 添加 vision 可选依赖组 | — |
| 14 | 全量测试 | 回归测试 + 代码格式化 | all |

**总计：约 50 个单元测试**

---

## 五、关键设计细节

### BoardConfig 物理参数

```python
@dataclass
class BoardConfig:
    grid_size: int = 19
    board_width_mm: float = 424.2   # 棋盘线区域宽度 (18 间距)
    board_length_mm: float = 454.5  # 棋盘线区域长度 (18 间距)
    border_width_mm: float = 15.0   # 边框到第一条线的距离（宽度方向）
    border_length_mm: float = 15.0  # 边框到第一条线的距离（长度方向）
```

### 坐标映射公式

```
像素 → 物理: x_mm = x_pixel × total_width / img_w
物理 → 格位: pos_x = round((x_mm - border_w) / board_width × 18)
格位 → 物理: x_mm = border_w + pos_x × board_width / 18  (反向，用于机械臂)
```

### YOLO11 vs YOLOv5 升级

```python
# 旧 (Fe-Fool): 需要 clone yolov5 仓库
from yolov5.detect_self import YoloDetecter
detecter = YoloDetecter(weights='best.pt')
res_img, yolo_list = detecter.detect(image)

# 新 (本项目): pip install ultralytics 即可
from ultralytics import YOLO
model = YOLO('best.pt')
results = model(image)
```

### GTP 坐标映射

```
格位 (0,0) → GTP "A1"  (注意跳过字母 I)
格位 (9,9) → GTP "K10" (天元)
格位 (3,3) → SGF "dd"  (星位)
```

---

## 六、潜在风险和关注点

请特别审核以下可能的问题：

1. **FocusFinder 在木质棋盘上的鲁棒性**：木棋盘 + 木桌面对比度低，Canny 边缘检测可能找不到轮廓。CLAHE 增强是否足够？是否需要考虑 ArUco 标记等替代方案？

2. **19×19 密集棋子检测精度**：终盘可能有 300+ 颗棋子密集排列，YOLO11 nano 模型是否能区分相邻棋子？是否需要更大模型（yolo11s/yolo11m）或更高分辨率（imgsz=960）？

3. **坐标映射精度**：线性映射假设透视变换完美矫正了图像，实际镜头畸变和透视残差是否会导致边角位置映射错误？

4. **实时性**：YOLO11 推理 + 板检测 + 坐标映射全流程能否在 CPU 上保持 10+ FPS？树莓派/RK3588 等嵌入式设备呢？

5. **落子检测可靠性**：3帧一致性方案在棋子被短暂遮挡或光照突变时是否会误判？

6. **训练数据量**：对于围棋场景（2 类、小目标、密集分布），200-300 张标注图片是否足够？YOLO11 nano 微调需要多少数据才能达到 mAP50 > 0.9？

7. **合成数据质量**：Fe-Fool 的合成管道（棋子抠图贴到棋盘上）生成的数据与真实场景差异多大？是否需要域适应或更复杂的增强策略？

---

## 七、验证方案

1. **单元测试**：`uv run pytest tests/test_vision/ -v`
2. **回归测试**：`CI=true uv run pytest tests -v`
3. **数据采集烟测**：`python -m katrain.vision.tools.collect_data --camera 0`
4. **实时演示（训练后）**：`python -m katrain.vision.tools.live_demo --model best.pt`
5. **代码格式化**：`uv run black -l 120 katrain/vision tests/test_vision`

---

**详细的逐任务代码和测试步骤见：`superpowers/tracks/visual-recognition/plan.md`**

请对以上计划提出审核意见和改进建议。
