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
SOFT_HOVER = "#DDE0E6"   # 悬停底色:比 BG(#ECEEF2) 明显深一点,否则看不出高亮

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


def card_shadow_strip(width, thickness=9, alpha0=0.13, bg=BG, radius=12):
    """卡片正下方的一条柔和投影(顶部最深、向下渐隐)。
    两端必须跟着卡片圆角收窄 —— 否则卡片是圆角、阴影两端是直角,
    底下会露出一条直边(实测就是"阴影还是直的")。
    做法:用竖向渐变 × 圆角遮罩(顶端按 radius 收圆),再整体高斯模糊。"""
    w = int(width)
    if w < 8:
        return None
    key = ("strip", w, thickness, alpha0, bg, radius)
    if key in _cache:
        return _cache[key]
    lay = Image.new("L", (w, thickness), 0)
    d = ImageDraw.Draw(lay)
    for y in range(thickness):
        a = int(255 * alpha0 * (1 - y / float(thickness)) ** 1.25)
        d.line([(0, y), (w, y)], fill=a)
    # 圆角遮罩:两端按卡片圆角"向内收",左右对称。
    # 做法:画一个满宽、上边在 y=0、下边在 y=thickness+2r 的圆角矩形,
    # 半径 r,圆角只切到顶部两角 → 顶行两端变淡、中部不变。
    r = max(4, int(radius))
    mask = Image.new("L", (w, thickness), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, w - 1, thickness + 2 * r), radius=r, fill=255)
    lay = Image.composite(lay, Image.new("L", (w, thickness), 0), mask)
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
        # ⚠️ value 可能是 StringVar(调用方要双向同步)也可能是普通字符串。
        #    以前一律当字符串比较 → 传 var 时判断恒为假 → 内部新建 var 且默认选中
        #    第一项 → 「界面大小」永远高亮"小"、「喂文件」永远高亮"回收站"(真 bug)。
        if hasattr(value, "get") and hasattr(value, "set"):
            self.var = value
            try:
                if value.get() not in self.values:
                    value.set(self.values[0])
            except Exception:
                self.var = tk.StringVar(value=self.values[0])
        else:
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


# ---------------- 导航图标(SVG 路径 → 高分辨率位图,非汉字) ----------------
NAV_ICON_PATHS = {
    # 账号:人像(头 + 肩,用圆弧开口)
    "account": [
        ("circle", 12, 8.4, 3.15),
        ("arc", 5.4, 19.4, 18.6, 19.4, 12, 15.0),
    ],
    # 外观与行为:眼睛(椭圆睁开 + 瞳孔)
    "behaviour": [
        ("ellipse", 2.6, 8.4, 21.4, 15.6),
        ("circle", 12, 12.0, 2.25),
    ],
    # 细节:三条滑杆带旋钮(调节)
    "details": [
        ("line", 3.2, 6.6, 20.8, 6.6),
        ("circle", 7.6, 6.6, 2.15),
        ("line", 3.2, 12.0, 20.8, 12.0),
        ("circle", 16.4, 12.0, 2.15),
        ("line", 3.2, 17.4, 20.8, 17.4),
        ("circle", 10.4, 17.4, 2.15),
    ],
    # 工具箱:扳手(开口螺环 + 斜柄)
    "toolbox": [
        ("circle", 7.6, 7.6, 3.7),
        ("circle", 9.2, 6.2, 2.5),
        ("line", 9.6, 10.2, 18.4, 19.0),
    ],
    # 卸载:垃圾桶(盖 + 躯干 + 两竖纹)
    "uninstall": [
        ("line", 4.2, 6.0, 19.8, 6.0),
        ("line", 9.4, 3.2, 14.6, 3.2),
        ("rrect", 5.6, 8.2, 18.4, 20.6),
        ("line", 9.4, 11.0, 9.4, 17.6),
        ("line", 14.6, 11.0, 14.6, 17.6),
    ],
}


def _icon_image(name, size, color, width, sc=1.0):
    """把 NAV_ICON_PATHS 里的 SVG 路径渲染成透明底 RGBA 位图(4x 超采样,丝滑)"""
    W = max(4, int(round(size * sc)))
    key = ("navicon", name, W, color, width)
    if key in _cache:
        return _cache[key]
    S = W * SS
    k = S / 24.0
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = rgb(color) + (255,)
    lw = max(1, int(round(width * k)))
    for prim in NAV_ICON_PATHS.get(name, []):
        t = prim[0]
        if t == "line":
            d.line([(prim[1] * k, prim[2] * k), (prim[3] * k, prim[4] * k)],
                   fill=col, width=lw)
        elif t == "circle":
            cx, cy, r = prim[1] * k, prim[2] * k, prim[3] * k
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        elif t == "ellipse":
            d.ellipse([prim[1] * k, prim[2] * k, prim[3] * k, prim[4] * k],
                      outline=col, width=lw)
        elif t == "rrect":
            d.rounded_rectangle([prim[1] * k, prim[2] * k, prim[3] * k, prim[4] * k],
                                radius=1.6 * k, outline=col, width=lw)
        elif t == "arc":
            d.arc([prim[1] * k, prim[2] * k, prim[3] * k, prim[4] * k],
                  prim[5], prim[6], fill=col, width=lw)
    out = img.resize((W, W), Image.Resampling.LANCZOS)
    _cache[key] = out
    return out


def icon_image(name, size, color, width=1.9, sc=1.0):
    W = max(4, int(round(size * sc)))
    key = ("navphoto", name, W, color, width)
    if key in _cache:
        return _cache[key]
    img = _icon_image(name, size, color, width, sc)
    ph = ImageTk.PhotoImage(img)
    _cache[key] = ph
    return ph


# ---------------- 导航按钮(PCL 风格左侧栏目) ----------------
def navbutton_image(width, height, state="normal", sc=1.0, radius=8, bar=False,
                    alpha=1.0):
    """state: normal | hover | active

    PCL 风：**常态不画底色**(与面板融为一体,没有白卡片/硬边/坏块),
    悬停给一层极淡的灰,选中给实心强调色。alpha 供展开/收起时淡入淡出。"""
    W, H = int(round(width * sc)), int(round(height * sc))
    rad = int(round(radius * sc))
    a01 = max(0.0, min(1.0, float(alpha)))
    key = ("nav", W, H, state, radius, round(a01, 3))
    if key in _cache:
        return _cache[key]
    L = Layer(W, H)
    if state == "active":
        L.gradient_rrect((0, 0, W - 1, H - 1), rad, shade(ACCENT, 0.10),
                         shade(ACCENT, -0.02))
    elif state == "hover":
        # 悬停:极淡灰底,无描边
        L.rrect((0, 0, W - 1, H - 1), rad, fill=rgb(SOFT_HOVER) + (255,))
    else:
        # 常态:完全透明(不画任何底) —— 这才是 PCL 的“平”
        pass
    out = L.out()
    if a01 < 0.999:
        out = out.copy()
        out.putalpha(out.getchannel("A").point(lambda v: int(v * a01)))
    _cache[key] = out
    return out


class NavButton(tk.Canvas):
    """左侧导航栏按钮。两种形态:
      * 固定态(icon-only):只画图标,方形小钮,不随悬停变宽(导航栏固定不动)
      * 悬停态:光标移上时向左展开成"条",显示图标 + 文字
    选中态为实心强调色(图标/文字转白)。
    展开/收起是动画:由栏驱动 bar.set_wide(t),t∈[0,1] 逐帧插值,
    图标左移、文字淡入(用 fill 颜色混色模拟透明度)。
    """

    def __init__(self, master, text, command=None, bg=BG, width=132, height=38,
                 font=None, sc=None, radius=9, icon=None, compact_w=44,
                 icon_size=20, expanding=True):
        sc = sc or scale_of(master)
        self.sc, self.command, self.font = sc, command, font
        self._cw, self._ch, self.radius = width, height, radius
        self._compact_w = compact_w
        self._expanding = expanding
        self._icon = icon
        self._icon_size = icon_size
        self._active = False
        self._hover = False
        self._text = text
        super().__init__(master, width=int(width * sc) + 2 * PAD,
                         height=int(height * sc) + 2 * PAD, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._imgs = {s: photo(navbutton_image(width, height, s, sc, radius,
                                               alpha=0.0 if s == "normal" else 1.0), None)
                      for s in ("normal", "hover", "active")}
        self._cur = "normal"
        # 图标(非汉字):固定态水平居中,展开态靠左
        self._icid = None
        self._ic_ph = None
        if icon:
            cw = int(compact_w * sc) / 2.0 + PAD
            self._icid = self.create_image(cw, PAD + int(height * sc) / 2.0,
                                           anchor="center")
        # 图标位图缓存(构造时生成一次;之后每帧只 itemconfig)
        self._build_icon_cache()
        if icon:
            self._ic_ph = self._icon_cache.get("normal")
            self.itemconfig(self._icid, image=self._ic_ph)
        self._tid = self.create_text(PAD + int(width * sc) / 2.0,
                                     PAD + int(height * sc) / 2.0, text=text,
                                     fill=TEXT, font=self.font, anchor="center")
        # 活动/悬停底图:预渲染帧表,动画时只查表(见 _bg_frames_build)
        from PIL import Image, ImageTk
        self._bg_tk = ImageTk.PhotoImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))
        self._bg_cap = None
        self._bg_frames = {}
        self._bgid = self.create_image(PAD, PAD, anchor="nw", image=self._bg_tk)
        self._bg_shown = 0.0
        self._bg_frames_build()
        self._t = 0.0        # 当前动画进度 0=收起 1=展开
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._release)

    def _icon_photo(self, col):
        return icon_image(self._icon, self._icon_size, col, 1.9, self.sc)

    def _icon_color(self):
        return "#FFFFFF" if self._active else (ACCENT if self._hover else SUB)

    def _build_icon_cache(self):
        """预生成三种状态的图标位图缓存。
        每帧都现场调 icon_image 会拖慢动画(每帧几十 ms、只够 2 帧),
        所以缓存后每帧只做 itemconfig。"""
        if not self._icon:
            self._icon_cache = {}
            return
        self._icon_cache = {
            "normal": self._icon_photo(SUB),
            "hover": self._icon_photo(ACCENT),
            "active": self._icon_photo("#FFFFFF"),
        }

    def _repaint_icon(self):
        if not self._icon:
            return
        s = "active" if self._active else ("hover" if self._hover else "normal")
        ph = self._icon_cache.get(s)
        if ph is not None and self._ic_ph is not ph:
            self._ic_ph = ph
            self.itemconfig(self._icid, image=ph)

    def set_wide(self, t):
        """栏动画逐帧回调:t∈[0,1],0=收起 1=展开。
        图标位置、文字淡入都按 t 插值——比布尔开关流畅得多。"""
        try:
            t = max(0.0, min(1.0, float(t)))
        except Exception:
            t = 1.0 if t else 0.0
        self._t = t
        self._reflect()

    def _bg_frames_build(self):
        """预渲染底图的所有帧(状态 × 宽度档 × 透明度档)。
        动画时只做 dict 查表 + itemconfig —— 绝不在帧里做 PIL 裁剪/重采样,
        那是之前每两三帧卡 80~90ms、动画只有 5~6 帧的根因。"""
        from PIL import Image
        self._bg_frames = {}
        W = int(self._cw * self.sc)
        NA, NW = 8, 14   # 透明度 8 档、宽度 14 档
        for s in ("active", "hover"):
            full = navbutton_image(self._cw, self._ch, s, self.sc, self.radius)
            fh = full.height
            for iw in range(NW + 1):
                t = iw / float(NW)
                w = int(round(W * (0.28 + 0.72 * t)))
                w = max(2, min(W, w))
                if w >= W:
                    # 满宽:直接用完整圆角图,不能裁 —— 裁会切平右端
                    cropped = full
                else:
                    # 窄于满宽:盖一层圆角遮罩,让右端跟着圆角收圆(而非直角切口)
                    cropped = full.crop((0, 0, w + 2 * PAD, fh)).copy()
                    m = Image.new("L", cropped.size, 0)
                    ImageDraw.Draw(m).rounded_rectangle(
                        (0, 0, cropped.size[0] - 1, cropped.size[1] - 1),
                        radius=max(2, int(self.radius * self.sc) + PAD), fill=255)
                    cropped.putalpha(
                        cropped.getchannel("A").point(lambda v: v).convert("L"))
                    a0 = cropped.getchannel("A")
                    a1 = Image.composite(a0, Image.new("L", cropped.size, 0), m)
                    cropped.putalpha(a1)
                for ia in range(NA + 1):
                    a = ia / float(NA)
                    if a <= 0.001:
                        continue
                    im = cropped.copy()
                    im.putalpha(im.getchannel("A").point(
                        lambda v, aa=a: int(v * aa)))
                    key = (s, iw, ia)
                    self._bg_frames[key] = photo(im, None)

    def _paint_bg(self, s, a, t):
        """画活动/悬停底图:宽度随 t 伸展、透明度随 a 淡入。
        只查预渲染表,不在帧里做图像处理(否则帧率崩)。"""
        if s == "normal" or a <= 0.001:
            # ⚠️ 必须连 _bg_cap 一起清掉!
            #    否则:悬停过→离开(隐藏)→再悬停时算出的 key 与残留的
            #    _bg_cap 相同 → 命中缓存直接 return → 底图永远不再显示。
            #    (东家反馈的"高亮还是有 bug"就是这个:第一次能亮,移开再回来就不亮)
            self._bg_cap = None
            if self._bg_shown != 0.0:
                self._bg_shown = 0.0
                self.itemconfig(self._bgid, state="hidden")
            return
        NA, NW = 8, 14
        iw = int(round(max(0.0, min(1.0, t)) * NW))
        ia = int(round(max(0.0, min(1.0, a)) * NA))
        key = (s, iw, ia)
        if getattr(self, "_bg_cap", None) == key:
            return
        ph = self._bg_frames.get(key)
        if ph is None:
            return
        self._bg_cap = key
        self._bg_tk = ph
        self._bg_shown = a
        self.itemconfig(self._bgid, image=ph, state="normal")

    def _reflect(self):
        """根据动画进度 t + 本项(悬停/选中)重排背景、图标位置与文字淡入。
        常态完全无底色(PCL 平),悬停/选中才画底色,且随 t 淡入——
        收起时底色跟着消失,不留任何白卡片/硬边。"""
        s = "active" if self._active else ("hover" if self._hover else "normal")
        self._cur = s
        t = getattr(self, "_t", 0.0)
        # 底图:淡入随 t 前段,宽度随 t 后段几乎同步(避免半截硬块)
        if s == "normal":
            a = 0.0
        else:
            a = min(1.0, t / 0.6)
        self._paint_bg(s, a, t)
        H = int(self._ch * self.sc)
        cy = PAD + H / 2.0
        # 底图是后画的,必须把图标/文字抬到它上面,否则被蓝块盖住(空蓝块)
        try:
            self.tag_raise(self._icid)
            self.tag_raise(self._tid)
        except Exception:
            pass
        if self._icon and self._expanding:
            # 图标从居中位置线性左移到展开位
            x0 = int(self._compact_w * self.sc) / 2.0 + PAD
            x1 = PAD + int(15 * self.sc)
            self.coords(self._icid, x0 + (x1 - x0) * t, cy)
            tx = PAD + int(31 * self.sc)
            self.coords(self._tid, tx, cy)
            if t > 0.55:
                # 文字淡入:t 0.55→1 映射到透明度 0→1(前景色向目标色混)
                a = (t - 0.55) / 0.45
                base = "#FFFFFF" if self._active else TEXT
                fill = self._blend(bg=(ACCENT if self._active else "#FFFFFF"),
                                   fg=base, k=a)
                self.itemconfig(self._tid, anchor="w", state="normal", fill=fill)
            else:
                self.itemconfig(self._tid, state="hidden")
        elif self._icon:
            self.coords(self._icid, PAD + int(15 * self.sc), cy)
            self.coords(self._tid, PAD + int(31 * self.sc), cy)
            self.itemconfig(self._tid, anchor="w", state="normal",
                            fill="#FFFFFF" if self._active else TEXT)
        else:
            self.itemconfig(self._tid, state="normal", anchor="center",
                            fill="#FFFFFF" if self._active else TEXT)
        self._repaint_icon()

    @staticmethod
    def _blend(bg, fg, k):
        """把 fg 按 k 叠到 bg 上(k=0 完全 bg,k=1 完全 fg)———模拟淡入"""
        try:
            b = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
            f = tuple(int(fg[i:i + 2], 16) for i in (1, 3, 5))
            mix = tuple(int(round(b[i] + (f[i] - b[i]) * k)) for i in range(3))
            return "#%02X%02X%02X" % mix
        except Exception:
            return fg

    def _on_enter(self, e):
        self._hover = True
        self._reflect()
        self._expand()

    def _on_leave(self, e):
        self._hover = False
        self._reflect()
        self._compress()

    def _release(self, e):
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        if inside and self.command:
            try:
                self.command()
            except Exception:
                pass
        self._reflect()

    # ---- 悬停展开 / 收起 ----
    def _expand(self):
        cb = getattr(self.master, "on_nav_hover", None)
        if cb:
            cb(True)

    def _compress(self):
        cb = getattr(self.master, "on_nav_hover", None)
        if cb:
            cb(False)

    def _state(self, s):
        # 兼容旧调用:只改悬停/常态
        self._hover = (s == "hover")
        self._reflect()

    def set_active(self, on):
        self._active = bool(on)
        self._reflect()


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
        self.entry.bind("<Return>", lambda e: self.on_enter())
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.bind("<Configure>", self._resize)

    def set_show(self, ch):
        self.entry.configure(show=ch)

    def on_enter(self):
        if getattr(self, "on_submit", None):
            try:
                self.on_submit()
            except Exception:
                pass

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
