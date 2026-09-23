# -*- coding: utf-8 -*-
"""棋子成像视差修正 —— 可直接接进识别流水线。

原理：识别器报的「棋子中心」在棋盘面上方 h 处，沿视线投回棋盘平面时
沿背离镜头方向外移。偏移是以 nadir 为中心、系数 m = H/(H-h) 的一次位似，
与俯角、焦距、FOV、畸变无关（前提：已用棋盘四角/网格做过透视矫正，
在棋盘平面坐标里计算）。

常量来自 Fusion 文档 ver9-camera-mount-fixed-j2 实测（对位修正后位姿）。
生产环境建议用 fit_from_samples() 现场标定，把 h、入瞳位置、装配误差一次吸收。
"""
import numpy as np

# ---- 实测常量（棋盘平面坐标，mm）------------------------------------------
CAM = (0.0, -70.545)      # nadir：镜头投影中心在棋盘面上的垂足
H = 339.4424              # 镜头离棋盘面高度
H_EFF = 3.5               # 棋子视觉中心高度 = 厚度/2（⌀22 x 7 扁椭球，上下对称）
K = (H - H_EFF) / H       # = 0.989686  修正系数

X0, Y0 = -213.3, -502.0   # 0 号线坐标（列 A / 行 19）
PX, PY = 23.7, 22.0       # 列间距 / 行间距
N = 19


def correct(dx, dy, cam=CAM, k=K):
    """识别到的棋子中心 -> 真实落点。dx, dy 为棋盘平面坐标 mm。"""
    return (cam[0] + (dx - cam[0]) * k,
            cam[1] + (dy - cam[1]) * k)


def forward(px, py, cam=CAM, k=K):
    """真实落点 -> 会被识别到的位置（做仿真/出偏移表用）。"""
    return (cam[0] + (px - cam[0]) / k,
            cam[1] + (py - cam[1]) / k)


def to_point(dx, dy, cam=CAM, k=K):
    """识别到的棋子中心 -> (列 i, 行 j)，均为 0..18。"""
    px, py = correct(dx, dy, cam, k)
    i = int(round((px - X0) / PX))
    j = int(round((py - Y0) / PY))
    return min(max(i, 0), N - 1), min(max(j, 0), N - 1)


def label(i, j):
    """(i, j) -> 'K10' 这样的坐标。列 A-T 跳过 I，行 1 靠近摄像头。"""
    return 'ABCDEFGHJKLMNOPQRST'[i] + str(N - j)


# ---- 现场标定：不假设 h，直接从实测数据解 m 和 nadir ------------------------
def fit_from_samples(P, D):
    """P: (n,2) 已知交点坐标；D: (n,2) 对应识别到的位置（同一平面坐标系）。

    正向模型 D = m*P + (1-m)*C，对 (m, bx, by) 线性。四角 + 天元五点即可
    （10 个方程 3 个未知数）。返回 (k, cam)，k 直接喂给 correct()。
    """
    P = np.asarray(P, float)
    D = np.asarray(D, float)
    n = len(P)
    A = np.zeros((2 * n, 3))
    b = np.zeros(2 * n)
    A[0::2, 0] = P[:, 0]; A[0::2, 1] = 1.0; b[0::2] = D[:, 0]
    A[1::2, 0] = P[:, 1]; A[1::2, 2] = 1.0; b[1::2] = D[:, 1]
    m, bx, by = np.linalg.lstsq(A, b, rcond=None)[0]
    cam = (bx / (1.0 - m), by / (1.0 - m))
    resid = np.linalg.norm(A @ [m, bx, by] - b) / np.sqrt(n)
    return 1.0 / m, cam, dict(m=m, rms_mm=resid, h_implied=H * (1 - 1 / m))


def apply_parallax(fx, fy, nadir, k):
    """连续网格坐标里的修正 —— 流水线要接的就是这一个。

    位似在仿射变换下不变：k 与坐标系无关，只有 nadir 要表示成同一坐标系里的一对数。
    所以这里的 (fx, fy) 可以是 board_state 的连续网格坐标，也可以是 mm。
    nadir 为 None 时是恒等映射（未标定 = 不修正）。
    """
    if nadir is None or k is None:
        return fx, fy
    return nadir[0] + (fx - nadir[0]) * k, nadir[1] + (fy - nadir[1]) * k


# CAD 推出来的 nadir 在连续网格坐标里的位置（对位修正后）。
# 只作参考：流水线的 (fx, fy) 原点与行列方向由 warp 的四角顺序决定，必须标定。
NADIR_GRID_CAD = ((CAM[0] - X0) / PX, (CAM[1] - Y0) / PY)   # (9.0000, 19.6116)


def dump_csv(path='offsets-361.csv'):
    """361 点偏移表。列 A-T 跳过 I，行 1 靠近摄像头。"""
    rows = ['point,i,j,x_mm,y_mm,dx_mm,dy_mm,mag_mm,pct_half_cell,far_margin_mm']
    for j in range(N):
        for i in range(N):
            p = (X0 + PX * i, Y0 + PY * j)
            d = forward(*p)
            dx, dy = d[0] - p[0], d[1] - p[1]
            mag = np.hypot(dx, dy)
            rows.append('%s,%d,%d,%.2f,%.2f,%.4f,%.4f,%.4f,%.1f,%.4f' % (
                label(i, j), i, j, p[0], p[1], dx, dy, mag,
                100 * mag / (PY / 2), PY / 2 - abs(dy)))
    with open(path, 'w') as f:
        f.write('\n'.join(rows) + '\n')
    return len(rows) - 1, path


if __name__ == '__main__':
    import sys
    if '--csv' in sys.argv:
        n, path = dump_csv()
        print('wrote %d rows -> %s' % (n, path))
        raise SystemExit
    # 自检：正向 + 反向必须回到原点；最远一排偏移量与网页一致
    worst = None
    for j in range(N):
        for i in range(N):
            p = (X0 + PX * i, Y0 + PY * j)
            d = forward(*p)
            back = correct(*d)
            assert max(abs(back[0] - p[0]), abs(back[1] - p[1])) < 1e-9
            assert to_point(*d) == (i, j), (i, j, to_point(*d))
            mag = np.hypot(d[0] - p[0], d[1] - p[1])
            if worst is None or mag > worst[0]:
                worst = (mag, label(i, j), d[0] - p[0], d[1] - p[1])
    print('K = %.6f   nadir = %s   H = %.4f   h = %.1f' % (K, CAM, H, H_EFF))
    print('往返自检 361 点全过；snap 全部回到原交点')
    print('最大偏移 %.3f mm @ %s   (dx %.3f, dy %.3f)' % worst)
    print('远端剩余摆子容差 %.3f mm（半格 %.1f）' % (PY / 2 - abs(worst[3]), PY / 2))
