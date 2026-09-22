# -*- coding: utf-8 -*-
"""线性视差公式的校核 —— 用精确二次曲面独立算一遍，报实际残差。

线性公式把棋子当成一个点。真棋子是扁椭球，从镜头看过去的轮廓是切锥与椭球的交线。
这里不复述公式的算术，而是走完整的射影几何：

  模型 A  切锥 ∩ 棋盘平面 -> 圆锥曲线，取其中心
          = 先把整幅图透视矫正、再在矫正图上跑检测
  模型 B  同一切锥投到真实像平面（法向 = 光轴）得椭圆，取像平面上的椭圆中心，
          再沿视线反投回棋盘面
          = 在原图上取 bbox 中心、再用单应把这一个点映过去

椭球齐次矩阵 Q，从 C 作的切锥 K = (C^T Q C)·Q − (QC)(QC)^T。

单位 mm，坐标为 Fusion 文档系。2026-09-21 实测输入，来源见 geometry.md。
"""
import numpy as np

LENS = np.array([0.0, -70.54526924505564, 348.9424157107176])
PCB = np.array([0.0, -61.57836239584512, 365.8067147343231])
AXIS = (LENS - PCB) / np.linalg.norm(LENS - PCB)
A_EQ, C_POL = 11.0, 3.5          # 棋子扁椭球：赤道半径 / 极半径（⌀22 x 7 实测）
PX, PY, N = 23.7, 22.0, 19

POSES = {
    'aligned': dict(label='对位修正后（棋盘 +14 / +2 / −2.5）', z_board=9.5, x0=-213.3, y0=-502.0),
    'current': dict(label='当前 CAD 位姿（对位未做）', z_board=12.0, x0=-227.3, y0=-504.0),
}


def ellipsoid_Q(cx, cy, cz, a, c):
    d = np.array([1.0 / a**2, 1.0 / a**2, 1.0 / c**2])
    e = np.array([cx, cy, cz])
    Q = np.zeros((4, 4))
    Q[:3, :3] = np.diag(d)
    Q[:3, 3] = Q[3, :3] = -d * e
    Q[3, 3] = float(d @ (e * e)) - 1.0
    return Q


def tangent_cone(Q, C):
    Ch = np.append(C, 1.0)
    QC = Q @ Ch
    return float(Ch @ QC) * Q - np.outer(QC, QC)


def conic_center(M):
    return np.linalg.solve(M[:2, :2], -M[:2, 2])


def image_basis():
    n = AXIS
    u = np.array([1.0, 0.0, 0.0]) - n * (np.array([1.0, 0.0, 0.0]) @ n)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u), n


U, V, NX = image_basis()


def exact_A(C, px, py, zb):
    K = tangent_cone(ellipsoid_Q(px, py, zb + C_POL, A_EQ, C_POL), C)
    S = np.array([[1, 0, 0], [0, 1, 0], [0, 0, zb], [0, 0, 1]], float)
    return conic_center(S.T @ K @ S)


def exact_B(C, px, py, zb, f=100.0):
    K = tangent_cone(ellipsoid_Q(px, py, zb + C_POL, A_EQ, C_POL), C)
    o = C + f * NX
    S = np.column_stack([np.append(U, 0.0), np.append(V, 0.0), np.append(o, 1.0)])
    m = conic_center(S.T @ K @ S)
    d = (o + m[0] * U + m[1] * V) - C
    return (C + (zb - C[2]) / d[2] * d)[:2]


def linear(C, px, py, H, h):
    k = h / (H - h)
    return np.array([px + (px - C[0]) * k, py + (py - C[1]) * k])


def run():
    C = LENS
    print('光轴 %s  偏离竖直 %.3f°' % (np.round(AXIS, 6), np.degrees(np.arccos(-AXIS[2]))))
    print('棋子 ⌀%.1f x %.1f  体积 %.4f mm³' % (2 * A_EQ, 2 * C_POL,
                                              4 / 3 * np.pi * A_EQ**2 * C_POL))
    for key, p in POSES.items():
        zb, H = p['z_board'], C[2] - p['z_board']
        rA, rB, mags = [], [], []
        for j in range(N):
            for i in range(N):
                px, py = p['x0'] + PX * i, p['y0'] + PY * j
                lin = linear(C, px, py, H, C_POL)
                rA.append(np.linalg.norm(exact_A(C, px, py, zb) - lin))
                rB.append(np.linalg.norm(exact_B(C, px, py, zb) - lin))
                mags.append(np.linalg.norm(lin - [px, py]))
        print('--- %s' % p['label'])
        print('    H = %.4f   k(h=t/2) = %.6f   max|Δ| = %.4f mm'
              % (H, C_POL / (H - C_POL), max(mags)))
        print('    模型 A 残差  max %.4f  mean %.5f mm' % (max(rA), np.mean(rA)))
        print('    模型 B 残差  max %.4f  mean %.5f mm' % (max(rB), np.mean(rB)))
        print('    最大残差占半格(%.1f mm)  A %.3f%%  B %.3f%%'
              % (PY / 2, 100 * max(rA) / (PY / 2), 100 * max(rB) / (PY / 2)))


if __name__ == '__main__':
    run()
