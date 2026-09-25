# -*- coding: utf-8 -*-
"""开关:改前 / 改后 对比图(给东家看的那种)"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import Image, ImageDraw, ImageFont        # noqa: E402

from dspet import uikit as U                       # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
Z = 4


def old_frames(on=U.GREEN, off=U.TRACK_OFF, w=42, h=24, ins=2):
    """改前的画法:无描边、旋钮带较重下阴影(所以看着"陷下去")"""
    from PIL import ImageFilter
    W, H = w, h
    dk_ = H - 2 * ins
    travel = max(1, W - 2 * ins - dk_)
    out = []
    for i in range(travel + 1):
        t = i / float(travel)
        L = U.Layer(W, H)
        L.rrect((0, 0, W - 1, H - 1), (H - 1) / 2.0, fill=U.rgb(U.mix(off, on, t)) + (255,),
                outline=None)
        L.shadow((0.5, 0.5, W - 0.5, H * 0.55), (H - 1) / 2.0, blur=1.5, dy=0.3,
                 alpha=0.16)
        L.rrect((1.2, H - 1.8, W - 1.2, H - 0.7), (H - 1) / 2.0, fill=(255, 255, 255, 26))
        kx = ins + int(round(t * travel))
        L.shadow((kx, ins, kx + dk_, ins + dk_), dk_ / 2.0, blur=1.1, dy=0.6, alpha=0.30)
        L.ellipse((kx, ins, kx + dk_, ins + dk_), fill=(255, 255, 255, 255),
                  outline=(0, 0, 0, 18), width=0.5)
        out.append(L.out())
    return out


try:
    f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
except Exception:
    f = None

old = old_frames()
new, w, h = U.switch_frames()
picks = (0, len(old) // 2, len(old) - 1)

sheet = Image.new("RGB", (w * Z * 3 + 120, h * Z * 2 + 150), (236, 238, 242))
d = ImageDraw.Draw(sheet)
d.text((14, 10), "改前", fill=(90, 92, 98), font=f)
d.text((14, 20 + h * Z + 22), "改后", fill=(90, 92, 98), font=f)
for r, (frames, y) in enumerate(((old, 32), (new, 20 + h * Z + 44))):
    for i, p in enumerate(picks):
        big = frames[p].resize((frames[p].width * Z, frames[p].height * Z), Image.NEAREST)
        x = 80 + i * (w * Z + 10)
        sheet.paste(big, (x, y), big)
        cy = y + h * Z / 2
        d.line([(x - 6, cy), (x + w * Z + 6, cy)], fill=(255, 0, 128), width=1)

out = os.path.join(WS, "_sw_before_after.png")
sheet.save(out)
print("saved", out, sheet.size)
