# -*- coding: utf-8 -*-
"""自绘圆角菜单 —— 替掉原生 CreatePopupMenu(直角灰底,太丑)

为什么不用原生菜单
    win32 的 TrackPopupMenu 画出来是系统味:直角、灰底、无图标、无悬停反馈。
    想跟设置界面一个血统(圆角卡片 + 柔和投影 + 悬停高亮),只能自己画。

窗口模型(照抄 pet.py 的成熟做法)
    * WS_EX_LAYERED + WS_POPUP + WS_EX_TOOLWINDOW,用 UpdateLayeredWindow 推
      一张带 alpha 的整图 → 真·圆角 + 柔和阴影,不会有方角黑边
    * WS_EX_TOOLWINDOW  → 不出现在任务栏/Alt-Tab

⚠️ 消息循环(踩过的坑,别再改回去)
    * 必须用 `PeekMessageW(hwnd=self.hwnd, ...)` **限定到本窗口**。
      传 None 会从整个线程队列里捞,可能捞到别的窗口的消息,而本窗口的消息
      一直躺在队列里没人派发 → 表现是**窗口画得好好的,但 hover/点击全没反应**。
    * PeekMessageW / DispatchMessageW / TranslateMessage 都要显式声明
      argtypes/restype(BOOL 返回值不声明会被当成别的宽度解析)。
    * 自己建窗 + 自己跑消息循环的 `WS_POPUP` 窗,不经过 win32gui 的
      `PumpMessages`,所以这个循环漏一条消息就是静默失效。

线程模型
    * 菜单是**模态**的:run() 阻塞当前线程(必须是桌宠主线程,因为要收窗口消息),
      返回被选中的命令 id(没选返回 None)。
"""
import ctypes
import ctypes.wintypes as wt
import math

import win32con
import win32gui
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import uikit

# ---- 尺寸(逻辑像素,DPI 缩放另算;东家要求:再小、圆角小、字小) ----
W = 116               # 卡片宽
ITEM_H = 20           # 普通菜单项高(东家:太高,原 24 我误改 29,现压到 20)
SEP_H = 9             # 分隔线行的行高(东家:上下两行字之间空隙过大)
                      #   旧版 sep 跟普通项一样占满 ITEM_H(20),但只画 1px 细线,
                      #   白留 19px → 看就是"两行字离得太开"。单独给个小行高。
PAD_V = 3             # 卡片上下内边距
GAP = 7               # 阴影留白(画布四周)
ICON = 11             # 图标方框边长
RADIUS = 5            # 卡片圆角(东家:不用太大)
SS = 4                # 超采样倍数
SHADOW_BLUR = 5.0
SHADOW_ALPHA = 0.22
FONT_PX = 11.0        # 字号(东家:不用那么大)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BD = r"C:\Windows\Fonts\msyhbd.ttc"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# ⚠️ 显式声明:BOOL 类返回值不声明会被按错误宽度解析。
_pMSG = ctypes.POINTER(wt.MSG)
user32.PeekMessageW.argtypes = [_pMSG, wt.HWND, wt.UINT, wt.UINT, wt.UINT]
user32.PeekMessageW.restype = ctypes.c_int
user32.DispatchMessageW.argtypes = [_pMSG]
user32.DispatchMessageW.restype = ctypes.c_long
user32.TranslateMessage.argtypes = [_pMSG]
user32.TranslateMessage.restype = ctypes.c_int
user32.GetForegroundWindow.restype = wt.HWND
user32.MsgWaitForMultipleObjects.argtypes = [wt.DWORD, ctypes.c_void_p, ctypes.c_int,
                                             wt.DWORD, wt.DWORD]
user32.MsgWaitForMultipleObjects.restype = wt.DWORD


class Item(object):
    """一个菜单项:kind == "sep" 表示纯分隔线"""

    __slots__ = ("cmd", "label", "icon", "kind")

    def __init__(self, cmd, label, icon="none", kind="normal"):
        self.cmd = cmd
        self.label = label
        self.icon = icon          # none / gear / power / dot
        self.kind = kind          # normal / danger / sep


# ---------------- 图标(全部矢量画,不依赖素材) ----------------
def _draw_icon(d, box, name, color):
    """在 box=(x0,y0,x1,y1) 里画线性图标。坐标已是 SS 倍后的像素。"""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    r = (x1 - x0) / 2.0
    lw = max(1, int(1.5 * SS))

    if name == "gear":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=lw)
        d.ellipse((cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36),
                  outline=color, width=lw)
        for i in range(8):
            a = math.pi * 2 * i / 8
            d.line((cx + math.cos(a) * r, cy + math.sin(a) * r,
                    cx + math.cos(a) * r * 1.40, cy + math.sin(a) * r * 1.40),
                   fill=color, width=lw)
    elif name == "power":
        d.arc((cx - r, cy - r * 0.90, cx + r, cy + r * 1.10), 300, 240,
              fill=color, width=lw)
        d.line((cx, cy - r * 1.15, cx, cy + r * 0.05), fill=color, width=lw)
    elif name == "dot":
        rr = r * 0.55
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=color)


def _mix(c1, c2, k):
    a, b = uikit.rgb(c1), uikit.rgb(c2)
    return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def _row_hs(items, sc=1.0):
    """每一项的行高(逻辑像素列表):分隔线用 SEP_H,其余用 ITEM_H。

    这样菜单卡片总高不再把分隔线当整行算,两行字之间不会多出 ~19px 空隙。"""
    return [float(SEP_H if it.kind == "sep" else ITEM_H) for it in items]


def menu_size(sc=1.0, n=None, items=None):
    """(卡片宽, 卡片高, 阴影留白) —— 单位:物理像素

    n 仅在 items 为 None 时作为"n 个普通项"的旧式回退(保持旧调用不炸)。"""
    if items is not None:
        rows = _row_hs(items)
        total_h = sum(rows)
    else:
        total_h = ITEM_H * (1 if n is None else n)
    iw = int(round(W * sc))
    ih = int(round((PAD_V * 2 + total_h) * sc))
    pad = int(round(GAP * sc))
    return iw, ih, pad


def item_image(items, state="normal", sc=1.0, hover_idx=-1):
    """渲染整张菜单图(含阴影留白)。返回 PIL.Image。"""
    iw, ih, pad = menu_size(sc, items=items)
    cw, ch = iw + 2 * pad, ih + 2 * pad
    big = Image.new("RGBA", (cw * SS, ch * SS), (0, 0, 0, 0))

    rad = int(RADIUS * sc * SS)
    bx0, by0 = pad * SS, pad * SS
    bx1, by1 = (pad + iw) * SS - 1, (pad + ih) * SS - 1

    # 1) 投影
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    off = int(2 * sc * SS)
    ImageDraw.Draw(sh).rounded_rectangle(
        (bx0, by0 + off, bx1, by1 + off), radius=rad,
        fill=(0, 0, 0, int(SHADOW_ALPHA * 255)))
    big.alpha_composite(sh.filter(ImageFilter.GaussianBlur(SHADOW_BLUR * sc * SS)))
    d = ImageDraw.Draw(big)

    # 2) 卡片底 + 1px 描边
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=rad,
                        fill=(255, 255, 255, 253),
                        outline=uikit.rgb("#DCDEE4") + (255,), width=max(1, SS // 2))

    try:
        f_norm = ImageFont.truetype(FONT, max(9, int(FONT_PX * sc * SS)))
        f_dang = ImageFont.truetype(FONT_BD, max(9, int(FONT_PX * sc * SS)))
    except Exception:
        f_norm = f_dang = ImageFont.load_default()

    item_h = int(ITEM_H * sc * SS)
    pad_v = int(PAD_V * sc * SS)
    y = pad * SS + pad_v                     # 逐行累加:分隔线行只占 SEP_H
    for i, it in enumerate(items):
        rh = int(round((SEP_H if it.kind == "sep" else ITEM_H) * sc * SS))
        iy0 = y
        iy1 = iy0 + rh
        y = iy1

        if it.kind == "sep":
            ly = (iy0 + iy1) // 2
            d.line((bx0 + int(7 * sc * SS), ly, bx1 - int(7 * sc * SS), ly),
                   fill=uikit.rgb(uikit.LINE) + (255,), width=max(1, SS // 2))
            continue

        # 整行高亮要铺满卡片:左右各留 1px(防圆角露白)。
        # ⚠️⚠️ 单位必须统一:整张图是 SS 超采样空间,iw/pad 要各自乘 SS。
        #    旧版写 `pad*SS + iw` —— iw(116)没乘 SS,导致高亮右边界只到
        #    pad*SS+116 ≈ 140(SS空间),实际只占卡片 20% 宽 → 高亮只包住图标。
        #    东家截图:第一项高亮是个小方块、第二项完全不高亮。已实测确认。
        ix0 = int(round(pad * SS + 1 * sc * SS))
        ix1 = int(round((pad + iw) * SS - 1 * sc * SS))

        # 整行高亮:普通项用更饱和的蓝灰,危险项用更明显的淡红
        # (旧色 #E7EEFB 太淡,浅色卡片上几乎看不出整行变化 -> 东家反馈"只有图标变了")
        if i == hover_idx:
            hc = "#FBDAD8" if it.kind == "danger" else "#D6E4FA"
            if state == "press":
                hc = _mix(hc, "#000000", 0.08)
            d.rounded_rectangle((ix0, iy0, ix1, iy1),
                                radius=rad,
                                fill=uikit.rgb(hc) + (255,))

        fg = "#FF3B30" if it.kind == "danger" else uikit.TEXT
        fnt = f_dang if it.kind == "danger" else f_norm
        cy = (iy0 + iy1) // 2

        icx = ix0 + int(6 * sc * SS)
        if it.icon and it.icon != "none":
            half = int(ICON * sc * SS / 2)
            if it.kind == "danger":
                icol = "#E03127" if i == hover_idx else "#FF3B30"
            else:
                icol = "#0064E0" if i == hover_idx else "#0A84FF"
            _draw_icon(d, (icx, cy - half, icx + half * 2, cy + half), it.icon,
                       uikit.rgb(icol) + (255,))
            tx = icx + half * 2 + int(7 * sc * SS)
        else:
            tx = icx

        d.text((tx, cy), it.label, font=fnt, fill=uikit.rgb(fg) + (255,), anchor="lm")

    return big.resize((cw, ch), Image.Resampling.LANCZOS)


class MenuWindow(object):
    """自绘菜单窗。run() 是模态阻塞调用,返回选中的 cmd。"""

    def __init__(self, items, owner_hwnd=None, sc=1.0):
        self.items = list(items)
        self.owner = owner_hwnd
        self.sc = max(0.75, min(2.4, sc))
        self.hover = -1
        self.result = None
        self._pressing = False
        self._imgs = {}
        self._open = False
        self._origin = (0, 0)
        self._hinst = win32gui.GetModuleHandle(None)
        self._cls = "DSPetMenuWnd%s" % id(self)
        self.hwnd = None

    # ---------- 几何 ----------
    def _place(self):
        """菜单出现在鼠标处;贴边自动翻转"""
        iw, ih, pad = menu_size(self.sc, items=self.items)
        cx, cy = win32gui.GetCursorPos()
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = cx - pad
        y = cy - pad
        if x + iw + pad > sw:
            x = sw - iw - pad - 4
        if y + ih + pad > sh:
            y = sh - ih - pad - 4
        x, y = max(4, x), max(4, y)
        return x, y, iw, ih, pad

    # ---------- 窗口 ----------
    def _create(self):
        wc = win32gui.WNDCLASS()
        wc.hInstance = self._hinst
        wc.lpszClassName = self._cls
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.lpfnWndProc = self._wndproc
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
        ex = win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW
        x, y, iw, ih, pad = self._place()
        self._origin = (x, y)
        self.hwnd = win32gui.CreateWindowEx(
            ex, self._cls, "", win32con.WS_POPUP,
            x, y, iw, ih, self.owner or 0, 0, self._hinst, None)

    def _push(self):
        """当前状态(含 hover)推成一张图,UpdateLayeredWindow 贴上去"""
        st = "press" if self._pressing else "normal"
        key = (self.hover, st)
        img = self._imgs.get(key)
        if img is None:
            img = item_image(self.items, state=st, sc=self.sc, hover_idx=self.hover)
            self._imgs[key] = img

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
        hbmp = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), 0,
                                      ctypes.byref(ppv), None, 0)
        old = gdi32.SelectObject(memdc, hbmp)
        ctypes.memmove(ppv, buf, len(arr))

        x, y = self._origin
        blend = (0, 0, 255, 1)
        try:
            win32gui.UpdateLayeredWindow(self.hwnd, hdc, (x, y), (img.width, img.height),
                                         memdc, (0, 0), 0, blend, win32con.ULW_ALPHA)
        except Exception:
            win32gui.UpdateLayeredWindow(self.hwnd, hdc, (x, y), (img.width, img.height),
                                         memdc, (0, 0), 0, (0, 0, 255, 1),
                                         win32con.ULW_ALPHA)
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        win32gui.ReleaseDC(0, hdc)

    # ---------- 命中 ----------
    def _index_at(self, mxc, myc):
        """客户区物理坐标 → 菜单项下标(不可点时 -1)

        ⚠️ 东家反馈"不够敏锐"。旧实现要求 x 落在 0..W 且严格整除 ITEM_H,
           鼠标稍偏到卡片留白/圆角外就丢 hover。这里放宽:
           - x 只判"是否在卡片内"(含左右各 1 个 GAP 的软区)
           - y 用 round() 代替 floor 的边界抖动,并对 sep 行做前后吸附
        """
        pad = int(round(GAP * self.sc))
        lx = mxc / self.sc
        ly = myc / self.sc
        # x 软区:卡片左右各放宽一点,别让贴着边缘的鼠标丢 hover
        if lx < -1 or lx > W + 1:
            return -1
        rel = ly - (pad + PAD_V)
        # ⚠️ 真 bug:命中空白区(卡片上下留白、分隔线行)时旧实现返回 -1,
        #    高亮被清掉 → 鼠标在卡片内滑动时高亮一闪一闪,像"只有图标有反应"。
        #    现在统一回退到**最近的菜单项**:分隔线吸附到前一项,越界吸附首/尾项。
        # ⚠️ 行高不再统一:分隔线用 SEP_H,普通项用 ITEM_H。这里逐行累加,
        #    否则命中区会和画出来的位置错位(点"退出桌宠"高亮到"打开设置"上)。
        if rel < 0:
            return self._nearest_item(0)
        y = 0.0
        for i, it in enumerate(self.items):
            rh = SEP_H if it.kind == "sep" else ITEM_H
            if rel < y + rh:
                # 落在第 i 行:分隔线自己的横条 → 吸附到前后最近可点项
                if it.kind == "sep":
                    return self._nearest_item(i)
                return i
            y += rh
        return self._nearest_item(len(self.items) - 1)

    def _nearest_item(self, i):
        """从下标 i 向外找最近的可点菜单项;都没有则 -1。"""
        if not self.items:
            return -1
        i = max(0, min(len(self.items) - 1, i))
        for d in range(len(self.items)):
            for k in (i - d, i + d):
                if 0 <= k < len(self.items) and self.items[k].kind != "sep":
                    return k
        return -1

    # ---------- 消息 ----------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        # ⚠️ 分层窗口(WS_EX_LAYERED)不显式返回 HTCLIENT 时,鼠标命中测试
        #    可能把整窗当"非客户区"→ 只发 WM_NCHITTEST 而**不发 WM_MOUSEMOVE**,
        #    表现就是 hover 全灭(这个坑踩过)。必须显式声明整窗都是客户区。
        if msg == win32con.WM_NCHITTEST:
            return win32con.HTCLIENT
        if msg == win32con.WM_MOUSEMOVE:
            _track_leave(hwnd)
            mx, my = _lo(lparam), _hi(lparam)
            i = self._index_at(mx, my)
            if i != self.hover:
                self.hover = i
                self._push()
            return 0
        if msg == win32con.WM_MOUSELEAVE:
            if self.hover != -1:
                self.hover = -1
                self._push()
            return 0
        if msg == win32con.WM_LBUTTONDOWN:
            if not self._pressing:
                self._pressing = True
                self._push()
            return 0
        if msg == win32con.WM_LBUTTONUP:
            self._pressing = False
            mx, my = _lo(lparam), _hi(lparam)
            i = self._index_at(mx, my)
            if i >= 0:
                self.result = self.items[i].cmd
                self._close()
            else:
                self._push()
            return 0
        if msg == win32con.WM_ACTIVATE:
            # 失去前台 → 关(点别处)
            if _lo(wparam) == win32con.WA_INACTIVE and self._open:
                self._close()
            return 0
        if msg == win32con.WM_KEYDOWN:
            self._on_key(wparam)
            return 0
        if msg == win32con.WM_TIMER:
            # 前台轮询兜底:某些情况下 WM_ACTIVATE 不来
            if self._open and user32.GetForegroundWindow() != self.hwnd:
                self._close()
            return 0
        if msg == win32con.WM_DESTROY:
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _on_key(self, vk):
        if vk == win32con.VK_ESCAPE:
            self.result = None
            self._close()
        elif vk in (win32con.VK_DOWN, win32con.VK_UP):
            n = len(self.items)
            if n:
                step = 1 if vk == win32con.VK_DOWN else -1
                i = self.hover
                for _ in range(n):
                    i = (i + step) % n
                    if self.items[i].kind != "sep":
                        break
                self.hover = i
                self._push()
        elif vk in (win32con.VK_RETURN, win32con.VK_SPACE):
            i = self.hover
            if 0 <= i < len(self.items) and self.items[i].kind != "sep":
                self.result = self.items[i].cmd
                self._close()

    def _close(self):
        if not self._open:
            return
        self._open = False
        try:
            user32.KillTimer(self.hwnd, 1)
        except Exception:
            pass
        try:
            win32gui.DestroyWindow(self.hwnd)
        except Exception:
            pass

    # ---------- 模态运行 ----------
    def run(self):
        """阻塞:返回选中的 cmd(没选返回 None)"""
        try:
            self._create()
        except Exception:
            return None
        self._open = True
        self._push()

        # ⚠️ 必须 SW_SHOW(激活)而不是 SW_SHOWNOACTIVATE。
        #    分层 + TOOLWINDOW + 无父窗的 WS_POPUP,不激活时 Windows **不给它发鼠标消息**
        #    (只发一条 WM_NCHITTEST 就没了)→ hover/点击全失效。
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        # 前台锁定(用户正在别的窗口)时 SetForegroundWindow 会失败,
        # 用 AttachThreadInput 借一下前台线程的输入队列,保证能抢到前台。
        try:
            fg = user32.GetForegroundWindow()
            tid_fg = user32.GetWindowThreadProcessId(fg, None)
            tid_me = ctypes.windll.kernel32.GetCurrentThreadId()
            if tid_fg and tid_me and tid_fg != tid_me:
                user32.AttachThreadInput(tid_fg, tid_me, True)
                user32.SetForegroundWindow(self.hwnd)
                user32.AttachThreadInput(tid_fg, tid_me, False)
            else:
                user32.SetForegroundWindow(self.hwnd)
        except Exception:
            pass
        self._push()
        user32.SetTimer(self.hwnd, 1, 120, None)

        # ⚠️⚠️ 这里是 hover 不稳的**真正根因**。
        #    菜单是弹在桌宠**主线程**里的(WM_RBUTTONUP → _menu → run())。
        #    旧实现 PeekMessageW 只捞本窗口的消息,于是:
        #      * 主线程上别的窗口(桌宠自身、Tk 定时器)的消息全被压在队列里没人派发;
        #      * 更糟的是——**Windows 只在"消息循环当前正在等待"时才做鼠标命中测试**。
        #        我们 8ms 就轮询一次,窗口刚建好时经常抢在系统完成 hit-test 之前就
        #        开始下一轮,于是 WM_MOUSEMOVE 时有时无 → 高亮闪、"只有图标有反应"。
        #
        #    两处一起改:
        #      ① PeekMessageW(hwnd=None) 捞**整个线程队列**,把不属于菜单的消息
        #         转交给原主循环(win32gui.PumpMessages 的窗口过程),既不饿死别人,
        #         也保证菜单自己的 WM_MOUSEMOVE 一定能被派发。
        #      ② 用 GetMessageW 式的**阻塞等待**(PeekMessage 不命中时
        #         MsgWaitForMultipleObjects 挂起等待输入),让系统把鼠标消息投递完
        #         再唤醒我们,彻底消掉 8ms 空转导致的命中测试竞争。
        msg = wt.MSG()
        PM_REMOVE = 1
        QS_ALLINPUT = 0x04FF
        while self._open:
            # ① 先把本线程队列里的消息全部捞干、派发掉
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == win32con.WM_QUIT:
                    self._open = False
                    break
                # 菜单自己的消息 + 别人的消息(桌宠窗口、Tk 定时器等)都照样派发
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            if not self._open:
                break
            # ② 队列空了就**阻塞等待**下一次输入,别空转抢 hit-test
            user32.MsgWaitForMultipleObjects(0, None, False, 40, QS_ALLINPUT)

        try:
            if win32gui.IsWindow(self.hwnd):
                win32gui.DestroyWindow(self.hwnd)
        except Exception:
            pass
        return self.result


# ---- 小工具 ----
def _lo(v):
    return ctypes.c_short(v & 0xFFFF).value


def _hi(v):
    return ctypes.c_short((v >> 16) & 0xFFFF).value


class _TRACK(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("dwFlags", wt.DWORD), ("hwndTrack", wt.HWND),
                ("dwHoverTime", wt.DWORD)]


def _track_leave(hwnd):
    t = _TRACK()
    t.cbSize = ctypes.sizeof(_TRACK)
    t.dwFlags = 0x00000002  # TME_LEAVE
    t.hwndTrack = hwnd
    t.dwHoverTime = 0
    user32.TrackMouseEvent(ctypes.byref(t))
