# Go Stone Detection: Architecture Analysis & Execution Guide

## 1. System Overview

The stone detection pipeline is a 5-stage frame processor that takes a raw camera image and outputs confirmed Go moves:

```
Raw Frame → MotionFilter → BoardFinder → StoneDetector (YOLO11) → BoardState → MoveDetector → Move
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| YOLO11n (nano) | Smallest/fastest variant, 足够检测两类目标 (black/white) |
| Inference size 960px | 比默认 640 更大, 提高 19x19 密集网格上的检测精度 |
| `agnostic_nms=True` | 防止同一位置输出两个重叠框 (一黑一白) |
| Motion filter 在 YOLO 之前 | 跳过静止帧的昂贵推理, 节省 GPU/CPU |
| HSV auto-labeling | 省去手动标注, 利用已矫正图的数学网格位置自动生成标签 |
| ArUco-first + Canny fallback | 有标记时稳定可靠, 无标记时仍可降级工作 |

---

## 2. Module Map

```
katrain/vision/
├── stone_detector.py      # YOLO11 推理: image → list[Detection]
├── board_state.py         # Detection → 19x19 grid (0=empty, 1=black, 2=white)
├── board_finder.py        # 透视矫正: ArUco / Canny → warped board image
├── coordinates.py         # pixel ↔ mm ↔ grid 坐标转换
├── motion_filter.py       # 帧间运动检测, 过滤静止帧
├── move_detector.py       # 多帧一致性确认单步落子
├── pipeline.py            # DetectionPipeline — 串联上述 5 个阶段
├── katrain_bridge.py      # vision coords → KaTrain/GTP coords
├── katrain_integration.py # VisionPlayerBridge — 提交 move 给 session
├── config.py              # BoardConfig (物理尺寸mm) + CameraConfig
└── tools/
    ├── collect_data.py       # 实时采集: 摄像头 → warped 图片
    ├── auto_label.py         # HSV 自动标注: warped 图 → YOLO .txt
    ├── download_dataset.py   # 下载 Roboflow 合成数据集
    ├── prepare_dataset.py    # split / merge 数据集
    ├── train_model.py        # ultralytics YOLO11 训练封装
    ├── show_grid.py          # 实时网格叠加 + 检测叠加
    ├── diagnose_image.py     # 单图诊断 (Canny/ArUco/grid/detection)
    ├── live_demo.py          # 完整 pipeline 实时演示
    ├── calibrate_camera.py   # 棋盘格标定 → camera_calibration.npz
    ├── generate_markers.py   # 生成 ArUco 标记打印页
    └── data_template.yaml    # 数据集目录结构模板
```

---

## 3. Training Pipeline — 详细流程

### 3.1 数据来源 (二选一或合并)

**方式 A: 实拍采集 + 自动标注**

```bash
# Step 1: 采集 — 摄像头拍摄, 空格保存 warped 图
python -m katrain.vision.tools.collect_data \
  --output ./real_dataset/images --camera 0

# Step 2: 自动标注 — HSV 阈值分类每个交叉点
python -m katrain.vision.tools.auto_label \
  --images ./real_dataset/images/train \
  --output ./real_dataset/labels/train \
  --verify  # 可选: 生成带 bbox 的验证图

# Step 3: split 训练/验证
python -m katrain.vision.tools.prepare_dataset \
  --images ./real_dataset/images/train \
  --labels ./real_dataset/labels/train \
  --output ./real_dataset --split 0.8 --validate
```

**方式 B: 下载 Roboflow 合成数据集**

```bash
# 需要 ROBOFLOW_API_KEY 环境变量
python -m katrain.vision.tools.download_dataset \
  --output ./synthetic_dataset
# 自动完成: 下载 → class remap (3类→2类) → data.yaml 生成
```

**方式 C: 合并两个数据源**

```bash
python -m katrain.vision.tools.prepare_dataset \
  --merge-base ./synthetic_dataset \
  --merge-extra ./real_dataset \
  --output ./combined_dataset --validate
```

### 3.2 数据集结构

```
dataset/
├── data.yaml              # nc: 2, names: ['black', 'white']
├── images/
│   ├── train/             # ~80% 图片
│   └── val/               # ~20% 图片
└── labels/
    ├── train/             # YOLO format .txt (与 images/train/ 一一对应)
    └── val/
```

**标签格式**: `class_id x_center y_center width height` (均为归一化 0-1)

| class_id | 含义 |
|----------|------|
| 0 | black stone |
| 1 | white stone |

**固定 bbox 尺寸**: `w=22mm/424.2mm ≈ 0.052`, `h=22mm/454.5mm ≈ 0.048` (22mm 棋子在标准棋盘上的比例)

### 3.3 训练

```bash
# 基础训练 (默认 yolo11n, 100 epochs, imgsz=960)
python -m katrain.vision.tools.train_model train \
  --data ./combined_dataset/data.yaml

# 自定义训练 (更大模型, 更多 epochs)
python -m katrain.vision.tools.train_model train \
  --data ./combined_dataset/data.yaml \
  --model yolo11s.pt \
  --epochs 200 \
  --imgsz 960 \
  --batch 16

# 权重输出: runs/detect/go_stones/weights/best.pt
```

**默认超参数**:
- Base model: `yolo11n.pt` (nano, 最快)
- Epochs: 100, Early stopping patience: 20
- Image size: 960, Batch: 16
- Output: `runs/detect/go_stones/weights/best.pt`

### 3.4 验证

```bash
python -m katrain.vision.tools.train_model val \
  --data ./combined_dataset/data.yaml \
  --model runs/detect/go_stones/weights/best.pt
# 输出 mAP50 和 mAP50-95
```

---

## 4. Inference Pipeline — 详细流程

### 4.1 DetectionPipeline (`pipeline.py`)

```python
pipeline = DetectionPipeline(
    model_path="runs/detect/go_stones/weights/best.pt",
    marker_ids=[0, 1, 2, 3],  # ArUco 模式 (可选)
    confidence_threshold=0.5,
)

# 每帧调用
result: FrameResult | None = pipeline.process_frame(raw_frame)
```

**5 个阶段详解**:

| Stage | Module | Input | Output | 耗时占比 |
|-------|--------|-------|--------|----------|
| 1. Motion Filter | `motion_filter.py` | raw frame | stable? (bool) | 极低 |
| 2. Board Finder | `board_finder.py` | raw frame | warped image + M matrix | 中 |
| 3. Stone Detector | `stone_detector.py` | warped image | list[Detection] | **最高** |
| 4. Board State | `board_state.py` | detections | 19x19 ndarray | 极低 |
| 5. Move Detector | `move_detector.py` | board state | confirmed Move | 极低 |

### 4.2 Motion Filter

```python
# 比较当前帧与上一帧灰度差
changed_pixels = count(abs(gray_diff) > 30)
stable = changed_pixels / total_pixels < 0.05  # 5% 阈值
```

拒绝运动帧 → 跳过后续所有昂贵计算。

### 4.3 Board Finder

**ArUco 模式** (推荐):
- 字典: `DICT_4X4_50`, 子像素精炼
- 4 个标记的 **内角** (朝向棋盘中心的角) 作为透视变换源点
- `marker_ids` 顺序: `[TL, TR, BR, BL]`

**Canny 模式** (fallback):
- GaussianBlur → Canny → morphClose → findContours
- 渐进 epsilon: 0.02 → 0.04 → 0.06 (适应真实棋盘的线条干扰)
- 过滤: 4 顶点 + 凸性 + 面积>10% + 宽高比 0.7-1.4

**稳定性过滤**: 角点移动 >50px 时拒绝该帧 (baseline 不因拒绝而漂移)。

### 4.4 Stone Detector (YOLO11)

```python
results = model(warped_image, verbose=False, imgsz=960, agnostic_nms=True)
# → list[Detection(x_center, y_center, class_id, confidence)]
```

只返回 `confidence > threshold` 的检测。

### 4.5 Board State Extraction

**坐标转换链**:
```
Detection pixel (warped img) → physical mm → grid position (0..18)

x_mm = x_pixel * 424.2 / img_w
pos_x = round(x_mm / 424.2 * 18)   # border=0 时简化
```

**冲突解决**: 多个检测映射到同一格时, 置信度最高的赢。

### 4.6 Move Detector

```python
# 比较 new_board vs prev_board
new_stones = [(r, c, color) for r, c where prev==EMPTY and new!=EMPTY]
if len(new_stones) == 1:
    if same_move_for_3_consecutive_frames:
        return confirmed_move
```

- 恰好 1 颗新子 → 计数器 +1
- 新子变化 → 计数器归零
- 连续 3 帧相同 → 确认落子
- 支持 `force_sync()` 应对悔棋/终局

---

## 5. Integration — KaTrain 对接

### 5.1 坐标转换

Vision 坐标系 (图像左上角为原点) → KaTrain/GTP 坐标系 (棋盘左下角为原点):

```python
katrain_row = board_size - 1 - vision_row  # 翻转 Y 轴
# vision (0,0) = A19, vision (0,18) = A1, vision (9,9) = K10
```

### 5.2 VisionPlayerBridge

```python
bridge = VisionPlayerBridge(session)
# 去重: 同一 move 不会重复提交
bridge.submit_move(result.confirmed_move)
# 内部调用 session.katrain("play", move.coords)
```

---

## 6. Auto-Label 算法细节

`auto_label.py` 中 HSV 分类逻辑 (关键参数):

```python
# 默认阈值
BLACK_V_MAX = 80    # V < 80 → 黑子
WHITE_S_MAX = 50    # S < 50 且 V > 160 → 白子
WHITE_V_MIN = 160

# 对每个交叉点 (row, col):
patch_half = int(0.015 * img_w)  # 约 14px (960px 图)
median_v = np.median(patch_hsv[:, :, 2])  # V 通道中位数
median_s = np.median(patch_hsv[:, :, 1])  # S 通道中位数
```

**适用条件**: warped 图光照均匀、棋子与棋盘对比度明确。光照不均匀时需要调整阈值或开启 CLAHE。

---

## 7. Execution Checklist — 从零到推理

### Phase 1: 硬件准备
- [ ] USB 摄像头 (推荐 1080p+)
- [ ] 打印 ArUco 标记: `python -m katrain.vision.tools.generate_markers` → 贴在棋盘四角
- [ ] (可选) 相机标定: `python -m katrain.vision.tools.calibrate_camera`

### Phase 2: 数据收集
- [ ] 采集: `collect_data.py` — 多种光照/角度/棋局, 至少 50-100 张
- [ ] 自动标注: `auto_label.py --verify` — 检查验证图, 调整 HSV 阈值
- [ ] (可选) 下载合成数据: `download_dataset.py`
- [ ] 准备数据集: `prepare_dataset.py --split 0.8 --validate`

### Phase 3: 训练
- [ ] 训练: `train_model.py train --data data.yaml`
- [ ] 验证: `train_model.py val` — 目标 mAP50 > 0.90
- [ ] 如精度不足: 增加实拍数据, 合并合成数据集, 或升级到 `yolo11s.pt`

### Phase 4: 部署测试
- [ ] 单图测试: `diagnose_image.py --image test.jpg --marker-ids 0 1 2 3`
- [ ] 实时网格: `show_grid.py --camera 0 --marker-ids 0 1 2 3`
- [ ] 完整 demo: `live_demo.py --model best.pt --camera 0 --marker-ids 0 1 2 3`

### Phase 5: 集成
- [ ] 创建 `DetectionPipeline` 实例
- [ ] 创建 `VisionPlayerBridge(session)` 绑定 KaTrain session
- [ ] 主循环: `process_frame()` → `submit_move()`

---

## 8. Known Limitations & Improvement Directions

| 问题 | 现状 | 改进方向 |
|------|------|----------|
| HSV 标注光照敏感 | 固定阈值, 强光/暗光不稳 | 自适应阈值 / 基于直方图的动态分类 |
| 仅支持 19x19 | config.grid_size=19 硬编码较多 | 参数化 9x9/13x13 支持 |
| 无棋子计数验证 | 不校验总子数合理性 | 加入 B/W 计数一致性检查 |
| 单相机 | 固定角度 | 多相机融合 / 更强的遮挡处理 |
| 无增量训练 | 每次全量重训 | Fine-tune on new real data |
| bbox 固定大小 | 22mm 棋子假设 | 根据实际棋子/棋盘比例自适应 |
