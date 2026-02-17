"""
Diagnose board detection on a single image — saves annotated debug output.

Usage:
    python -m katrain.vision.tools.diagnose_image --image photo.jpg
    python -m katrain.vision.tools.diagnose_image --image photo.jpg --use-clahe
"""

import argparse

import cv2
import numpy as np

from katrain.vision.board_finder import BoardFinder


def diagnose(image_path: str, use_clahe: bool = False, canny_min: int = 30, canny_max: int = 250):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: cannot read {image_path}")
        return

    h, w = img.shape[:2]
    print(f"Image: {w}x{h}")

    finder = BoardFinder()

    # --- Run Canny pipeline manually for diagnostics ---
    processed = img.copy()
    if use_clahe:
        lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_ch = clahe.apply(l_ch)
        lab = cv2.merge([l_ch, a_ch, b_ch])
        processed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        print("CLAHE: ON")

    gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(processed, (3, 3), 0, 0)
    canny = cv2.Canny(blurred, canny_min, canny_max)
    k = np.ones((3, 3), np.uint8)
    canny = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, k)

    contours, _ = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    frame_area = h * w
    debug = img.copy()

    print(f"\nFrame area: {frame_area}")
    print(f"Total contours found: {len(contours)}")
    print(f"Min perimeter threshold: {finder.min_perimeter}")
    print()

    for i, contour in enumerate(contours[:10]):
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        epsilon = 0.02 * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)
        is_convex = cv2.isContourConvex(approx) if len(approx) >= 3 else False
        rect = cv2.boundingRect(approx)
        _, _, rw, rh = rect
        aspect = rw / rh if rh > 0 else 0
        area_pct = area / frame_area * 100

        status = "OK" if (len(approx) == 4 and is_convex and 0.7 <= aspect <= 1.4 and area_pct >= 10) else "REJECT"
        reject_reasons = []
        if len(approx) != 4:
            reject_reasons.append(f"vertices={len(approx)}")
        if not is_convex:
            reject_reasons.append("non-convex")
        if aspect < 0.7 or aspect > 1.4:
            reject_reasons.append(f"aspect={aspect:.2f}")
        if area_pct < 10:
            reject_reasons.append(f"area={area_pct:.1f}%")

        color = (0, 255, 0) if status == "OK" else (0, 0, 255)
        cv2.drawContours(debug, [contour], -1, color, 2)

        # Label
        cx, cy = rect[0], rect[1]
        cv2.putText(debug, f"#{i}", (cx, cy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        reason_str = ", ".join(reject_reasons) if reject_reasons else ""
        print(
            f"  #{i}: area={area_pct:5.1f}%  perim={perimeter:7.0f}  vertices={len(approx)}  "
            f"convex={is_convex}  aspect={aspect:.2f}  → {status} {reason_str}"
        )

        # Draw approxPolyDP corners
        if len(approx) == 4:
            for pt in approx:
                cv2.circle(debug, (pt[0][0], pt[0][1]), 6, (255, 0, 255), -1)

    # --- Run actual find_focus ---
    print("\n--- find_focus() result ---")
    warped, found = finder.find_focus(img, min_threshold=canny_min, max_threshold=canny_max, use_clahe=use_clahe)
    print(f"found={found}")
    if warped is not None:
        print(f"warped shape: {warped.shape}")
        cv2.imwrite("diag_warped.jpg", warped)
        print("Saved diag_warped.jpg")

    cv2.imwrite("diag_contours.jpg", debug)
    cv2.imwrite("diag_canny.jpg", canny)
    print("\nSaved diag_contours.jpg, diag_canny.jpg")


def main():
    parser = argparse.ArgumentParser(description="Diagnose board detection on a single image")
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--use-clahe", action="store_true")
    parser.add_argument("--canny-min", type=int, default=30)
    parser.add_argument("--canny-max", type=int, default=250)
    args = parser.parse_args()
    diagnose(args.image, args.use_clahe, args.canny_min, args.canny_max)


if __name__ == "__main__":
    main()
