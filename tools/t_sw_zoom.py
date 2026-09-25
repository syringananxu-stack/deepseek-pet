# -*- coding: utf-8 -*-
"""自查开关细节(放大看:偏心 / 描边 / 阴影)"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import Image, ImageDraw          # noqa: E402

from dspet import uikit as U              # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
Z = 6
frames, w, h = U.switch_frames()
pick = [frames[0], frames[len(frames) // 2], frames[-1]]

sheet = Image.new("RGB", (w * Z * 3 + 40, h * Z + 40 + (h + 8) * 2), (236, 238, 242))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(pick):
    x = 10 + i * (w * Z + 10)
    big = f.resize((f.width * Z, f.height * Z), Image.NEAREST)
    sheet.paste(big, (x, 10), big)
    # 中线参考(看旋钮是否与轨道同心)
    cy = 10 + h * Z / 2
    d.line([(x - 6, cy), (x + w * Z + 6, cy)], fill=(255, 0, 128), width=1)

# 全帧条(2x)
strip = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
for i, f in enumerate(frames):
    strip.alpha_composite(f, (i * w, 0))
strip = strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST)
y0 = h * Z + 20
sheet.paste(strip.convert("RGB"), (10, y0), strip)

out = os.path.join(WS, "_sw_zoom.png")
sheet.save(out)
print("saved", out, sheet.size)
