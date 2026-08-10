#!/usr/bin/env python3
"""Section headings as SVG - the only way to put a custom typeface on a heading,
since GitHub strips <style>/CSS/inline fonts from README markdown itself.
Lowercase mono label with a hairline rule running to the right edge, per Part 3.
"""
import base64
import os

LABELS = ["languages", "year"]
WIDTH = 460
HEIGHT = 28
FONT_PATH = "fonts/headings.woff2"


def main():
    with open(FONT_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    os.makedirs("headings", exist_ok=True)
    for label in LABELS:
        text_w = len(label) * 8.5
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<defs>
  <style>
    @font-face {{
      font-family: 'HeadingFont';
      src: url(data:font/woff2;base64,{b64}) format('woff2');
    }}
    text {{ font-family: 'HeadingFont', monospace; fill: #6e7681; letter-spacing: 2px; }}
  </style>
</defs>
<text x="0" y="19" font-size="13">{label}</text>
<line x1="{text_w + 14}" y1="14" x2="{WIDTH}" y2="14" stroke="#30363d" stroke-width="1"/>
</svg>'''
        with open(f"headings/{label}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote headings/{label}.svg")


if __name__ == "__main__":
    main()
