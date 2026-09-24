"""按新单应重建 GeometryLock。

外框法(`OuterCornerStrategy`)只给得出 `M` / `Minv` —— 它是**帧单应**,
不产出整张网格。而识别用的是 `points`(19×19 的交叉点像素坐标),
所以要用新的 M 把四角映回原图,再走和首次标定同一个 `grid_points_from_corners`。

**朝向**(PRD §2.1 R2):外框法按**画面位置**排四角(`sort_corners`),LED 锁按**棋盘行列**排。
两者不一定一致 ⇒ 重建时把四角重排成离旧锁最近的那一种,否则整张网格转 90°/180°,
识别坐标、维持档、视差(`mount_parallax_for_lock` 按四角顺序认哪条边朝镜头)一起转。

`baseline`(空盘 HSV 基线)**原样保留**:它采在 warp 空间的 xs/ys 上,
几何对齐回同一块实体盘之后仍然成立;重采要空盘,而这条路存在的理由正是盘上有子。
"""

from dataclasses import replace

import cv2
import numpy as np
import pytest

from katrain.vision import geometry_calibrate
from katrain.vision.geometry_detect import sort_corners
from katrain.vision.geometry_lock import GeometryLock
from katrain.vision.parallax import mount_parallax_for_lock
from katrain.vision.relock import relock_with_homography

SIZE = 950
DST = np.array([[0, 0], [SIZE - 1, 0], [SIZE - 1, SIZE - 1], [0, SIZE - 1]], np.float32)
# 画面里的外框:下边成像最长 ⇒ 下边离镜头最近(视差认边靠的就是这个)。
IMG_QUAD = np.array([[200, 100], [800, 100], [900, 700], [100, 700]], np.float32)
BUMP = np.array([6.0, -4.0], np.float32)  # 盘被推了一点


def _lock(corners):
    corners = np.asarray(corners, np.float32)
    M = cv2.getPerspectiveTransform(corners, DST).astype(np.float64)
    xs = np.linspace(0, SIZE - 1, 19).astype(np.float32)
    return GeometryLock(
        corners=corners,
        points=geometry_calibrate.grid_points_from_corners(corners, size=SIZE).astype(np.float32),
        xs=xs,
        ys=xs.copy(),
        M=M,
        Minv=np.linalg.inv(M),
        out_size=SIZE,
        baseline=np.full((19, 19, 3), 7.0, np.float32),
        confidence=0.9,
    )


def _outer_M(quad):
    """外框法的输出形状:四角按**画面**左上/右上/右下/左下排,与锁的朝向无关。"""
    return cv2.getPerspectiveTransform(sort_corners(quad), DST).astype(np.float64)


def test_points_match_the_shared_grid_helper():
    lock = _lock(IMG_QUAD)
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    expected = geometry_calibrate.grid_points_from_corners(IMG_QUAD + BUMP, size=SIZE)
    assert np.allclose(out.points, expected, atol=0.5)
    assert np.allclose(out.corners, IMG_QUAD + BUMP, atol=0.5)


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_relock_keeps_the_lock_orientation(roll):
    """旧锁的四角是画面顺序转过 roll 格;外框法给的永远是画面顺序。重建后必须仍是旧锁的顺序。"""
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert np.allclose(out.corners, np.roll(IMG_QUAD + BUMP, roll, axis=0), atol=0.5)
    assert np.allclose(out.points[0, 0], lock.points[0, 0] + BUMP, atol=0.5)  # 只随平移动,不换点


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_parallax_nadir_stays_on_the_same_edge(roll):
    """**守住 develop 的视差校正**(`f522fe53`):worker 在 set_geometry 里按新锁重推 nadir,
    朝镜头的是哪条边由四角顺序决定。朝向没对齐,nadir 就换到另一条边。"""
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert mount_parallax_for_lock(out).nadir == mount_parallax_for_lock(lock).nadir


def test_mirrored_lock_order_is_kept_too():
    mirrored = IMG_QUAD[[0, 3, 2, 1]]
    out = relock_with_homography(_lock(mirrored), _outer_M(IMG_QUAD + BUMP))
    assert np.allclose(out.corners, mirrored + BUMP, atol=0.5)


def test_without_alignment_the_nadir_would_move():
    """对照:直接用画面顺序建锁(不对齐)时 nadir 会换边 —— 证明上面那条测得到东西。"""
    lock = _lock(np.roll(IMG_QUAD, 1, axis=0))
    M = _outer_M(IMG_QUAD)
    naive = replace(lock, corners=IMG_QUAD, M=M, Minv=np.linalg.inv(M))
    assert mount_parallax_for_lock(naive).nadir != mount_parallax_for_lock(lock).nadir


def test_a_board_turned_half_way_is_refused():
    """盘转了约 45°:最近与次近两种排法一样近,分不出朝向 ⇒ 拒绝,不猜。"""
    square = np.array([[100, 100], [900, 100], [900, 900], [100, 900]], np.float32)
    c, th = np.array([500.0, 500.0]), np.deg2rad(45)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    turned = ((square - c) @ R.T + c).astype(np.float32)
    with pytest.raises(ValueError, match="orientation_ambiguous"):
        relock_with_homography(_lock(square), cv2.getPerspectiveTransform(turned, DST))


def test_baseline_is_carried_over_untouched():
    lock = _lock(IMG_QUAD)
    out = relock_with_homography(lock, lock.M)
    assert out.baseline is lock.baseline or np.array_equal(out.baseline, lock.baseline)


def test_original_lock_is_not_mutated():
    lock = _lock(IMG_QUAD)
    before = lock.points.copy()
    relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert np.array_equal(lock.points, before)


def test_singular_homography_raises():
    with pytest.raises(ValueError):
        relock_with_homography(_lock(IMG_QUAD), np.zeros((3, 3), np.float64))


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_a_real_bump_is_accepted(roll):
    """真碰盘:平移 + 小角度旋转 + 一点透视。朝向保持,nadir 同边。"""
    c, th = IMG_QUAD.mean(axis=0), np.deg2rad(8)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    bumped = ((IMG_QUAD - c) @ R.T + c + np.array([25.0, -15.0])).astype(np.float32)
    bumped[2] += np.array([6.0, 4.0], np.float32)  # 透视:一个角多挪一点
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(bumped))
    assert np.allclose(out.corners, np.roll(bumped, roll, axis=0), atol=0.5)
    assert mount_parallax_for_lock(out).nadir == mount_parallax_for_lock(lock).nadir


def test_a_board_moved_far_is_refused():
    """挪了 4 格:不是碰动,是换了位置 —— 拒绝,交给用户重新标定。"""
    cell = (IMG_QUAD[1, 0] - IMG_QUAD[0, 0]) / 18.0
    with pytest.raises(ValueError, match="moved_too_far"):
        relock_with_homography(_lock(IMG_QUAD), _outer_M(IMG_QUAD + np.array([4 * cell * 1.2, 0], np.float32)))


def test_new_lock_records_the_frame_resolution_it_was_computed_on():
    """旧锁在 1920x1080 上标定,这次帧是 1280x720:四角先换算再对齐,新锁记本次尺寸。"""
    lock = _lock(IMG_QUAD * 1.5)
    lock.source_width, lock.source_height = 1920, 1080
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP), frame_size=(1280, 720))
    assert (out.source_width, out.source_height) == (1280, 720)
    assert np.allclose(out.corners, IMG_QUAD + BUMP, atol=0.5)


def test_confidence_and_diag_say_this_lock_came_from_relocation():
    lock = _lock(IMG_QUAD)
    lock.diag = {"source": "led_anchor_ransac", "orientation": "seated_human"}
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP), confidence=0.73)
    assert out.confidence == pytest.approx(0.73)
    assert out.diag["relocated_by"] == "outer_corner"
    assert out.diag["orientation"] == "seated_human"
    assert lock.diag == {"source": "led_anchor_ransac", "orientation": "seated_human"}  # 旧锁没被改
