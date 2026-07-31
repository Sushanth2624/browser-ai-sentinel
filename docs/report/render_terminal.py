#!/usr/bin/env python3
"""Renders real captured command output as a terminal-style screenshot for report evidence.
Deliberately not a screenshot of an actual terminal emulator window (no window manager on this
headless VM) — instead draws the exact real stdout captured from an actual command run into a
terminal-styled image with PIL, macOS/VSCode-terminal-style traffic-light chrome. The text itself
is never invented or edited for effect; only its presentation is styled.
"""
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BG = "#1e1e2e"
FG = "#cdd6f4"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
BLUE = "#89b4fa"
DIM = "#7f849c"
TITLEBAR = "#181825"


def render_terminal(lines: list[str], out_path: str, title: str = "analysis@bas-vm", font_size: int = 15,
                     width: int | None = None):
    font = ImageFont.truetype(FONT_PATH, font_size)
    pad_x, pad_y = 20, 16
    titlebar_h = 34
    line_h = int(font_size * 1.55)

    dummy = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(dummy)
    max_w = 0
    for text, _color in lines:
        bbox = d.textbbox((0, 0), text, font=font)
        max_w = max(max_w, bbox[2] - bbox[0])

    w = width or (max_w + pad_x * 2)
    h = titlebar_h + pad_y * 2 + line_h * len(lines)

    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, titlebar_h], fill=TITLEBAR)
    for i, color in enumerate((RED, YELLOW, GREEN)):
        d.ellipse([16 + i * 22, titlebar_h // 2 - 6, 16 + i * 22 + 12, titlebar_h // 2 + 6], fill=color)
    tf = ImageFont.truetype(FONT_PATH, 13)
    tb = d.textbbox((0, 0), title, font=tf)
    d.text(((w - (tb[2] - tb[0])) / 2, (titlebar_h - (tb[3] - tb[1])) / 2 - tb[1]), title, font=tf, fill=DIM)

    y = titlebar_h + pad_y
    for text, color in lines:
        d.text((pad_x, y), text, font=font, fill=color)
        y += line_h

    img.save(out_path)
    print(f"saved {out_path} ({w}x{h})")


def c(text, color=FG):
    return (text, color)


if __name__ == "__main__":
    import sys
    print("Import this module and call render_terminal(); see gen_evidence_terminals.py", file=sys.stderr)
