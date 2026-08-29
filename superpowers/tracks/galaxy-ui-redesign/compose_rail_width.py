#!/usr/bin/env python3
"""右栏加宽的四图合成：before / after / 并排 / 差异。

before 与 after 出自**同一次构建**（before 用 CSS 覆盖把栏宽压回旧三档），
所以两张图之间除了栏宽没有别的变量——字体、抗锯齿、随机化的落子全一样。
用法：python3 superpowers/tracks/galaxy-ui-redesign/compose_rail_width.py
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent / "visual" / "rail-width"
GAP, BAR = 24, 46
BG, FG = (18, 18, 18), (235, 233, 230)


def label(img, text):
    out = Image.new("RGB", (img.width, img.height + BAR), BG)
    out.paste(img, (0, BAR))
    ImageDraw.Draw(out).text((12, 14), text, fill=FG)
    return out


for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and "x" in p.name):
    before, after = d / "before.png", d / "implementation.png"
    if not (before.exists() and after.exists()):
        continue
    b, a = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")

    lb, la = label(b, f"BEFORE  {d.name}  rail 320/340/380"), label(a, f"AFTER  {d.name}  rail 320/360/420/520/620")
    side = Image.new("RGB", (lb.width + GAP + la.width, max(lb.height, la.height)), BG)
    side.paste(lb, (0, 0))
    side.paste(la, (lb.width + GAP, 0))
    side.save(d / "side-by-side.png")

    diff = ImageChops.difference(b, a).convert("L").point(lambda v: 255 if v > 12 else 0)
    changed = sum(diff.point(lambda v: 1 if v else 0).getdata())
    bbox = diff.getbbox()
    over = Image.blend(b, Image.merge("RGB", (diff, Image.new("L", diff.size), Image.new("L", diff.size))), 0.55)
    over.save(d / "diff-overlay.png")
    print(f"{d.name}: changed={changed} px  bbox={bbox}")
