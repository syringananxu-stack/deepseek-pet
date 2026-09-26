# -*- coding: utf-8 -*-
"""设置窗开场用的「圆形标记」——真透明分层窗,负责"小标记冒出来"那一段。

东家需求(原话):
    「3 我想要的是有那个圆形图标啊,那个我没看到」
    —— 设置窗进场时,应该先冒出一个**圆形的标记**,停顿一下,再铺开成完整窗口。

为什么单独开一个窗,而不是在设置窗里画圆:
    设置窗是普通 Tk/CTk 窗口(TkTopLevel),**不支持逐像素透明**,
    在它里面画圆只能得到"带方形底色的圆"。要做真·圆形、圆外全透明,
    唯一正路是 WS_EX_LAYERED + UpdateLayeredWindow。
    这套技术在 menuwin.py 里已经踩平过(见那里的注释),这里复用同样的做法。

设计:
    IntroCircle(root_x, root_y, root_w, root_h, size, ...)
      - 以设置窗的最终位置为基准,算出圆心(默认窗口水平居中,垂直略偏上)
      - show()  -> 淡入 + 从小到大轻微弹出
      - hold()  -> 停顿(由调用方控制时长)
      - close() -> 淡出并销毁
    所有方法都设计成**绝不抛异常拖垮主程序**:失败时静默降级,
    主程序照常直接把设置窗显示出来(宁可没有开场,不能开不出窗)。
"""
import ctypes
import os
from ctypes import wintypes as wt

from PIL import Image, ImageDraw, ImageFont

# ---- 可选依赖(win32 不可用时降级) ----
try:
    import win32con
    import win32gui
    _HAS_WIN32 = True
except Exception:                                   # pragma: no cover
    _HAS_WIN32 = False

try:
    from ctypes import windll
    gdi32 = windll.gdi32
    user32 = windll.user32
except Exception:                                   # pragma: no cover
    gdi32 = user32 = None

SS = 4                       # 超采样倍数(圆边更顺滑)
_CLS = "DSPetIntroCircle"
_FONT_CANDS = (r"C:\Windows\Fonts\msyhbd.ttc",
               r"C:\Windows\Fonts\msyh.ttc",
               r"C:\Windows\Fonts\simhei.ttf")

# 配色:DeepSeek 蓝,和菜单/设置窗的强调色一致
RING = (74, 144, 255)        # 圆环
RING_SOFT = (168, 205, 255)  # 圆环外圈柔光
FILL = (255, 255, 255)       # 圆内底色


# 开场圆标记用的素材(东家给的那张:蓝发女仆抱鲸鱼,本身即圆形)
# 用 paths.resource_path 定位,兼容 PyInstaller 打包(_MEIPASS/assets)。
# 之前手搓 __file__ 相对路径,打包后 exists() 为假 -> 误走兜底画"九"字。
try:
    from .paths import resource_path as _resource_path
except Exception:
    _resource_path = None
BADGE = (_resource_path("intro_badge_circle.png") if _resource_path
         else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "assets", "intro_badge_circle.png"))


def _font(size):
    for fp in _FONT_CANDS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def circle_image(size=96, text="九", logo=None):
    """产出开场用的圆形标记(正方形 RGBA,圆外全透明)。

    首选:东家给的 badge 素材(intro_badge_circle.png,本身自带蓝环与圆形),
          直接等比缩放进圆里 —— 不额外描边,免得"环套环"。
    兜底:没有素材时,现画一个 蓝环+白底+文字 的圆(旧行为)。

    size  —— 圆直径(逻辑像素)
    text  —— 兜底圆里的字
    logo  —— 指定图;None 表示用默认 BADGE(若存在)
    """
    S = size * SS
    art = logo
    if art is None and os.path.exists(BADGE):
        art = BADGE

    # ---- 有素材:直接缩放,圆的自带边就是它的边 ----
    if art:
        try:
            src = Image.open(art).convert("RGBA")
            sw, sh = src.size
            k = S / float(max(sw, sh))
            src = src.resize((max(1, int(sw * k)), max(1, int(sh * k))), Image.LANCZOS)
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.alpha_composite(src, ((S - src.width) // 2, (S - src.height) // 2))
            return out.resize((size, size), Image.LANCZOS)
        except Exception:
            pass

    # ---- 兜底:现画一个圆 ----
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pad = int(S * 0.06)
    gd.ellipse((pad, pad, S - pad, S - pad), fill=RING_SOFT + (92,))
    from PIL import ImageFilter
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.035)))
    m = int(S * 0.10)
    d.ellipse((m, m, S - m, S - m), fill=FILL + (255,))
    d.ellipse((m, m, S - m, S - m), outline=RING + (255,), width=max(2, int(S * 0.028)))
    if text:
        f = _font(int((S - 2 * m) * 0.54))
        try:
            bb = d.textbbox((0, 0), text, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            tw, th = 0, 0
        d.text(((S - tw) // 2 - bb[0], (S - th) // 2 - bb[1]), text,
               font=f, fill=RING + (255,))
    return img.resize((size, size), Image.LANCZOS)


def _push_layered(hwnd, img, x, y, alpha=1.0):
    """把一张 RGBA 图贴到分层窗上(圆外自然全透明)。"""
    if alpha < 1.0:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img = img.copy()
        img.putalpha(a)
    arr = img.tobytes("raw", "BGRA")
    buf = (ctypes.c_char * len(arr)).from_buffer_copy(arr)

    hdc = win32gui.GetDC(0)
    memdc = gdi32.CreateCompatibleDC(hdc)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    class BI(ctypes.Structure):
        _fields_ = [("bmiHeader", BMIH), ("bmiColors", wt.DWORD * 3)]

    bmi = BI()
    bmi.bmiHeader.biSize = ctypes.sizeof(BMIH)
    bmi.bmiHeader.biWidth = img.width
    bmi.bmiHeader.biHeight = -img.height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    ppv = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), 0, ctypes.byref(ppv), None, 0)
    old = gdi32.SelectObject(memdc, hbmp)
    ctypes.memmove(ppv, buf, len(arr))
    try:
        win32gui.UpdateLayeredWindow(hwnd, hdc, (x, y), (img.width, img.height),
                                     memdc, (0, 0), 0, (0, 0, 255, 1), win32con.ULW_ALPHA)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        win32gui.ReleaseDC(0, hdc)


class IntroCircle(object):
    """设置窗开场时冒出来的圆形标记。所有异常都被吞掉,失败即降级。"""

    def __init__(self, win_x, win_y, win_w, win_h, size=168, text="九", logo=None):
        self.size = max(48, int(size))
        self.win_x, self.win_y = int(win_x), int(win_y)
        self.win_w, self.win_h = int(win_w), int(win_h)
        # 圆心:居中于整个屏幕(东家要求:圆要居于屏幕正中)
        try:
            import ctypes
            u = ctypes.windll.user32
            self.cx = int(u.GetSystemMetrics(0) // 2)
            self.cy = int(u.GetSystemMetrics(1) // 2)
        except Exception:
            # 降级:退回窗口中心
            self.cx = self.win_x + self.win_w // 2
            self.cy = self.win_y + self.win_h // 2
        self._img = circle_image(self.size, text=text, logo=logo)
        self.hwnd = None
        self._shown = False

    # ---------- 生命周期 ----------
    def _create(self):
        if not _HAS_WIN32:
            return False
        hinst = win32gui.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = _CLS
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.lpfnWndProc = self._wndproc
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
        ex = win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE
        s = self.size
        self.hwnd = win32gui.CreateWindowEx(
            ex, _CLS, "", win32con.WS_POPUP,
            self.cx - s // 2, self.cy - s // 2, s, s, 0, 0, hinst, None)
        return bool(self.hwnd)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """标记不吃鼠标:点击穿透到下面的窗口,也别抢焦点。"""
        if msg == win32con.WM_NCHITTEST:
            return win32con.HTTRANSPARENT
        if msg == win32con.WM_MOUSEACTIVATE:
            return win32con.MA_NOACTIVATE
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _place(self, scale):
        """按缩放比例算窗口位置与尺寸,贴图。"""
        s = max(8, int(self.size * scale))
        x = self.cx - s // 2
        y = self.cy - s // 2
        img = self._img
        if s != self.size:
            img = img.resize((s, s), Image.LANCZOS)
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, x, y, s, s,
                              win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
        _push_layered(self.hwnd, img, x, y, alpha=1.0)

    # ---------- 对外 ----------
    def show(self, steps=7, delay=14):
        """在 tk 主线程里调用:淡入 + 轻微弹出。"""
        if not self._create():
            return False
        self._shown = True
        try:
            self._place(1.0)
            for i in range(steps + 1):
                k = i / float(steps)
                e = 1 - (1 - k) ** 2
                self._place(0.72 + 0.28 * e)
                if i < steps:
                    import time
                    time.sleep(delay / 1000.0)
        except Exception:
            pass
        return True

    def close(self):
        if not self._shown or not self.hwnd:
            return
        try:
            import time
            for i in range(5, -1, -1):
                k = i / 5.0
                self._place(1.0)
                # 收尾淡出:直接缩小 + 贴回,简单可靠
                s = max(8, int(self.size * (0.72 + 0.28 * k)))
                x = self.cx - s // 2
                y = self.cy - s // 2
                img = self._img.resize((s, s), Image.LANCZOS)
                a = img.getchannel("A").point(lambda v: int(v * k))
                img.putalpha(a)
                _push_layered(self.hwnd, img, x, y)
                time.sleep(0.012)
        except Exception:
            pass
        try:
            win32gui.DestroyWindow(self.hwnd)
        except Exception:
            pass
        self.hwnd = None
        self._shown = False
