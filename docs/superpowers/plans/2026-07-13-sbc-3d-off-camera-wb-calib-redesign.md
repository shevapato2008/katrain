# SBC 修复三合一：关 3D · 摄像头白平衡 · 标定页重设计

日期：2026-07-13 · 分支：`feature/kiosk-ui-redesign` → `develop` → submodule → SBC 部署

诊断来源：live SBC (`ssh rk3562-direct`) 排障。根因见对话记录。

## 背景（已在设备上确认的根因）

- **反应慢**：4 核 RK3562 负载 12、CPU 仅 ~15% 空闲、784MB swap。three.js WebGL 占 **321MB Mali GPU 内存**（统一内存 = 系统 RAM），并与 KataGo 的 OpenCL（399MB GPU）**争抢同一块 Mali GPU**。YOLO 本身健康（NPU，~250ms）。→ 关掉 kiosk 3D。
- **画面发红**：`lock_awb=True` → `camera.py` 每次 open 都 `cap.set(CAP_PROP_AUTO_WB, 0)`，禁用自动白平衡；HBV 摄像头手动 WB(4600K) 不生效 → 红偏 3×。Mac 上 AVFoundation 忽略该控制所以正常。实测 `AUTO_WB=1` → R/G/B 142/146/147 中性（已在设备上验证）。
- **标定画面太小**：`GeometryCalibrationWorkspace` 在 1024px 宽屏并排两个预览（16:9 + 1:1）+ 大量文字 chrome → 每格网格 ~13px 看不清。

## 变更

### A. 摄像头白平衡永久修复（backend）
1. `katrain/web/core/capture_service.py:35`  `lock_awb: bool = True` → `False`
2. `katrain/web/core/camera_hub.py:18`       `lock_awb: bool = True` → `False`
3. `katrain/web/vision/camera.py:172-173` — 不锁 WB 时**显式启用** auto WB（V4L2 状态跨进程持久，必须主动置 1）：
   ```python
   if self._lock_awb:
       cap.set(cv2.CAP_PROP_AUTO_WB, 0)
   else:
       cap.set(cv2.CAP_PROP_AUTO_WB, 1)
   ```
   仅动 WB，不碰曝光（曝光由 software-AE 处理，与红偏无关）。

### B. 关闭 kiosk 3D / WebGL（frontend + 构建边界）
4. `GameControlPanel.tsx` — 删 3D `ItemToggle`（108-110）、`ViewInAr` import（8）、`webgl` useState（42）。
5. `GamePage.tsx` — 删 `view3d` 初值（105）、Board3D 懒加载 state+effect（108-119）、Board3D 渲染（528-560）、`kiosk_view3d` 持久化（563）；清理 `ComponentType`/`BoardProps` 未用 import。
6. `GameControlPanel.test.tsx` / `GamePage.test.tsx` — 去掉 3D 相关断言。
7. **重新收紧 kiosk-2d 边界**（撤销 Plan-2 T1，保证 three.js 物理不进 kiosk bundle）：
   - `vite.config.ts`：kiosk 模式恢复 `rollupOptions.external:['three','@react-three/fiber','@react-three/drei']`
   - `eslint.config.js`：`forbiddenFromKiosk` 恢复 `components/Board3D/**` 禁令
   - `scripts/verify-kiosk.sh`：恢复 `THREE.`/`three`/`@react-three` grep 门
   - **galaxy/full build 的 Board3D 不动**（服务器/桌面端保留 3D）。

### C. 标定页重设计（frontend-design）— mockup 已确认
- 单张大预览（近 520px 方形），分段控件切换 俯视矫正 / 摄像头原始；`ready` 后自动切俯视核对。
- 头部压成一行（返回 + 标题 + 摄像头/LED 状态 chip）；相位/诊断/指标/操作收进右栏 292px。
- 复用 kiosk 主题（jade #58b57a / slate / Newsreader serif）。改 `GeometryCalibrationWorkspace.tsx`（+ 可能 `GeometryVideoPanel`）；`VisionSetupPage` 容器基本不变。

## 门禁 — ✅ 已通过 (2026-07-13)
`tsc -b` 0 err · vitest 586/586 · `npm run build`(full, galaxy 3D 保留) + `npm run build:kiosk-2d` 均 exit 0 · `verify:kiosk-2d` 干净(**three.js 已从 kiosk dist 移除**,KioskApp.js 408KB) · py_compile OK · pytest camera_hub/capture_service/geometry_api 25/25。
标定页两处调整已落地:智星盒外框沿用 KioskLayout(vision/setup 本就在其内)· 俯视矫正复用 `warp_with_margin`(1 cell margin,overlay 同步内缩)。

## 部署（用户指令 1-4）
1. commit 到 `feature/kiosk-ui-redesign` → push
2. merge → `develop` → push
3. bump `smartbox-software/vendor/katrain` submodule（+ 提交 superproject）
4. 部署 SBC：拉新码 → **必须重建 `static-kiosk-2d`**（`npm run build:kiosk-2d`，不是 `npm run build`）→ 重启 `smartbox-katrain`。
   - 检查 `smartbox-software/provisioning/*` 与 `scripts/board_upgrade.sh`（已知 bug：build 错 bundle）——如影响 golden image 则一并修正。
