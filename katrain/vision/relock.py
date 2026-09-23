"""把一个已有的 GeometryLock 搬到新的单应上(外框重定位用)。

`OuterCornerStrategy` 给的是**帧单应**(M / Minv),不产出网格与基线。识别要的是
`points`(19×19 交叉点像素坐标),所以这里用 M 把 warp 空间的四角映回原图,
再走与首次标定**同一个** `grid_points_from_corners` —— 两条路算网格的方式必须同源,
否则重定位之后的坐标会和标定时差一点点,而那一点点正好是「识别串位」。

**朝向**:外框法按画面位置排四角,LED 锁按棋盘行列排(`diag.orientation = "seated_human"`)。
这里把四角重排成离旧锁四角最近的那一种(4 个起点 × 2 个绕向),M 按重排后的四角重算。
盘只是被碰动时,最近的那一种比次近的近得多;两者分不开(盘转了约 45°)就拒绝,不猜。
外框是对称的,**盘被整个转了 90° 是认不出来的** —— 这里的前提是「碰动」,即小位移;
挪得超过 MAX_SHIFT_CELLS 就拒绝,交给用户重新标定。

**分辨率**:M 是在本次帧上算的。旧锁的四角先按它记录的源分辨率换算到本次帧坐标再比,
新锁记录本次帧的 `source_width/height` —— 否则 worker 的 `adjust_M_for_resolution`
会按旧尺寸把新 M 再缩放一次。

`baseline` 原样带过去:它采在 warp 空间的 xs/ys 上,几何对齐回同一块盘之后仍然成立;
重采需要空盘,而这条路存在的理由正是**盘上有子**。
"""

from dataclasses import replace

import cv2
import numpy as np

from katrain.vision import geometry_calibrate

# 同一块盘的四角在画面里的八种排法:四个起点 × 两个绕向。
_ORDERS = [tuple((start + step * i) % 4 for i in range(4)) for start in range(4) for step in (1, -1)]
# 「碰动」的上限:四角平均位移超过这么多格就不是碰动了(盘被挪走 / 换了位置),拒绝。
MAX_SHIFT_CELLS = 3.0


def _lock_corners_in_frame(lock, frame_size):
    corners = np.asarray(lock.corners, np.float64)
    src_w, src_h = getattr(lock, "source_width", None), getattr(lock, "source_height", None)
    if frame_size is None or not src_w or not src_h:
        return corners
    w, h = frame_size
    return corners * np.array([w / float(src_w), h / float(src_h)])


def _align_to_lock(quad, lock_corners):
    costs = sorted((float(np.linalg.norm(quad[list(order)] - lock_corners, axis=1).sum()), order) for order in _ORDERS)
    (best, order), (second, _) = costs[0], costs[1]
    if not best < 0.5 * second:
        raise ValueError("orientation_ambiguous")
    aligned = quad[list(order)]
    sides = np.linalg.norm(lock_corners - np.roll(lock_corners, -1, axis=0), axis=1)
    cell_px = float(sides.mean()) / 18.0
    if best / 4.0 > MAX_SHIFT_CELLS * cell_px:
        raise ValueError("moved_too_far")
    return aligned


def relock_with_homography(lock, M, Minv=None, *, frame_size=None, confidence=None):
    """``frame_size`` = (width, height) of the frames M was computed on."""
    M = np.asarray(M, np.float64)
    if M.shape != (3, 3):
        raise ValueError(f"M must be 3x3, got {M.shape}")
    if Minv is None:
        try:
            Minv = np.linalg.inv(M)
        except np.linalg.LinAlgError as exc:
            raise ValueError("singular homography") from exc
    Minv = np.asarray(Minv, np.float64)
    if not np.all(np.isfinite(Minv)):
        raise ValueError("singular homography")

    size = int(lock.out_size)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    quad = cv2.perspectiveTransform(dst.reshape(-1, 1, 2), Minv).reshape(4, 2)
    corners = _align_to_lock(quad, _lock_corners_in_frame(lock, frame_size)).astype(np.float32)
    M = cv2.getPerspectiveTransform(corners, dst).astype(np.float64)
    points = geometry_calibrate.grid_points_from_corners(corners, size=size).astype(np.float32)
    changes = dict(corners=corners, points=points, M=M, Minv=np.linalg.inv(M))
    if frame_size is not None:
        changes.update(source_width=int(frame_size[0]), source_height=int(frame_size[1]))
    if confidence is not None:
        changes["confidence"] = float(confidence)
    # 这把锁不是 LED 13 点出来的:diag 里点名,排查识别问题时有个起点。旧的 anchors 等键留着(那是 golden 的来历)。
    changes["diag"] = {**(lock.diag or {}), "relocated_by": "outer_corner"}
    # `replace` 返回新对象 —— 调用方可能还拿着旧 lock(失败时要回退到它);也不许原地改(PRD §2.1 R1)。
    return replace(lock, **changes)
