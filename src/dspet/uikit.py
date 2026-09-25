# -*- coding: utf-8 -*-
"""uikit —— 用 PIL 超采样渲染的精致小控件(替代 tkinter 手绘,消除锯齿)

为什么要这么干
    tkinter 的 Canvas 圆弧/矩形是**没有抗锯齿**的,拼出来的圆角、旋钮边缘发毛,
    描边还是死板的 1px 灰线 —— 这就是"粗糙"的根子。
    这里统一改成:**4 倍超采样绘制 → GaussianBlur 画柔和阴影 → LANCZOS 缩回**,
    于是得到真·丝滑边缘;动画只切换预渲染好的帧,几乎不吃 CPU。

适配
    所有尺寸都会乘以窗口所在屏幕的 DPI 缩放(`scale_of`),所以 100%/125%/150%
    缩放下物理大小一致、而且都是高清的(按缩放后的像素渲染,而不是拉伸)。
"""
import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

# ---------------- 调色板(macOS 浅色) ----------------
BG = "#ECEEF2"
CARD = "#FFFFFF"
TEXT = "#1D1D1F"
SUB = "#86868B"
FAINT = "#A5A7AE"
ACCENT = "#0A84FF"
ACCENT_HOVER = "#2B95FF"
GREEN = "#34C759"
DANGER = "#FF3B30"
TL_CLOSE = "#FF5F57"
TL_MIN = "#FEBC2E"
TL_ZOOM = "#28C840"
TRACK_OFF = "#DEDFE5"
LINE = "#E6E7EB"
BORDER = "#D8DAE0"
FIELD = "#FFFFFF"
SOFT = "#E9EBF0"
SOFT_HOVER = "#E3E5EA"

SS = 4          # 超采样倍数
PAD = 4         # 阴影留白(逻辑像素)

_cache = {}


# ---------------- 颜色 ----------------
def rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, k):
    a, b = rgb(c1), rgb(c2)
    return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def shade(c, k):
    return mix(c, "#ffffff", k) if k >= 0 else mix(c, "#000000", -k)


def scale_of(widget):
    try:
        return max(1.0, min(2.0, float(widget.winfo_fpixels("1i")) / 96.0))
    except Exception:
        return 1.0


def photo(img, key=None):
    if key is not None and key in _cache:
        return _cache[key]
    ph = ImageTk.PhotoImage(img)
    if key is not None:
        _cache[key] = ph
    return ph


# ---------------- 绘制层 ----------------
class Layer(object):
    """4x 超采样画布:坐标用逻辑像素,PAD 自动留出阴影空间"""

    def __init__(self, w, h, pad=PAD):
        self.w, self.h, self.pad = int(w), int(h), pad
        self.im = Image.new("RGBA", ((self.w + 2 * pad) * SS, (self.h + 2 * pad) * SS),
                            (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _b(self, box):
        return [(self.pad + box[0]) * SS, (self.pad + box[1]) * SS,
                (self.pad + box[2]) * SS, (self.pad + box[3]) * SS]

    def rrect(self, box, radius, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self._b(box), radius=radius * SS, fill=fill,
                                 outline=outline, width=max(1, int(width * SS)))

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._b(box), fill=fill, outline=outline,
                       width=max(1, int(width * SS)))

    def circle(self, cx, cy, r, fill=None, outline=None, width=0.6):
        """按圆心+半径画圆(上下左右完全对称,不会偏心)"""
        x, y, rr = (self.pad + cx) * SS, (self.pad + cy) * SS, r * SS
        self.d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=fill, outline=outline,
                       width=max(1, int(width * SS)))

    def shadow_circle(self, cx, cy, r, blur=1.0, alpha=0.28, dy=0.0, dx=0.0):
        lay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x, y, rr = (self.pad + cx + dx) * SS, (self.pad + cy + dy) * SS, r * SS
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(0, 0, 0, int(alpha * 255)))
        self.im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur * SS)))

    def shadow(self, box, radius, blur=2.0, dy=0.5, dx=0.0, alpha=0.30):
        lay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        b = self._b(box)
        d.rounded_rectangle([b[0] + dx * SS, b[1] + dy * SS, b[2] + dx * SS,
                             b[3] + dy * SS], radius=radius * SS,
                            fill=(0, 0, 0, int(alpha * 255)))
        self.im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur * SS)))

    def glow(self, box, radius, color, blur=1.6, alpha=0.5, grow=1.5):
        lay = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        b = self._b([box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow])
        d.rounded_rectangle(b, radius=(radius + grow) * SS,
                            outline=rgb(color) + (int(alpha * 255),),
                            width=max(1, int(1.8 * SS)))
        self.im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur * SS)))

    def gradient_rrect(self, box, radius, c_top, c_bottom, alpha=255):
        b = self._b(box)
        w, h = int(b[2] - b[0]), int(b[3] - b[1])
        if w < 2 or h < 2:
            return
        t, bo = rgb(c_top), rgb(c_bottom)
        face = Image.new("RGBA", (w, h))
        d = ImageDraw.Draw(face)
        for y in range(h):
            k = y / float(h - 1)
            col = tuple(int(round(t[i] + (bo[i] - t[i]) * k)) for i in range(3)) + (alpha,)
            d.line([(0, y), (w, y)], fill=col)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius * SS,
                                              fill=255)
        face.putalpha(Image.composite(face.getchannel("A"), Image.new("L", (w, h), 0), mask))
        self.im.alpha_composite(face, (int(b[0]), int(b[1])))

    def out(self):
        return self.im.resize((self.w + 2 * self.pad, self.h + 2 * self.pad),
                              Image.Resampling.LANCZOS)


def card_shadow(size, radius=13, blur=7.0, dy=3.0, alpha=0.16, bg=BG):
    """卡片下面的柔和投影(与背景合成成不透明图,可直接当 Label 背景)"""
    w, h = int(size[0]), int(size[1])
    if w < 4 or h < 4:
        return None
    key = ("card_sh", w, h, radius, blur, dy, alpha, bg)
    if key in _cache:
        return _cache[key]
    pad = int(blur * 2 + abs(dy) + 2)
    out = Image.new("RGB", (w + 2 * pad, h + 2 * pad), rgb(bg))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (pad, pad + dy, pad + w, pad + h + dy), radius=radius,
        fill=(0, 0, 0, int(alpha * 255)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.paste(sh, (0, 0), sh)
    _cache[key] = out
    return out


def card_shadow_strip(width, thickness=9, alpha0=0.13, bg=BG):
    """卡片正下方的一条柔和投影(顶部最深、向下渐隐),避免整圈阴影带来的白角问题"""
    w = int(width)
    if w < 8:
        return None
    key = ("strip", w, thickness, alpha0, bg)
    if key in _cache:
        return _cache[key]
    lay = Image.new("L", (w, thickness), 0)
    d = ImageDraw.Draw(lay)
    for y in range(thickness):
        a = int(255 * alpha0 * (1 - y / float(thickness)) ** 1.25)
        d.line([(0, y), (w, y)], fill=a)
    lay = lay.filter(ImageFilter.GaussianBlur(1.6))
    out = Image.new("RGB", (w, thickness), rgb(bg))
    out.paste(Image.new("RGB", (w, thickness), (0, 0, 0)), (0, 0), lay)
    _cache[key] = out
    return out


def hairline(parent, color=LINE):
    return tk.Frame(parent, height=1, bd=0, highlightthickness=0, bg=color)


# ---------------- 开关(左右滑块) ----------------
SWITCH_W, SWITCH_H, KNOB_INSET = 42, 24, 2


def switch_frames(on=GREEN, off=TRACK_OFF, w=SWITCH_W, h=SWITCH_H, inset=KNOB_INSET,
                  sc=1.0):
    """预渲染"每个像素位置"一帧(off→on),返回 (frames, 画布宽, 画布高)"""
    W = max(10, int(round(w * sc)))
    H = max(10, int(round(h * sc)))
    ins = int(round(inset * sc))
    key = ("sw", W, H, on, off, ins)
    if key in _cache:
        return _cache[key]
    dk_ = H - 2 * ins - 1      # 旋钮直径(比轨道内高再小 1px,留出描边的呼吸位)
    travel = max(1, W - 2 * ins - dk_)
    rr = (H - 1) / 2.0         # 轨道的"胶囊"半径
    cy = H / 2.0               # 垂直中线(旋钮和轨道共用,保证同心)
    kr = dk_ / 2.0 - 0.3       # 旋钮半径
    frames = []
    for i in range(travel + 1):
        t = i / float(travel)
        track = mix(off, on, t)
        L = Layer(W, H)
        # 轨道:灰描边(0.5px,很淡)让"凹槽"有轮廓
        L.rrect((0.4, 0.4, W - 0.4, H - 0.4), rr, fill=rgb(track) + (255,),
                outline=(0, 0, 0, 68), width=0.6)
        # 凹槽:只留一丝内阴影(参考 iOS:立体感主要靠描边,不靠阴影)
        L.shadow((1.0, 1.0, W - 1.0, H * 0.34), rr, blur=1.0, dy=0.2, alpha=0.05)
        L.rrect((1.6, H - 1.6, W - 1.6, H - 0.9), rr, fill=(255, 255, 255, 16))
        kx = ins + int(round(t * travel))
        cx = kx + dk_ / 2.0
        # 旋钮:轻投影(往下 0.35px,别压太重,免得看着"陷进去")+ 灰描边白块
        L.shadow_circle(cx, cy + 0.4, kr, blur=0.9, alpha=0.26)
        L.circle(cx, cy, kr, fill=(255, 255, 255, 255), outline=(0, 0, 0, 58),
                 width=0.7)
        frames.append(L.out())
    _cache[key] = (frames, W + 2 * PAD, H + 2 * PAD)
    return _cache[key]


def switch_photos(on=GREEN, off=TRACK_OFF, w=SWITCH_W, h=SWITCH_H, sc=1.0):
    frames, wp, hp = switch_frames(on, off, w, h, sc=sc)
    pkey = ("swp", wp, hp, on, off)
    if pkey not in _cache:
        _cache[pkey] = [ImageTk.PhotoImage(f) for f in frames]
    return _cache[pkey], wp, hp


class Switch(tk.Canvas):
    """macOS 风左右滑块开关 —— 帧动画,边缘丝滑"""

    def __init__(self, master, variable, bg=CARD, on=GREEN, off=TRACK_OFF,
                 command=None, sc=None):
        sc = sc or scale_of(master)
        frames, wp, hp = switch_photos(on, off, sc=sc)
        super().__init__(master, width=wp, height=hp, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._frames, self._n = frames, len(frames)
        self.var = variable
        self.command = command
        self._t = 1.0 if variable.get() else 0.0
        self._target = self._start = self._t
        self._anim = False
        self._last = self._idx()
        self._id = self.create_image(0, 0, anchor="nw", image=frames[self._last])
        self.bind("<Button-1>", self.toggle)
        try:
            self.var.trace_add("write", lambda *a: self._sync())
        except Exception:
            pass

    def _idx(self):
        return max(0, min(self._n - 1, int(round(self._t * (self._n - 1)))))

    def _paint(self):
        i = self._idx()
        if i != self._last:
            self.itemconfig(self._id, image=self._frames[i])
            self._last = i

    def toggle(self, _e=None):
        self.var.set(not bool(self.var.get()))
        if self.command:
            try:
                self.command(bool(self.var.get()))
            except Exception:
                pass

    def _sync(self):
        want = 1.0 if self.var.get() else 0.0
        if abs(want - self._target) < 1e-6:
            return
        self._start, self._target = self._t, want
        if not self._anim:
            self._anim = True
            self._animate(0, 11)

    def _animate(self, i, total):
        k = min(1.0, i / float(total))
        self._t = self._start + (self._target - self._start) * (0.5 - 0.5 * math.cos(math.pi * k))
        self._paint()
        if k < 1.0:
            self.after(11, lambda: self._animate(i + 1, total))
        else:
            self._t = self._target
            self._paint()
            self._anim = False
            self._sync()


# ---------------- 滑动条 ----------------
SLIDER_H = 20
TRACK_TH = 4


def slider_frame(width, t, accent=ACCENT, track=TRACK_OFF, sc=1.0, h=SLIDER_H):
    W = max(24, int(round(width * sc)))
    H = int(round(h * sc))
    key = ("sl", W, H, accent, track, round(t, 4))
    if key in _cache:
        return _cache[key]
    th = max(2, int(round(TRACK_TH * sc)))
    ty = (H - th) / 2.0
    K = H
    kx = int(round(t * (W - K)))
    L = Layer(W, H)
    L.rrect((0, ty, W, ty + th), th / 2.0, fill=rgb(track) + (255,),
            outline=(0, 0, 0, 16), width=0.5)
    fill_w = max(float(th), kx + K / 2.0)
    L.rrect((0, ty, fill_w, ty + th), th / 2.0, fill=rgb(accent) + (255,))
    L.shadow((kx, 0, kx + K, K), K / 2.0, blur=1.6, dy=1.0, alpha=0.34)
    L.ellipse((kx, 0, kx + K, K), fill=(255, 255, 255, 255), outline=(0, 0, 0, 28),
              width=0.6)
    out = L.out()
    _cache[key] = out
    return out


class Slider(tk.Canvas):
    def __init__(self, master, from_, to, value, bg=CARD, command=None, steps=None,
                 width=220, height=SLIDER_H, sc=None):
        sc = sc or scale_of(master)
        self.sc, self._cw, self._ch = sc, width, height
        self.from_, self.to = float(from_), float(to)
        self.steps = int(steps) if steps else 0
        self.command = command
        super().__init__(master, width=int(width * sc) + 2 * PAD,
                         height=int(height * sc) + 2 * PAD, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._t = self._norm(value)
        self._id = self.create_image(0, 0, anchor="nw", image=self._render())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Configure>", self._resize)

    def _norm(self, v):
        span = (self.to - self.from_) or 1.0
        return max(0.0, min(1.0, (float(v) - self.from_) / span))

    @property
    def value(self):
        span = (self.to - self.from_) or 1.0
        v = self.from_ + self._t * span
        if self.steps > 1:
            v = round((v - self.from_) / span * (self.steps - 1)) * span / (self.steps - 1) + self.from_
        return int(round(v))

    def _render(self):
        return photo(slider_frame(self._cw, self._t, sc=self.sc, h=self._ch),
                     key=("slp", self._cw, self._ch, self.sc, round(self._t, 3)))

    def set_value(self, v, notify=False):
        self._t = self._norm(v)
        self.itemconfig(self._id, image=self._render())
        if notify and self.command:
            self.command(self.value)

    def _set_from_x(self, x):
        w = int(self._cw * self.sc)
        K = int(self._ch * self.sc)
        self._t = max(0.0, min(1.0, (x - PAD - K / 2.0) / max(1.0, w - K)))
        self.itemconfig(self._id, image=self._render())
        if self.command:
            self.command(self.value)

    def _press(self, e):
        self._set_from_x(e.x)

    def _drag(self, e):
        self._set_from_x(e.x)

    def _resize(self, e):
        w = int((e.width - 2 * PAD) / self.sc)
        if abs(w - self._cw) > 1:
            self._cw = w
            self.itemconfig(self._id, image=self._render())


# ---------------- 分段控件 ----------------
def seg_image(width, height, idx, n, sc=1.0, radius=9):
    W, H = int(round(width * sc)), int(round(height * sc))
    rad = int(round(radius * sc))
    inner = int(round(3 * sc))
    key = ("seg", W, H, idx, n, radius)
    if key in _cache:
        return _cache[key]
    cw = (W - 2 * inner) / float(max(1, n))
    L = Layer(W, H)
    L.rrect((0, 0, W - 1, H - 1), rad, fill=rgb("#E7E8ED") + (255,),
            outline=None)
    px = inner + cw * idx
    py = inner
    L.shadow((px, py, px + cw, py + H - 2 * inner), max(6, rad - 2), blur=2.6, dy=1.1,
             alpha=0.30)
    L.rrect((px, py, px + cw, py + H - 2 * inner), max(6, rad - 2),
            fill=(255, 255, 255, 255), outline=(0, 0, 0, 10), width=0.5)
    out = L.out()
    _cache[key] = (out, cw, inner)
    return _cache[key]


class Segmented(tk.Canvas):
    def __init__(self, master, values, value, bg=CARD, command=None, width=250,
                 height=30, font=None, sc=None):
        sc = sc or scale_of(master)
        self.sc, self.values, self.command = sc, list(values), command
        self.font = font
        self.wreq, self.hreq = width, height
        super().__init__(master, width=int(width * sc) + 2 * PAD,
                         height=int(height * sc) + 2 * PAD, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self.var = tk.StringVar(value=value if value in self.values else self.values[0])
        self._ph = None
        self._cw, self._inner = 0, 0
        self._id = self.create_image(0, 0, anchor="nw")
        self._texts = []
        self._repaint()
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._resize)

    def _build_texts(self):
        for t in self._texts:
            self.delete(t)
        self._texts = []
        n = len(self.values)
        for i, v in enumerate(self.values):
            x = PAD + self._inner * self.sc + self._cw * (i + 0.5)
            y = int(self.cget("height")) / 2.0
            col = TEXT if v == self.var.get() else SUB
            self._texts.append(self.create_text(x, y, text=v, fill=col, font=self.font,
                                                anchor="center"))

    def _repaint(self):
        idx = self.values.index(self.var.get())
        img, cw, inner = seg_image(self.wreq, self.hreq, idx, len(self.values), self.sc)
        self._cw, self._inner = cw, inner
        # ⚠️ 必须留引用,否则 PhotoImage 被回收 → 控件变空白
        self._ph = photo(img, key=("segp", self.wreq, self.hreq, idx,
                                   len(self.values), self.sc))
        self.itemconfig(self._id, image=self._ph)
        self._build_texts()

    def select(self, value, notify=True):
        if value not in self.values:
            value = self.values[0]
        self.var.set(value)
        self._repaint()
        if notify and self.command:
            self.command(value)

    def _click(self, e):
        x = (e.x - PAD) / float(self.sc) - self._inner
        idx = int(max(0, min(len(self.values) - 1, x // max(1.0, self._cw))))
        self.select(self.values[idx])

    def _resize(self, e):
        w = int((e.width - 2 * PAD) / self.sc)
        if abs(w - self.wreq) > 1:
            self.wreq = w
            self._repaint()


# ---------------- 按钮 ----------------
def button_image(width, height, kind="primary", state="normal", sc=1.0, radius=9):
    W, H = int(round(width * sc)), int(round(height * sc))
    rad = int(round(radius * sc))
    key = ("btn", W, H, kind, state, radius)
    if key in _cache:
        return _cache[key]
    base = {"primary": ACCENT, "soft": SOFT, "ghost": "#FFFFFF", "danger": DANGER,
            "success": GREEN}[kind]
    if state == "hover":
        base = {"primary": ACCENT_HOVER, "soft": SOFT_HOVER, "ghost": "#F4F5F8",
                "danger": shade(DANGER, .08), "success": shade(GREEN, .08)}[kind]
    elif state == "press":
        base = shade(base, -0.07)
    L = Layer(W, H)
    if kind in ("primary", "danger", "success"):
        L.shadow((0, 0.5, W, H), rad, blur=3.2, dy=1.6, alpha=0.24)
    if kind == "ghost":
        L.rrect((0, 0, W - 1, H - 1), rad, fill=(255, 255, 255, 255),
                outline=rgb(BORDER) + (255,), width=1)
    else:
        L.gradient_rrect((0, 0, W - 1, H - 1), rad, shade(base, 0.10), shade(base, -0.02))
        if kind == "soft":
            L.rrect((0.5, 0.5, W - 1.5, H - 1.5), rad - 0.5, fill=None,
                    outline=(0, 0, 0, 18), width=0.5)
    if state == "normal" and kind != "ghost":
        L.rrect((0.5, 0.5, W - 1.5, H - 1.5), rad - 0.5, fill=None,
                outline=(255, 255, 255, 46), width=0.5)
    out = L.out()
    _cache[key] = out
    return out


class Button(tk.Canvas):
    def __init__(self, master, text, command=None, bg=CARD, kind="primary", width=100,
                 height=34, font=None, text_color=None, sc=None, radius=9):
        sc = sc or scale_of(master)
        self.sc, self.kind, self.command, self.font = sc, kind, command, font
        self._cw, self._ch, self.radius = width, height, radius
        super().__init__(master, width=int(width * sc) + 2 * PAD,
                         height=int(height * sc) + 2 * PAD, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._imgs = {s: photo(button_image(width, height, kind, s, sc, radius), None)
                      for s in ("normal", "hover", "press")}
        self._cur = "normal"
        self._bgid = self.create_image(0, 0, anchor="nw", image=self._imgs["normal"])
        self._tcol = text_color or ("#FFFFFF" if kind in ("primary", "danger") else TEXT)
        self._tid = self.create_text(PAD + int(width * sc) / 2.0,
                                     PAD + int(height * sc) / 2.0, text=text,
                                     fill=self._tcol, font=self.font)
        self.bind("<Enter>", lambda e: self._state("hover"))
        self.bind("<Leave>", lambda e: self._state("normal"))
        self.bind("<Button-1>", lambda e: self._state("press"))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", self._resize)

    def _state(self, s):
        self._cur = s
        self.itemconfig(self._bgid, image=self._imgs[s])

    def _release(self, e):
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self._state("hover" if inside else "normal")
        if inside and self.command:
            try:
                self.command()
            except Exception:
                pass

    def set_text(self, s):
        self.itemconfig(self._tid, text=s)

    def set_kind(self, kind, text_color=None):
        self.kind = kind
        if text_color:
            self._tcol = text_color
        self.itemconfig(self._tid, fill=self._tcol)
        self._imgs = {s: photo(button_image(self._cw, self._ch, kind, s, self.sc,
                                           self.radius), None)
                      for s in ("normal", "hover", "press")}
        self.itemconfig(self._bgid, image=self._imgs[self._cur])

    def _resize(self, e):
        w = int((e.width - 2 * PAD) / self.sc)
        if abs(w - self._cw) > 1:
            self._cw = w
            self._imgs = {s: photo(button_image(w, self._ch, self.kind, s, self.sc,
                                               self.radius), None)
                          for s in ("normal", "hover", "press")}
            self.itemconfig(self._bgid, image=self._imgs[self._cur])
            self.coords(self._tid, e.width / 2.0, e.height / 2.0)


# ---------------- 输入框 ----------------
ENTRY_PAD = 4


def entry_image(width, height, sc=1.0, focused=False, radius=8):
    W, H = int(round(width * sc)), int(round(height * sc))
    rad = int(round(radius * sc))
    key = ("ent", W, H, focused, radius)
    if key in _cache:
        return _cache[key]
    L = Layer(W, H, pad=ENTRY_PAD)
    if focused:
        L.glow((0, 0, W - 1, H - 1), rad, ACCENT, blur=1.6, alpha=0.55, grow=1.4)
        L.rrect((0, 0, W - 1, H - 1), rad, fill=rgb(FIELD) + (255,),
                outline=rgb(ACCENT) + (255,), width=1.2)
    else:
        L.rrect((0, 0, W - 1, H - 1), rad, fill=rgb(FIELD) + (255,),
                outline=rgb(BORDER) + (255,), width=1)
    out = L.out()
    _cache[key] = out
    return out


class Entry(tk.Canvas):
    def __init__(self, master, textvariable, bg=CARD, width=200, height=34, font=None,
                 show="", sc=None, radius=8):
        sc = sc or scale_of(master)
        self.sc, self._cw, self._ch, self.radius = sc, width, height, radius
        super().__init__(master, width=int(width * sc) + 2 * ENTRY_PAD,
                         height=int(height * sc) + 2 * ENTRY_PAD, bg=bg, bd=0,
                         highlightthickness=0, cursor="xterm")
        self._imgs = {False: photo(entry_image(width, height, sc, False, radius)),
                      True: photo(entry_image(width, height, sc, True, radius))}
        self._bgid = self.create_image(0, 0, anchor="nw", image=self._imgs[False])
        self.var = textvariable
        self.entry = tk.Entry(self, textvariable=textvariable, bd=0, relief="flat",
                              highlightthickness=0, bg=FIELD, fg=TEXT, show=show,
                              insertbackground=ACCENT, font=font)
        self._win = self.create_window(ENTRY_PAD + int(7 * sc),
                                       ENTRY_PAD + int(height * sc) / 2.0, anchor="w",
                                       window=self.entry,
                                       width=int(width * sc) - int(14 * sc),
                                       height=int(height * sc) - int(8 * sc))
        self.entry.bind("<FocusIn>", lambda e: self.itemconfig(self._bgid, image=self._imgs[True]))
        self.entry.bind("<FocusOut>", lambda e: self.itemconfig(self._bgid, image=self._imgs[False]))
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.bind("<Configure>", self._resize)

    def set_show(self, ch):
        self.entry.configure(show=ch)

    def get_text(self):
        return self.var.get()

    def set_text(self, s):
        self.var.set(s)

    def _resize(self, e):
        w = int((e.width - 2 * ENTRY_PAD) / self.sc)
        if abs(w - self._cw) > 1:
            self._cw = w
            self._imgs = {False: photo(entry_image(w, self._ch, self.sc, False, self.radius)),
                          True: photo(entry_image(w, self._ch, self.sc, True, self.radius))}
            self.itemconfig(self._bgid, image=self._imgs[False])
            self.coords(self._win, ENTRY_PAD + int(7 * self.sc), e.height / 2.0)
            self.itemconfig(self._win, width=int(w * self.sc) - int(14 * self.sc))


# ---------------- 交通灯小圆点 ----------------
def dot_image(d, color, sc=1.0):
    D = int(round(d * sc))
    key = ("dot", D, color)
    if key in _cache:
        return _cache[key]
    L = Layer(D, D, pad=1)
    L.ellipse((0, 0, D - 1, D - 1), fill=rgb(color) + (255,), outline=(0, 0, 0, 46),
              width=0.5)
    out = L.out()
    _cache[key] = out
    return out


class Dot(tk.Canvas):
    def __init__(self, master, d=13, color=TL_CLOSE, bg=CARD, command=None, sc=None):
        sc = sc or scale_of(master)
        self.command = command
        super().__init__(master, width=int(d * sc) + 2, height=int(d * sc) + 2, bg=bg,
                         bd=0, highlightthickness=0, cursor="hand2")
        self._id = self.create_image(0, 0, anchor="nw",
                                     image=photo(dot_image(d, color, sc),
                                                 key=("dotp", int(round(d * sc)), color)))
        self.bind("<Button-1>", lambda e: command() if command else None)
        self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))
