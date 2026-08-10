#!/usr/bin/env python3
"""ASCII portrait generator with typing animation, per the setup guide.
Pipeline: rembg cutout -> bilateral filter -> CLAHE -> darkening curve -> ramp -> SVG.

Usage: python generate_portrait.py <input_photo.jpg> [output.svg]

Requirements (not stdlib): pillow, numpy, opencv-python-headless, rembg, onnxruntime
  pip install pillow numpy opencv-python-headless rembg onnxruntime
First run downloads a ~176MB background-removal model, cached after that.
"""

import sys
import numpy as np
import cv2
from PIL import Image
from rembg import remove

# Same ramp as the stats generator - shared visual language across the whole page.
RAMP = " .`:-=+*cs#%@"

COLS = 90
FONT_SIZE = 12.9
CHAR_W = 7.74      # exactly 0.600 em advance width at this font-size - matches
                    # JetBrains Mono/Liberation Mono/DejaVu Sans Mono/Noto Sans Mono.
                    # Consolas (Windows default) is ~0.55 - a visitor without the
                    # embedded font sees the portrait ~7% narrower. Part 4 fixes this
                    # by inlining the font, so this constant only matters for our own
                    # layout math here, not for what a visitor's browser renders with.
DISPLAY_PX = 460


def load_and_cut(path):
    img = Image.open(path).convert("RGB")
    cut = remove(img)  # forces background to transparent -> composited to white below
    bg = Image.new("RGB", cut.size, (255, 255, 255))
    bg.paste(cut, mask=cut.split()[3] if cut.mode == "RGBA" else None)
    return bg


def process(img):
    arr = np.array(img.convert("L"))
    # Bilateral filter: smooths skin while keeping edges (unlike gaussian blur).
    arr = cv2.bilateralFilter(arr, d=9, sigmaColor=75, sigmaSpace=75)
    # CLAHE: local contrast per tile, not global autocontrast (which leaves a
    # flatly-lit face as one flat tone).
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    arr = clahe.apply(arr)
    # The fix: without this curve the face comes out washed out/featureless.
    # This is what makes glasses, brows, and lips survive to the ramp mapping.
    normalized = arr.astype(np.float64) / 255.0
    darkened = np.power(normalized, 1.7)
    return (darkened * 255).astype(np.uint8)


def to_ascii_rows(arr):
    h, w = arr.shape
    cols = COLS
    rows = int(cols * (h / w) * 0.48)  # monospace chars are ~2x taller than wide
    resized = cv2.resize(arr, (cols, rows), interpolation=cv2.INTER_AREA)
    ramp_len = len(RAMP)
    lines = []
    for r in range(rows):
        line = []
        for c in range(cols):
            v = resized[r, c]
            idx = min(ramp_len - 1, int((v / 255) * (ramp_len - 1)))
            line.append(RAMP[idx])
        lines.append("".join(line))
    return lines


def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&#32;")


def render_svg(lines, out_path):
    n_rows = len(lines)
    n_cols = max(len(l) for l in lines) if lines else 0
    width = n_cols * CHAR_W
    height = n_rows * FONT_SIZE * 1.0
    stagger = 0.09
    total_time = n_rows * stagger + 1.2

    row_svgs = []
    for i, line in enumerate(lines):
        row_w = len(line) * CHAR_W
        begin = round(i * stagger, 3)
        dur = 0.9
        row_svgs.append(f'''
  <clipPath id="clip{i}">
    <rect x="0" y="{i*FONT_SIZE}" width="0" height="{FONT_SIZE}">
      <animate attributeName="width" from="0" to="{row_w}" begin="{begin}s" dur="{dur}s" fill="freeze"/>
    </rect>
  </clipPath>''')

    text_svgs = []
    cursor_svgs = []
    for i, line in enumerate(lines):
        row_w = len(line) * CHAR_W
        begin = round(i * stagger, 3)
        dur = 0.9
        text_svgs.append(
            f'<text x="0" y="{(i+1)*FONT_SIZE - 2}" font-size="{FONT_SIZE}" '
            f'clip-path="url(#clip{i})" xml:space="preserve">{escape(line)}</text>'
        )
        cursor_svgs.append(f'''
  <rect y="{i*FONT_SIZE}" width="{CHAR_W}" height="{FONT_SIZE}" fill="#58a6ff">
    <animate attributeName="x" from="0" to="{row_w}" begin="{begin}s" dur="{dur}s" fill="freeze"/>
    <set attributeName="opacity" to="0" begin="{begin+dur}s" fill="freeze"/>
  </rect>''')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{DISPLAY_PX}" height="{height*(DISPLAY_PX/width):.0f}"
     viewBox="0 0 {width} {height}">
<defs>
  <style>
    @font-face {{
      font-family: 'PortraitRamp';
      src: url(data:font/woff2;base64,PLACEHOLDER_RAMP_FONT_BASE64) format('woff2');
    }}
    text {{ font-family: 'PortraitRamp', 'JetBrains Mono', monospace; fill: #c9d1d9; }}
  </style>
  <rect id="bg" width="{width}" height="{height}" fill="#0d1117"/>
{"".join(row_svgs)}
</defs>
<use href="#bg"/>
{"".join(text_svgs)}
{"".join(cursor_svgs)}
</svg>'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {out_path}: {n_rows} rows x {n_cols} cols, ~{total_time:.1f}s to finish typing")
    print("NOTE: PLACEHOLDER_RAMP_FONT_BASE64 needs the real subset font inlined - see subset_font.py / Part 4")


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_portrait.py <input_photo.jpg> [output.svg]")
        sys.exit(1)
    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "portrait.svg"

    print("Loading and removing background...")
    img = load_and_cut(in_path)
    print("Applying bilateral filter + CLAHE + darkening curve...")
    processed = process(img)
    print(f"Converting to ASCII ({COLS} columns)...")
    lines = to_ascii_rows(processed)
    render_svg(lines, out_path)


if __name__ == "__main__":
    main()
