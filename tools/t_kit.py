# -*- coding: utf-8 -*-
"""自查:把 uikit 渲染出来的控件拼成一张大图,肉眼验收"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from PIL import Image, ImageDraw, ImageFont       # noqa: E402

from dspet import uikit as U                      # noqa: E402

WS = os.environ.get("WS", r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace")
BG = (236, 238, 242, 255)
Z = 2                                              # 放大倍数(看细节)
SC = 1.0

sheet = Image.new("RGBA", (900, 560), BG)
dr = ImageDraw.Draw(sheet)
try:
    f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
except Exception:
    f = None


def label(x, y, s):
    dr.text((x, y), s, fill=(120, 122, 128, 255), font=f)


def blit(im, x, y):
    sheet.alpha_composite(im.resize((im.width * Z, im.height * Z), Image.NEAREST), (x, y))
    return im.height * Z


# 1) 开关全部帧(10 个一行)
label(10, 6, "开关 42x24 —— 全部 19 个位置(off → on)")
frames, w, h = U.switch_frames(sc=SC)
y = 26
for r in range(2):
    x = 10
    for fr in frames[r * 10:(r + 1) * 10]:
        blit(fr, x, y)
        x += w * Z
    y += h * Z + 2

# 2) 滑动条
label(10, y + 6, "滑动条(0 / 0.35 / 1.0)")
y += 24
for t in (0.0, 0.35, 1.0):
    y += blit(U.slider_frame(240, t, sc=SC), 10, y) + 2

# 3) 分段控件
label(10, y + 6, "分段控件(选中 0 / 1)")
y += 24
for idx in (0, 1):
    im, cw, inner = U.seg_image(200, 30, idx, 2, SC)
    y += blit(im, 10, y) + 3

# 4) 按钮 / 输入框 / 交通灯 放右边
x2 = 520
label(x2, 6, "按钮 normal / hover / press")
y2 = 26
for kind in ("primary", "soft", "ghost"):
    label(x2, y2 + 4, kind)
    for state in ("normal", "hover", "press"):
        im = U.button_image(96, 34, kind, state, SC)
        sheet.alpha_composite(im.resize((im.width * Z, im.height * Z), Image.NEAREST),
                              (x2 + 52 + ("normal", "hover", "press").index(state) * 100, y2))
    y2 += 34 * Z + 6

y2 += 10
label(x2, y2, "输入框 常态 / 聚焦")
y2 += 20
for focus in (False, True):
    im = U.entry_image(240, 34, SC, focus)
    y2 += blit(im, x2, y2) + 4

y2 += 10
label(x2, y2, "交通灯")
y2 += 20
x = x2
for c in (U.TL_CLOSE, U.TL_MIN, U.TL_ZOOM):
    im = U.dot_image(13, c, SC)
    blit(im, x, y2)
    x += 40

# 5) 卡片投影
y += 30
label(10, y, "卡片投影")
y += 20
sh = U.card_shadow((300, 60), radius=13, bg="#ECEEF2")
pad = (sh.width - 300) // 2
sheet.alpha_composite(sh.convert("RGBA").resize((sh.width * Z, sh.height * Z),
                                                Image.LANCZOS), (10, y))
card = Image.new("RGBA", (300, 60), (255, 255, 255, 255))
mask = Image.new("L", (300, 60), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, 299, 59), radius=13, fill=255)
card.putalpha(mask)
sheet.alpha_composite(card.resize((300 * Z, 60 * Z), Image.LANCZOS), (10 + pad * Z, y + pad * Z))

out = os.path.join(WS, "_kit.png")
sheet.convert("RGB").save(out)
print("saved", out, sheet.size)
