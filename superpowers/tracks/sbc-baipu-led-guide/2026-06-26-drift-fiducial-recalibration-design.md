# P11 设计落地 + 执行记录：棋盘位移在线检测 + 基准灯自动校正

> 配套 `plan.md` 的 P11 节。本文记录**实际落地的设计**与**执行结果**（2026-06-27）。
> 计划经 Codex / Gemini 两轮对抗评审重写（见 `2026-06-26-review-feedback-{codex,gemini}-p11-drift-fiducial.md`）。

## 1. 问题与方向

冻结几何 + 摆谱中碰移棋盘 → warped 网格自 `frame_031` 整体偏移；旧的「全局平移」离线修复在拥挤盘失效（LED 命中 37%、`residual>10px` 占 56%）。根因：单一平移修不了「平移+旋转」复合漂移。

方向（两家评审一致认可）：每手用**已知空交叉点**点亮 LED 作 fiducial，**重解该帧相机→规范棋盘的绝对单应 `M_f`**（修全平移+旋转+缩放），在线校正、离线消费。

## 2. 关键设计决策（as-built）

1. **`M_f` 目标空间 = warped 规范网格 `(xs[col], ys[row])`，不是相机空间 `points[row][col]`。** 通过**复用 `led_geometry_calibrator.fit_geometry_from_anchors`**（其 dst 已是 `col*spacing,row*spacing`）一举修对坐标 + 继承 `min_inliers`/`max_rms_cells`/`max_residual_cells` 残差门。`points[row][col]`（相机空间）**改作 ROI 搜索中心**预测 fiducial 在 raw 帧中的位置。
   - *为何*：评审 #1（两家 Critical）。`grid_points_from_corners` 返回 original-image（相机）坐标；用它作 homography 目标解出的是「当前相机→旧相机」变换，`warpPerspective` 出来不是俯视规范图。
2. **暗/亮帧差 + ROI 多 blob 分配**：新增 `detect_led_centroids(dark, lit, expected, channel, search_px)`——一手只需 **1 暗 + 1 亮**两帧（不是每点一对），在每个预测 ROI 内独立取主光斑加权中心。规避现有单 blob `detect_led_centroid` 多点同亮时只返回最亮一个 / `ambiguous_blobs` 失败。
   - *为何*：评审 #2/#3（两家 Critical）。
3. **鲁棒下限**：目标 9~13 fiducial；`corrected` 需**检测成功 ≥8 点且 `solve_frame_homography(min_inliers=6)` 过残差门**。`≥4` 作废（4 点是单应最小解，无冗余剔外点）。
4. **失败回退不回 `M_0`**：`last_good_M_f` carry-forward；状态 `corrected`（本帧解成功）/`stale`（不足/失败→沿用 last-good）/`frozen`（尚无 last-good→冻结 `M_0`）。
   - *为何*：评审 #5。碰移后的 `M_0` 本身是错几何，静默回退会二次污染。
5. **`drift-gated` 移出本期**：`GeometryDriftMonitor` 用 `phaseCorrelate` 只测平移，看不见 P11 主因（旋转）。本期只实现 `every-move`（默认）+ `off`。
6. **离线质量门**：`corrected` 用 `M_f` 直接 warp + 零位移放框；`stale` 用 last-good 并标 `label_quality="stale"`；本局若出现 `drift.over_threshold`，则 `frozen`/legacy 帧默认**跳过**，`--allow-legacy-drift` 才导出。
7. **artifact 隔离 + 覆盖清理**：实时存 `warped/`、`grid_overlay/`、`fiducial/`（训练帧 `frame_NNN.jpg` 保持只含制导灯）；`_unlink_manifest_frame` 连同 artifact 删除，overwrite/repair 不留孤儿。`warped_boxes` 归离线 `--verify-dir`。
8. **manifest 富 `geometry_correction`**：`{status, source, reason, M(3x3), inlier_count, rms_residual_cells, drift{dx,dy,deg,scale,median_cells,over_threshold}}` + `fiducials[]` + `artifacts{}`。统一阈值 `baipu_drift_threshold_cells`（默认 0.15）。

**未采纳**：codex 的 `M_0 @ H_cur_to_cam0` 组合路径（直接 warped 目标更简）；gemini 的逐帧 `M_f.npy` 旁路（内联 manifest 更简）+ ORB 预检（drift-gated 已搁置）；codex `detected≥8` 作为 inlier 下限（采 inliers≥6 平衡中后盘稀缺）。

## 3. 落地文件

| 文件 | 改动 |
|---|---|
| `katrain/vision/fiducial_recalibrate.py` | **新增**：`select_fiducials`/`predict_camera_positions`/`detect_led_centroids`/`solve_frame_homography`/`drift_from_homography` + `CentroidResult`/`Drift`。 |
| `katrain/web/core/baipu_capture.py` | `run_capture(fiducial_mode, drift_threshold_cells)` + `_run_fiducial_calibration`/`_write_warp_artifacts`/`_draw_grid_overlay`/`_last_good_mf`；artifact-aware `_unlink_manifest_frame`。 |
| `katrain/web/api/v1/endpoints/baipu.py` | capture 透传 `fiducial_mode`/`drift_threshold_cells`（从 `app.state`），响应携带 `geometry_correction`。 |
| `katrain/web/server.py` | `app.state.baipu_fiducial_mode`（默认 `every-move`）/ `baipu_drift_threshold_cells`（0.15），可经 `settings` 覆盖。 |
| `katrain/vision/tools/baipu_autolabel.py` | `process_game(allow_legacy_drift)` 消费逐帧 `M_f`、质量门、`label_quality` 列；`--allow-legacy-drift` CLI。 |
| `katrain/web/ui/src/api/baipuApi.ts` | `BaipuGeometryCorrection` 类型 + `BaipuCaptureResult.geometry_correction`。 |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | `DriftBanner`（corrected/stale/frozen）+ 接线。 |

## 4. 执行结果（2026-06-27）

**测试（全绿）：**
- `tests/test_vision/test_fiducial_recalibrate.py` — 9 passed（含坐标空间正确性、旋转恢复、4 点+1 外点应失败、9 点+2 外点通过、ROI 多 blob、漂移分解）。
- `tests/test_baipu_capture.py` — 12 passed（3 新 fiducial：corrected/off/stale-回退 last-good；+ artifact 覆盖清理无孤儿；+ 9 既有回归）。
- `tests/test_baipu_api.py` — 11 passed（含 capture 响应携带 `geometry_correction`）。
- `tests/test_vision/test_baipu_autolabel.py` — 18 passed（含 corrected 用 `M_f` 不跑 `estimate_global_shift`、frozen+drift 默认隔离/`--allow-legacy-drift` 导出、legacy 回退 + `label_quality`）。
- `tests/test_geometry_drift.py` — 通过（回归）。
- 后端合计 **53 passed**（`fiducial_recalibrate + baipu_capture + baipu_api + geometry_drift` = 35；autolabel CI = 18）。
- 前端：`DriftBanner.test.tsx` 6 passed + `baipuApi.test.ts` 5 passed；`npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d` 3D 隔离）均退出 0。

**前端既有失败（非本期引入）：** 全量 `vitest` 有 19 个失败，分布在 `GamePage / theme / OrientationContext / AuthContext / TeachingSettingsDialog / ResearchPage` 等与 baipu 无关的子系统；已用 `HEAD~1` 复核确认为**本改动之前就存在**的技术债。P11 自身的前端测试与两套构建均绿。

## 5. 真机待办（硬件依赖，未在本机执行）

- **Step 6.3 SBC 延迟基准 gate（决策点）**：在 RK3562/3576/3588 上 `every-move` 跑 ≥20 手，记录每手新增阻塞（`clear+SHOW ACK`×3、`grab_fresh` dark/lit×2、`detect+solve`、`imwrite`×3）。判据：≤800ms 保持同步写；>800ms → artifact 异步写后台线程，仍超 → 默认降为「每 N 手强制」。把实测数字回填本节。
- **Step 6.4 真机重采 + 离线复核**：`every-move` 重摆一局（或重采 `kifu_24171`）→ `python -m katrain.vision.tools.baipu_autolabel --game-dir ~/.katrain/baipu_captures/<gid> --out-images /tmp/go4/images_raw --out-labels /tmp/go4/labels_raw --verify-dir /tmp/go4/verify` → 断言 `shifts.csv` 中 `corrected` 帧 `residual<5px`（对照现状 56% 帧 >10px）、`label_quality` 列符合预期；中途**故意碰移棋盘**验证在线 `corrected` + 横幅；摆到中后盘空点不足处验证 `stale` 告警不崩、不阻断。
- **baipu.spec.ts** 横幅 e2e：需 dev server（路由 mock `/baipu/capture` 返回 stale），随 6.4 一并验。

## 6. Known limits

- **中后盘退化**：填充率高时凑不齐 ≥8 空 fiducial → `stale`（沿用 last-good）；相邻手增量漂移小，可接受，但极满盘可能长期 `stale`。manifest/UI 已诚实暴露。
- **`drift-gated` 未实现**：需旋转感知预检（如 ORB/特征匹配），留作后续。
- **旧 `kifu_24171` 不可训练**：无 fiducial 帧、且盘动过 → 离线默认隔离；需重采。
- **单色 fiducial**：本期统一低亮度绿（channel 1）；低信噪场景的红/蓝重试留作后续。
