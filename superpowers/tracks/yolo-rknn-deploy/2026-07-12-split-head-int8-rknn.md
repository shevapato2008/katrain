# go4_s YOLO → RK3562 RKNN 部署：拆头 INT8 量产方案

**日期:** 2026-07-12
**板:** RK3562 SBC(Debian 11 aarch64,~1 TOPS INT8 NPU),`ssh rk3562-direct`,root
**运行时:** librknnrt 2.3.2 / rknn-toolkit2 2.3.2 / RKNPU driver v0.9.8
**模型:** `go4_s_best.pt`(YOLOv11s,4 类 `black/white/led_red/led_green`,blur 增强;与 `go4_s_ab_blur_s0.pt` 字节相同)

---

## 结论(TL;DR)

**拆头 INT8 是量产模型——又快又准。** 首次真机 NPU 验证,留出集(`go4_eval_24138` / `kifu_24138`,26 帧,从未参与训练),center-match tol 25px:

| 模型 | vs-GT F1 | vs-FP32 一致 | 纯 NPU 中位延迟 | FPS |
|---|---|---|---|---|
| 朴素 INT8(单拼接输出) | **0.000**(类别分全归 0) | 0 | 206 ms | 4.9 |
| FP16 | 0.997 | 100% | 343 ms | 2.9 |
| **拆头 INT8** | **0.998** | **0.997(0 extra)** | **191 ms** | **5.2** |

- 拆头 INT8 逐类:black 1.000 / white 0.997 / led_red 0.980;精度**反超** FP32(白子误检 8 vs FP32 的 14)。
- 比 FP16 **快 1.8×**。既解决正确性,又拿回 INT8 的速度。
- 端到端(含 letterbox 预处理 + 主机端解码)245 ms / 4.1 FPS。围棋落子间隔长,余量充足。
- 一个 `led_green` 误检(frame_056,把亮着的 LED 判成绿而非红)在 **FP16/FP32/INT8 里都存在,同一帧** —— 训练特性,非量化产物。

---

## 朴素 INT8 为什么坏(根因)

标准 ultralytics 导出的 YOLOv8/v11 推理输出是**单个拼接张量** `(1, 4+nc, 8400)`:

```
[ cx, cy, w, h,  cls0, cls1, cls2, cls3 ]   # 每个 anchor 一行(转置后)
  └──── 0–640 像素 ────┘  └─── 0–1 概率 ───┘
```

RKNN 逐张量(per-tensor)INT8 量化对**整个输出张量**用同一个标度(scale)。框坐标量程 0–640,类别分量程 0–1,混在一起:

- scale ≈ max(|value|)/127 ≈ 638/127 ≈ **~5 / 步**
- 所有 ≤1 的类别分 → round(cls / 5) = **恰好 0**
- 每个 anchor 的 4 个类别分全 0 → argmax 后 confidence=0 → **每帧 0 检测**

框坐标正常(它们量程大,量化没被抹掉)。转换日志里 `model.23.cv3`(分类头)的 outlier 警告同源。

> 关键教训:**INT8 崩溃只在真机 NPU 暴露**。此前所有 eval 都在 Mac MPS/FP32 上跑,从未在目标 NPU 上验证过 INT8。上板首测才发现。

---

## 修复:拆头(split-head)导出 + 主机端解码

把检测头拆成**每尺度、框/类别独立的原始 conv 张量**,在 DFL 解码 / anchor 相加 / sigmoid / concat **之前**就输出:

```
box_s8  (1, 4*reg_max, 80, 80)   cls_s8  (1, nc, 80, 80)
box_s16 (1, 4*reg_max, 40, 40)   cls_s16 (1, nc, 40, 40)
box_s32 (1, 4*reg_max, 20, 20)   cls_s32 (1, nc, 20, 20)
```

每个张量量程单一(框 logits 一组,类别 logits 一组),RKNN 逐张量 INT8 各自定标度,类别分不再被框坐标的大量程"淹没"。

所有解码逻辑(DFL softmax → ltrb 距离 → anchor+stride → xyxy → sigmoid → NMS)**移到主机后处理**。这些是 element-wise / 小算子,CPU 上开销可忽略。

### 导出侧(`export_onnx_split.py`)

patch `Detect.forward`,只吐 6 个原始 conv 输出:

```python
def forward_split(self, x):
    outs = []
    for i in range(self.nl):
        outs.append(self.cv2[i](x[i]))   # (1, 4*reg_max, H, W) 框-DFL logits
        outs.append(self.cv3[i](x[i]))   # (1, nc, H, W) 类别 logits
    return tuple(outs)
```

meta 里带上解码所需参数:`format="onnx_split"`, `nc`, `reg_max`, `nl`, `strides`, `output_names`, `decode="host_dfl_anchor_sigmoid_nms"`。

### 主机解码(`split_decode.decode_split_heads`)

```
reg (A,4,reg_max) --softmax(bins)--> dist(A,4) ltrb(格点单位)
x1=(anchor_x - dist_l)*stride  y1=(anchor_y - dist_t)*stride
x2=(anchor_x + dist_r)*stride  y2=(anchor_y + dist_b)*stride
score = sigmoid(cls_logits) --argmax--> class_id, conf
--conf 过滤--> agnostic cv2.dnn.NMSBoxes --> letterbox 逆映射回原图坐标
```

**对 RKNN 输出重排序鲁棒**:按 (H,W) + 通道数识别每个张量(框通道=4*reg_max,类别通道=nc),不依赖输出顺序。anchor 用 `meshgrid(indexing="ij")` + 0.5 偏移,row-major(y*W+x),与 ultralytics 对齐。

### 先在 Mac 上 de-risk,再上板

上板之前,先用 **onnxruntime 跑拆头 ONNX + 同一份主机解码**,与 FP32 ultralytics `.pt` 逐检测对齐(2523/2523,0 extra,F1=0.997)。解码数学确认无误后再上板,所以板上一次通过。这条"先 Mac 后板"的验证顺序是本方案零返工的关键。

---

## 生产集成(接进 katrain 后端)

| 文件 | 改动 |
|---|---|
| `katrain/vision/inference/split_decode.py` | **新增** 共享解码 `decode_split_heads(...) -> list[Detection]`,onnx/rknn 两后端共用(避免重复) |
| `katrain/vision/inference/rknn_backend.py` | meta 判定 split → 把全部 6 个输出张量交给共享解码(而非 `outputs[0]`) |
| `katrain/vision/inference/onnx_backend.py` | 同上,使拆头路径在开发机 onnxruntime 上可单测(与 Mac 验证同路径) |
| `katrain/vision/tools/export_onnx_split.py` | **新增** 拆头 ONNX 导出工具(源自已验证的 scratchpad 脚本,类别取自 `vision.classes` 单一真源) |
| `katrain/vision/tools/export_rknn.py` | 源 meta 为 `onnx_split` 时,透传 `nc/reg_max/strides/decode/output_names` 生成 `rknn_split` sidecar(否则部署的 .rknn meta 是错的) |
| `tests/test_vision/test_split_decode.py` | **新增** 合成张量确定性单测(无需板/NPU):已知 DFL 分布 + 类别 logit → 断言解码出的框/类别;含输出乱序鲁棒性 |

后端通过 meta 的 `format` 自动切换:`onnx_split` / `rknn_split` 走拆头解码,`onnx` / `rknn`(旧单拼接)走原路径 —— **向后兼容**,老模型不受影响。

---

## 复现命令

```bash
# 环境:conda py311_katago(ultralytics 8.4.34);仓库 .venv 没有 ultralytics
# 仓库:~/Repositories/katrain-yolo-train(branch feature/yolo-train)

# 1) 拆头 ONNX 导出(默认 imgsz 640)
python -m katrain.vision.tools.export_onnx_split \
    --pt go4_s_best.pt --imgsz 640 --out rknn_build_split/go4_s_split.onnx

# 2) ONNX → 拆头 INT8 RKNN(Docker linux/amd64 + rknn-toolkit2 2.3.2)
#    复用已建好的 katrain-rknn-toolkit2:latest 镜像 docker run,绕过每次 rebuild
#    校准 dataset.txt 路径按其所在目录解析 → 用 /work/... 容器绝对路径
docker run --rm --platform linux/amd64 -v "$PWD:/work" katrain-rknn-toolkit2 \
    --onnx rknn_build_split/go4_s_split.onnx --target rk3562 \
    --quantize --dataset rknn_build/calibration.txt --output-dir rknn_build_split

# 3) 上板测试(板上隔离 .venv:numpy<2 + opencv-python-headless + rknnlite 2.3.2)
#    rknnlite wheel 从 github airockchip/rknn-toolkit2 取,版本须 == librknnrt(2.3.2)
scp rknn_build_split/go4_s_split_rk3562.rknn rk3562-direct:~/rknn-test/go4_s_split.rknn
ssh rk3562-direct 'cd ~/rknn-test && .venv/bin/python board_split_infer.py \
    --model go4_s_split.rknn --images testset-images --out dets_split.json \
    --conf 0.25 --iou 0.5 --timing-iters 100 --warmup 10'

# 4) 精度评估(GT 标签在 labels/val/ 子目录!别漏)
python eval_compare.py --gt data/go4_eval_24138/labels/val \
    --rknn dets_split.json --ref ref_dets.json --tol 25
```

---

## 部署路径

provisioning 期望 `/opt/smartbox/share/katrain-vision/go4_s.rknn`。**上线用拆头 INT8**;因为拆头模型的输出接口(6 张量)与旧单拼接不同,`.rknn` 必须配**拆头 meta**(`format=rknn_split`),后端才会走拆头解码。

## 转换踩坑清单

- `convert_rknn.sh` 每次强制 rebuild;torch CPU 下载易 SSL-EOF → 直接 `docker run` 复用已建镜像。
- 校准 `dataset.txt` 图片路径按**该文件所在目录**解析,非容器 CWD → 用 `/work/...` 绝对路径。
- 本仓库版 `export_rknn.py` 无 `--out-name`(vendor/katrain 版有);默认名 `{stem}_{target}` 再改名。
- 板测试 rknnlite wheel 不在 PyPI:从 github raw 取,版本须 == librknnrt。
- **eval GT 标签在 `labels/val/` 子目录**,漏了会得到"全 FP、0 TP、FN=0"(标签根本没加载,不是模型坏)。

## 相关

- 记忆:`project_go4s_rknn_rk3562`
- provisioning 轨道:`superpowers/tracks/vision-led-provisioning-2026-07-12`(smartbox-software)
- 未收尾:LED 矩阵控制(ESP32 LED 板此前未在 USB 枚举,待确认物理连接)
