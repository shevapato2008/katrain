"""
Camera calibration tool using a printed checkerboard pattern.

Usage:
    1. Print a checkerboard pattern (e.g. 9x6 inner corners)
    2. Run: python -m katrain.vision.tools.calibrate_camera --camera 0 --rows 9 --cols 6
    3. Take 10-15 photos from different angles (press SPACE to capture)
    4. Press Q to finish — calibration parameters saved to camera_calibration.npz

The .npz file contains camera_matrix and dist_coeffs for cv2.undistort().
"""

import argparse
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Calibrate camera with checkerboard")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--rows", type=int, default=9, help="Inner corner rows in checkerboard")
    parser.add_argument("--cols", type=int, default=6, help="Inner corner cols in checkerboard")
    parser.add_argument("--output", type=str, default="camera_calibration.npz")
    args = parser.parse_args()

    pattern_size = (args.cols, args.rows)
    objp = np.zeros((args.cols * args.rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0 : args.cols, 0 : args.rows].T.reshape(-1, 2)

    obj_points = []
    img_points = []

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    print(f"Show checkerboard ({args.cols}x{args.rows} inner corners) to camera.")
    print("SPACE = capture | Q = finish calibration")

    img_size = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if img_size is None:
            img_size = gray.shape[::-1]

        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        display = frame.copy()
        if found:
            cv2.drawChessboardCorners(display, pattern_size, corners, found)

        cv2.putText(display, f"Captures: {len(obj_points)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Calibration", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and found:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            obj_points.append(objp)
            img_points.append(corners_refined)
            print(f"Captured {len(obj_points)} images")

    cap.release()
    cv2.destroyAllWindows()

    if len(obj_points) < 5:
        print(f"Need at least 5 captures, got {len(obj_points)}. Aborting.")
        return

    print("Calibrating...")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, img_size, None, None)

    print(f"Calibration RMS error: {ret:.4f}")
    print(f"Camera matrix:\n{camera_matrix}")
    print(f"Distortion coefficients: {dist_coeffs.ravel()}")

    np.savez(args.output, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
