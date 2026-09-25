# -*- coding: utf-8 -*-
"""大肥鱼本体:分层透明窗口 / 弹簧形变 / 溜达 / 全屏让位 / 喂文件

设计要点
  * 纯本地渲染(win32 分层窗口 + PIL),不联网也能跑
  * 唯一联网点 = 余额查询(balance.py),用户自己的 Key,只读、不消耗 token
  * 线程模型:主线程跑 win32 消息循环;余额轮询 / 全屏检测 / 设置窗口各自独立线程
  * 设置改动 → settings_ui 写盘后给窗口 PostMessage(WM_APP_RELOAD),由主线程应用
"""
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import math
import os
import random
import threading
import time

import win32con
import win32gui
from PIL import Image, ImageDraw, ImageFont

from . import VERSION
from . import autostart, balance, config
from .paths import resource_path

CHAR_BASE = 250.0
LEVELS = [0.55, 0.68, 0.82, 1.00, 1.20]

TICK_IDLE = 500
TICK_WALK = 20
TICK_ANIM = 20

INFO_SECONDS = 5
OVERRIDE_SECONDS = 4
SPEED_MIN, SPEED_MAX = 26.0, 44.0

# 弹簧参数(偏硬一点 → 点击反应更短促、每次都是干净的一下)
K_SPRING = 0.22
C_SPRING = 0.15
HOLD_STRETCH = -0.45
IMP_GRAB = -0.34
IMP_CLICK = 0.30        # 菜单「弹一下」/ 吃东西用
POP_PRESET = -0.17      # 点击前先"压一下",保证每次都从同一状态弹起
POP_IMPULSE = 0.60      # 点击冲击(比之前大,反应更明显)

# 安静 / 溜达节奏(秒):被打扰后先老实待着,冷落够了才自己溜达
CALM_INIT = (20, 45)      # 刚启动:先静止多久
CALM_AFTER = (25, 55)     # 被点/被菜单打扰后
CALM_AFTER_DRAG = (45, 120)   # 被抓住拖过之后 → 老实很久

WM_APP_RELOAD = win32con.WM_APP + 1

WS_EX_ACCEPTFILES = 0x00000010
WM_DROPFILES = 0x0233
FO_DELETE = 3
FOF_ALLOWUNDO = 0x40
FOF_NOCONFIRMATION = 0x10
FOF_SILENT = 0x0004
FOF_NOERRORUI = 0x0400

NAVY = (32, 46, 104)
GREEN = (43, 163, 92)
RED = (214, 69, 69)
GREY = (138, 150, 168)
MAGENTA = (188, 76, 132)
ORANGE = (206, 118, 30)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BD = r"C:\Windows\Fonts\msyhbd.ttc"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
winmm = ctypes.windll.winmm
shell32 = ctypes.windll.shell32
SPI_GETWORKAREA = 0x0030

CHAT = [
    "哼,又来看人家?",
    "看什么看,笨蛋。",
    "诶——你偷看人家!",
    "钱包又瘪了?笨蛋。",
    "别乱点啦,会烦的。",
    "摸摸头?做梦哦。",
    "人家忙着呢,少烦。",
    "点一次记你一次账。",
    "省着点花,笨蛋。",
    "就这么想人家?",
    "盯着看干嘛,杂鱼。",
    "再点就咬你哦,嗷呜。",
    "真拿你没办法……",
    "杂鱼,力气真小。",
    "这点钱就心疼啦?",
    "哈?就这?杂鱼。",
    "笨蛋笨蛋笨蛋——",
    "人家才不是害羞!",
    "啧,又来蹭人家脸。",
    "钱花这么快,猪吗?",
    "走两步都不行?",
    "文件乱丢,猪窝吗?",
    "拎人家像拎史莱姆?",
    "手别抖啊,笨蛋。",
]
CHAT_LATE = [
    "这么晚还不睡?笨蛋。",
    "夜猫子,陪你一会儿。",
    "都几点了还在折腾。",
]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("wFunc", wt.UINT), ("pFrom", wt.LPCWSTR),
                ("pTo", wt.LPCWSTR), ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wt.BOOL), ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wt.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def work_area():
    r = RECT()
    try:
        if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def play_sound(path):
    if not path or not os.path.exists(path):
        return

    def _run():
        try:
            alias = "dspet%d" % random.randint(1000, 9999)
            winmm.mciSendStringW('open "%s" alias %s' % (path, alias), None, 0, None)
            winmm.mciSendStringW('play %s' % alias, None, 0, None)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def recycle(paths):
    if not paths:
        return False
    buf = "\0".join(paths) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.hwnd = 0
    op.wFunc = FO_DELETE
    op.pFrom = buf
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    try:
        return shell32.SHFileOperationW(ctypes.byref(op)) == 0
    except Exception:
        return False


class Pet(object):
    def __init__(self):
        self.cfg = config.load()
        self.key = config.get_api_key(self.cfg)
        self.balance = None
        self.err = ""
        self.pending_key = None
        self.calm_mode = bool(self.cfg.get("calm", True))
        self.still_until = 0.0
        self._moving = False

        self.level = max(0, min(len(LEVELS) - 1, int(self.cfg.get("size_level", 1))))
        self.wander = bool(self.cfg.get("wander", True))
        self.hard_delete = bool(self.cfg.get("hard_delete", False))
        self.topmost = bool(self.cfg.get("topmost", True))
        self.auto_hide_fs = bool(self.cfg.get("auto_hide_fullscreen", True))
        self.sounds = bool(self.cfg.get("sounds", True))
        self.show_chat = bool(self.cfg.get("chat", True))
        self.refresh_sec = max(10, int(self.cfg.get("refresh_sec", 30)))

        self.dragging = False
        self.drag_off = (0.0, 0.0)
        self.moved = False
        self.squash = 0.0
        self.sqv = 0.0
        self.sq_target = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self._tickn = 0
        self._period = 0
        self._last_move_t = 0.0
        self._pos_valid = False
        self._hidden = False
        self.info_until = 0.0
        self.override_txt = ""
        self.override_until = 0.0
        self.chat = self._pick_chat()
        self.chat_until = time.time() + random.uniform(22, 45)
        self._settings_open = False

        self.char_src = Image.open(resource_path("DSniang1.png")).convert("RGBA")
        self.snd_press = resource_path("Ya1.mp3")
        self.snd_eat = None
        for cand in ("eat.wav", "Ya1.mp3"):
            p = resource_path(cand)
            if os.path.exists(p):
                self.snd_eat = p
                break

        self._layout()
        self._create_window()
        self._init_velocity()
        self.still_until = time.time() + self._delay(CALM_INIT)   # 开机先安静待着

    # ---------- 调试 ----------
    def _dbg(self, tag):
        if not os.environ.get("DSPET_DEBUG"):
            return
        try:
            with open(os.path.join(config.config_dir(), "_dbg.log"), "a", encoding="utf-8") as fh:
                fh.write("%.3f %s squash=%.3f sqv=%.3f tgt=%.3f drag=%s v=(%.1f,%.1f) pos=(%d,%d)\n"
                         % (time.time() % 100000, tag, self.squash, self.sqv, self.sq_target,
                            self.dragging, self.vx, self.vy, self.x, self.y))
        except Exception:
            pass

    def _init_velocity(self):
        spd = random.uniform(SPEED_MIN, SPEED_MAX)
        ang = random.uniform(0, 2 * math.pi)
        self.vx = spd * math.cos(ang)
        self.vy = spd * 0.62 * math.sin(ang)
        if abs(self.vx) < 9.0:
            self.vx = 9.0 if self.vx >= 0 else -9.0
        if abs(self.vy) < 6.0:
            self.vy = 6.0 if self.vy >= 0 else -6.0

    # ---------- 安静 / 溜达节奏 ----------
    def _delay(self, rng):
        fast = os.environ.get("DSPET_FAST_STILL")
        if fast:                                    # 自查用:固定等待秒数
            try:
                return float(fast)
            except ValueError:
                return 3.0
        if not self.calm_mode:
            return 0.0
        return random.uniform(*rng)

    def _go_calm(self, rng=CALM_AFTER):
        """开始安静期:这段时间她待着不动,到点才继续溜达"""
        self.still_until = time.time() + self._delay(rng)
        self._moving = False

    def _wants_to_move(self):
        now = time.time()
        return (self.wander and self.calm_mode and now >= self.still_until) or \
               (self.wander and not self.calm_mode)

    # ---------- 点击反馈 ----------
    def _pop(self):
        """每次点击都给一个完整、短促的一下(先把弹簧压回去,再弹起)"""
        self.squash = POP_PRESET
        self.sqv = 0.0
        self._impulse(POP_IMPULSE)

    # ---------- 文本 ----------
    def _pick_chat(self):
        if not self.show_chat:
            return "…"
        h = dt.datetime.now().hour
        pool = CHAT_LATE if (h >= 23 or h < 6) else CHAT
        choices = [c for c in pool if c != getattr(self, "chat", None)]
        return random.choice(choices or pool)

    def _lines(self):
        now = time.time()
        if now < self.override_until:
            return "chat", [(self.override_txt, ORANGE, self.f2)]
        if now < self.info_until:
            is_peak, left = balance.peak_info()
            if self.balance is not None:
                bal = "余额 ¥%.2f" % self.balance
            else:
                bal = "余额读不到"
            return "info", [(bal, NAVY, self.f1),
                            ("● " + ("高峰 · 全价" if is_peak else "低谷 · 半价"),
                             (RED if is_peak else GREEN), self.f2),
                            (("→高峰 " if not is_peak else "→低谷 ") + balance.hms(left), GREY, self.f3)]
        return "chat", [(self.chat, MAGENTA, self.f2)]

    # ---------- 布局 ----------
    def _layout(self):
        self.s = LEVELS[self.level]
        self.CW = int(CHAR_BASE * self.s)
        self.char = self.char_src.resize((self.CW, self.CW), Image.LANCZOS)
        self.f1 = self._font(24 * self.s, True)
        self.f2 = self._font(17 * self.s)
        self.f3 = self._font(14 * self.s)
        self.wrap_w = int(196 * self.s)
        self.pad = int(15 * self.s)
        self.mw = self.wrap_w + 2 * self.pad
        self.w = max(self.mw + int(10 * self.s), self.CW + 6)
        self.max_bh = int(103 * self.s) + int(16 * self.s)
        self.h = self.max_bh + self.CW

    def _font(self, size, bold=False):
        try:
            return ImageFont.truetype(FONT_BD if bold else FONT, max(11, int(size)))
        except Exception:
            return ImageFont.load_default()

    def _wrap(self, text, font):
        tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        lines, cur = [], ""
        for ch in text:
            if tmp.textlength(cur + ch, font=font) <= self.wrap_w or not cur:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    # ---------- 窗口 ----------
    def _create_window(self):
        w, h = self.w, self.h
        wa = work_area()
        pos = self.cfg.get("pos") or []
        try:
            self.x = int(pos[0])
            self.y = int(pos[1])
        except Exception:
            self.x, self.y = wa[2] - w - 90, wa[3] - h - 20
        self.fx, self.fy = float(self.x), float(self.y)
        hInst = win32gui.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hInst
        wc.lpszClassName = "DSPetWnd"
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_HAND)
        wc.lpfnWndProc = self._wndproc
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
        ex = (win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW | WS_EX_ACCEPTFILES)
        if self.topmost:
            ex |= win32con.WS_EX_TOPMOST
        self.hwnd = win32gui.CreateWindowEx(ex, "DSPetWnd", "DeepSeek 大肥鱼",
                                            win32con.WS_POPUP, self.x, self.y, w, h,
                                            0, 0, hInst, None)
        try:
            shell32.DragAcceptFiles(self.hwnd, True)
        except Exception:
            pass
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        self._pos_valid = True
        self._redraw()

    def _set_pos(self, x, y):
        ix, iy = int(round(x)), int(round(y))
        if ix == self.x and iy == self.y and self._pos_valid:
            return
        self.x, self.y = ix, iy
        self._pos_valid = True
        z = win32con.HWND_TOPMOST if self.topmost else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(self.hwnd, z, self.x, self.y, self.w, self.h,
                              win32con.SWP_NOACTIVATE | win32con.SWP_NOSENDCHANGING)

    def _move_to(self, x, y):
        self.fx, self.fy = float(x), float(y)
        self._set_pos(self.fx, self.fy)

    def _clamp(self, x, y):
        wa = work_area()
        x = max(wa[0] + 4, min(x, wa[2] - self.w - 4))
        y = max(wa[1] + 4, min(y, wa[3] - self.h - 4))
        return float(x), float(y)

    def _snap(self):
        wa = work_area()
        sl, st, sr, sb = wa
        if abs((self.y + self.h) - sb) <= 70:
            self.y = sb - self.h
        if abs(self.y - st) <= 70:
            self.y = st
        if abs((self.x + self.w // 2) - (sl + (sr - sl) // 2)) <= 70:
            self.x = sl + (sr - sl) // 2 - self.w // 2
        if abs(self.x - sl) <= 40:
            self.x = sl
        if abs((self.x + self.w) - sr) <= 40:
            self.x = sr - self.w
        self.fx, self.fy = float(self.x), float(self.y)

    # ---------- 绘制 ----------
    def _measure(self):
        tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        kind, rows = self._lines()
        out = []
        for text, color, font in rows:
            for seg in self._wrap(text, font):
                out.append((seg, color, font))
        wpx = max([tmp.textlength(s, font=f) for s, c, f in out] or [10])
        step = int(27 * self.s) if kind == "info" else int(23 * self.s)
        hpx = len(out) * step + int(22 * self.s)
        return out, wpx, hpx, step

    def _compose(self):
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        s = self.s
        content, wpx, hpx, step = self._measure()
        bw = int(min(self.w - int(6 * s), wpx + 2 * self.pad))
        bh = int(hpx)
        bx = (self.w - bw) // 2
        by = 3
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(15 * s),
                            fill=(255, 255, 255, 247), outline=NAVY, width=max(2, int(3 * s)))
        ox, oy = bx + bw // 2 + int(10 * s), by + bh
        d.ellipse([ox - int(9 * s), oy + int(3 * s), ox + int(9 * s), oy + int(21 * s)],
                  fill=(255, 255, 255, 247), outline=NAVY, width=max(2, int(3 * s)))
        d.ellipse([ox - int(14 * s), oy + int(26 * s), ox - int(2 * s), oy + int(38 * s)],
                  fill=(255, 255, 255, 247), outline=NAVY, width=max(1, int(2 * s)))
        y = by + int(11 * s)
        for text, color, font in content:
            d.text((bx + self.pad, y), text, font=font, fill=color)
            y += step
        sq = max(-1.35, min(1.35, self.squash))
        dy = int(round(10 * sq * s))
        f = self.char
        if abs(sq) > 0.01:
            f = f.resize((max(8, int(f.width * (1 + 0.15 * sq))),
                          max(8, int(f.height * (1 - 0.21 * sq)))), Image.BILINEAR)
        img.alpha_composite(f, ((self.w - f.width) // 2, self.h - f.height + dy))
        return img

    def _redraw(self):
        img = self._compose()
        try:
            import numpy as np
            arr = np.array(img, dtype=np.uint8)
            bgra = arr[:, :, [2, 1, 0, 3]]
            a = bgra[:, :, 3:4].astype(np.uint16)
            rgb = (bgra[:, :, :3].astype(np.uint16) * a) // 255
            data = np.dstack([rgb.astype(np.uint8), bgra[:, :, 3]]).tobytes()
        except Exception:
            px = img.load()
            data = bytearray()
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = px[x, y]
                    data += bytes((b * a // 255, g * a // 255, r * a // 255, a))
            data = bytes(data)
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        hdc = win32gui.GetDC(0)
        memdc = gdi32.CreateCompatibleDC(hdc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = img.width
        bmi.bmiHeader.biHeight = -img.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        ppv = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), 0, ctypes.byref(ppv), None, 0)
        old = gdi32.SelectObject(memdc, hbmp)
        ctypes.memmove(ppv, buf, len(data))
        try:
            win32gui.UpdateLayeredWindow(self.hwnd, hdc, (self.x, self.y),
                                         (img.width, img.height), memdc, (0, 0), 0,
                                         BLENDFUNCTION(0, 0, 255, 1), win32con.ULW_ALPHA)
        except Exception:
            win32gui.UpdateLayeredWindow(self.hwnd, hdc, (self.x, self.y),
                                         (img.width, img.height), memdc, (0, 0), 0,
                                         (0, 0, 255, 1), win32con.ULW_ALPHA)
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        win32gui.ReleaseDC(0, hdc)

    # ---------- 计时器 / 弹簧 / 漂移 ----------
    def _set_tick(self, ms):
        if ms != self._period:
            self._period = ms
            user32.SetTimer(self.hwnd, 1, ms, None)

    def _spring_step(self):
        a = -K_SPRING * (self.squash - self.sq_target) - C_SPRING * self.sqv
        self.sqv += a
        self.squash += self.sqv
        if abs(self.squash - self.sq_target) < 0.004 and abs(self.sqv) < 0.004:
            self.squash = self.sq_target
            self.sqv = 0.0
            return False
        return True

    def _spring_active(self):
        return (self.dragging
                or abs(self.squash - self.sq_target) > 0.004
                or abs(self.sqv) > 0.004)

    def _impulse(self, dv):
        self.sqv += dv
        self._set_tick(TICK_ANIM)

    def _bounce(self, amp=1.0, snd=True, sign=1, pop=False):
        if snd and self.sounds:
            play_sound(self.snd_press)
        if pop:
            self._pop()                 # 每次都从压扁状态弹起 → 一击一下就有效果
        else:
            self.sq_target = 0.0
            self._impulse(IMP_CLICK * amp * sign)
        self._dbg("bounce pop=%s" % pop)

    def _step_wander(self):
        wa = work_area()
        dt_s = TICK_WALK / 1000.0
        nx, ny = self.fx + self.vx * dt_s, self.fy + self.vy * dt_s
        hit = False
        if nx <= wa[0] + 4:
            nx = wa[0] + 4
            self.vx = abs(self.vx)
            hit = True
        elif nx + self.w >= wa[2] - 4:
            nx = wa[2] - 4 - self.w
            self.vx = -abs(self.vx)
            hit = True
        if ny <= wa[1] + 4:
            ny = wa[1] + 4
            self.vy = abs(self.vy)
            hit = True
        elif ny + self.h >= wa[3] - 4:
            ny = wa[3] - 4 - self.h
            self.vy = -abs(self.vy)
            hit = True
        if hit:
            a = random.uniform(-0.20, 0.20)
            ca, sa = math.cos(a), math.sin(a)
            self.vx, self.vy = self.vx * ca - self.vy * sa, self.vx * sa + self.vy * ca
        self._move_to(nx, ny)

    def _on_tick(self):
        self._tickn += 1
        now = time.time()
        need = False
        anim = False
        if self._spring_active():
            anim = self._spring_step()
            need = True
        moving = (self.wander and not self.dragging
                  and (not self.calm_mode or now >= self.still_until))
        if moving and not self._moving:
            self._init_velocity()          # 歇够了重新出发,顺便换个方向
        self._moving = moving
        if moving:
            self._step_wander()
        if now >= self.chat_until and now >= self.info_until and now >= self.override_until:
            self.chat = self._pick_chat()
            self.chat_until = now + random.uniform(22, 45)
            need = True
        if now < self.info_until and self._tickn % 20 == 0:
            need = True
        if need:
            self._redraw()
        if not self.dragging:
            self._set_tick(TICK_ANIM if anim else (TICK_WALK if moving else TICK_IDLE))

    # ---------- 余额 ----------
    def _refresh_once(self):
        key = self.pending_key or self.key
        if not key:
            self.balance, self.err = None, "未设置 API Key"
            return
        try:
            b, _cur = balance.fetch_balance(key)
            self.balance, self.err = b, ""
            self.pending_key = None
        except Exception as e:
            self.err = str(e)[:60]
            if self.pending_key:
                self.pending_key = None

    def _balance_loop(self):
        while True:
            self._refresh_once()
            time.sleep(self.refresh_sec)

    # ---------- 全屏游戏自动让位 ----------
    _FS_EXCLUDE = ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                   "SysShadow", "TaskListThumbnailWnd", "Windows.UI.Core.CoreWindow",
                   "XamlExplorerHostIslandWindow", "Windows.Internal.Shell.TabProxyWindow")

    def _fg_is_fullscreen(self):
        try:
            fg = user32.GetForegroundWindow()
        except Exception:
            return False
        if not fg or fg == getattr(self, "hwnd", 0):
            return False
        try:
            cls = win32gui.GetClassName(fg)
        except Exception:
            return False
        if cls in self._FS_EXCLUDE:
            return False
        try:
            r = win32gui.GetWindowRect(fg)
        except Exception:
            return False
        w, h = r[2] - r[0], r[3] - r[1]
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return w >= sw - 2 and h >= sh - 2 and r[0] <= 2 and r[1] <= 2

    def _fullscreen_loop(self):
        while True:
            try:
                if self.auto_hide_fs:
                    fs = self._fg_is_fullscreen()
                    if fs and not self._hidden:
                        self._hidden = True
                        if self.topmost:
                            win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                                  win32con.SWP_NOACTIVATE)
                        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
                        self._dbg("fullscreen -> hide")
                    elif not fs and self._hidden:
                        self._show_back()
                elif self._hidden:
                    self._show_back()
            except Exception:
                pass
            time.sleep(0.8)

    def _show_back(self):
        self._hidden = False
        if self.topmost:
            win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                  win32con.SWP_NOACTIVATE)
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
        self._pos_valid = False
        self._set_pos(self.fx, self.fy)
        self._redraw()
        self._dbg("fullscreen off -> show")

    # ---------- 喂文件 ----------
    def _files_eat(self, hdrop):
        n = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths = []
        for i in range(min(n, 20)):
            buf = ctypes.create_unicode_buffer(1024)
            if shell32.DragQueryFileW(hdrop, i, buf, 1024):
                paths.append(buf.value)
        shell32.DragFinish(hdrop)
        if not paths:
            return
        names = ", ".join(os.path.basename(p) for p in paths[:3])
        more = "" if len(paths) <= 3 else " 等 %d 个" % len(paths)
        where = "彻底删除(不进回收站)" if self.hard_delete else "丢进回收站(可找回)"
        tip = "要让我吃掉吗?\n\n%s%s\n\n处理方式:%s" % (names, more, where)
        if user32.MessageBoxW(0, tip, "喂给大肥鱼", 0x04 | 0x20 | 0x40000 | 0x1000) != 6:
            self.override_txt = "哼,逗人家玩呢?笨蛋。"
            self.override_until = time.time() + OVERRIDE_SECONDS
            self._redraw()
            return
        ok = recycle(paths)
        if ok and self.hard_delete:
            for p in paths:
                try:
                    if os.path.isdir(p):
                        import shutil
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                except Exception:
                    pass
        if ok:
            self.override_txt = ("咔嚓咔嚓——谢谢款待,笨蛋。" if len(paths) == 1
                                 else "咔嚓咔嚓——%d 个都吃掉了,笨蛋。" % len(paths))
            if self.sounds:
                play_sound(self.snd_eat)
            self._bounce(1.0, snd=False)
        else:
            self.override_txt = "呃……咬不动,这什么鬼东西?"
        self.override_until = time.time() + OVERRIDE_SECONDS
        self.info_until = 0.0
        self._redraw()

    # ---------- 配置应用 ----------
    def _apply_level(self):
        cx, cy = self.x + self.w // 2, self.y + self.h
        self._layout()
        self._move_to(cx - self.w // 2, cy - self.h)
        self._redraw()

    def _save_cfg(self):
        self.cfg["pos"] = [self.x, self.y]
        self.cfg["size_level"] = self.level
        self.cfg["wander"] = self.wander
        self.cfg["calm"] = self.calm_mode
        self.cfg["topmost"] = self.topmost
        self.cfg["auto_hide_fullscreen"] = self.auto_hide_fs
        self.cfg["sounds"] = self.sounds
        self.cfg["chat"] = self.show_chat
        self.cfg["hard_delete"] = self.hard_delete
        self.cfg["refresh_sec"] = self.refresh_sec
        config.save(self.cfg)

    def reload_config(self):
        """主线程里应用设置窗口写回的新配置"""
        old_key = self.key
        self.cfg = config.load()
        self.key = config.get_api_key(self.cfg)
        if self.key != old_key:
            self.balance = None
        self.refresh_sec = max(10, int(self.cfg.get("refresh_sec", 30)))
        new_level = max(0, min(len(LEVELS) - 1, int(self.cfg.get("size_level", 1))))
        self.wander = bool(self.cfg.get("wander", True))
        self.calm_mode = bool(self.cfg.get("calm", True))
        if not self.calm_mode:
            self.still_until = 0.0
        self.topmost = bool(self.cfg.get("topmost", True))
        self.auto_hide_fs = bool(self.cfg.get("auto_hide_fullscreen", True))
        self.sounds = bool(self.cfg.get("sounds", True))
        self.show_chat = bool(self.cfg.get("chat", True))
        self.hard_delete = bool(self.cfg.get("hard_delete", False))
        if new_level != self.level:
            self.level = new_level
            self._apply_level()
        self._set_pos(self.fx, self.fy)
        if not self.auto_hide_fs and self._hidden:
            self._show_back()
        self._set_tick(TICK_WALK if self.wander else TICK_IDLE)
        self._redraw()
        self._dbg("config reloaded")

    def open_settings(self):
        if self._settings_open:
            return
        self._settings_open = True

        def _done():
            self._settings_open = False
            try:
                win32gui.PostMessage(self.hwnd, WM_APP_RELOAD, 0, 0)
            except Exception:
                pass

        from . import settings_ui
        settings_ui.open_settings(self.cfg, on_close=_done)

    # ---------- 菜单 ----------
    def _menu(self):
        m = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(m, win32con.MF_STRING, 20, "设置…(填 API Key / 外观)")
        win32gui.AppendMenu(m, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(m, win32con.MF_STRING, 1, "看余额 / 峰谷")
        win32gui.AppendMenu(m, win32con.MF_STRING, 6, "弹一下")
        win32gui.AppendMenu(m, win32con.MF_STRING, 8, "换一句话")
        win32gui.AppendMenu(m, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(m, win32con.MF_STRING, 9, "别乱跑(关掉溜达)" if self.wander else "让她溜达(开启)")
        win32gui.AppendMenu(m, win32con.MF_STRING, 10, "喂文件:直接删除" if not self.hard_delete else "喂文件:丢回收站")
        win32gui.AppendMenu(m, win32con.MF_STRING, 0, "  (把文件拖到她身上=喂她)")
        win32gui.AppendMenu(m, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(m, win32con.MF_STRING, 11,
                            "窗口置顶:开 ✓ (全屏游戏自动让位)" if self.topmost
                            else "窗口置顶:关 (全屏游戏直接盖住)")
        win32gui.AppendMenu(m, win32con.MF_STRING, 7, "移到屏幕正下方")
        win32gui.AppendMenu(m, win32con.MF_STRING, 4, "变小一点" if self.level > 0 else "已是最小")
        win32gui.AppendMenu(m, win32con.MF_STRING, 5, "变大一点" if self.level < len(LEVELS) - 1 else "已是最大")
        win32gui.AppendMenu(m, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(m, win32con.MF_STRING, 3, "退出桌宠")
        p = win32gui.GetCursorPos()
        cmd = win32gui.TrackPopupMenu(m, win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
                                      p[0], p[1], 0, self.hwnd, None)
        win32gui.DestroyMenu(m)

        if cmd == 20:
            self.open_settings()
        elif cmd == 1:
            self.err = ""
            if not self.key:
                self.override_txt = "还没填 API Key 呢,笨蛋。右键→设置。"
                self.override_until = time.time() + 4
            threading.Thread(target=self._refresh_once, daemon=True).start()
            self.info_until = time.time() + INFO_SECONDS
            self._redraw()
        elif cmd == 6:
            self._bounce(1.0)
        elif cmd == 8:
            self.chat = self._pick_chat()
            self.chat_until = time.time() + random.uniform(22, 45)
            self._redraw()
        elif cmd == 9:
            self.wander = not self.wander
            self.override_txt = "哼,人家才不喜欢乱跑呢。" if not self.wander else "好耶,人家要去转转啦~"
            self.override_until = time.time() + 3
            self._set_tick(TICK_WALK if self.wander else TICK_IDLE)
            self._save_cfg()
            self._redraw()
        elif cmd == 10:
            self.hard_delete = not self.hard_delete
            self._save_cfg()
        elif cmd == 11:
            self.topmost = not self.topmost
            if self.topmost:
                win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                      win32con.SWP_NOACTIVATE)
            else:
                win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                      win32con.SWP_NOACTIVATE)
            self._save_cfg()
        elif cmd == 7:
            wa = work_area()
            self._move_to(wa[0] + (wa[2] - wa[0]) // 2 - self.w // 2, wa[3] - self.h)
            self._save_cfg()
            self._redraw()
        elif cmd == 4 and self.level > 0:
            self.level -= 1
            self._save_cfg()
            self._apply_level()
        elif cmd == 5 and self.level < len(LEVELS) - 1:
            self.level += 1
            self._save_cfg()
            self._apply_level()
        elif cmd == 3:
            self._save_cfg()
            win32gui.DestroyWindow(self.hwnd)
        if cmd:
            self._go_calm(CALM_AFTER)      # 菜单操作也算"被打扰"

    # ---------- 窗口消息 ----------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_TIMER:
            try:
                self._on_tick()
            except Exception:
                pass
            return 0
        if msg == WM_APP_RELOAD:
            try:
                self.reload_config()
            except Exception:
                pass
            return 0
        if msg == WM_APP_RELOAD + 1:
            try:
                self.open_settings()
            except Exception:
                pass
            return 0
        if msg == WM_DROPFILES:
            try:
                self._files_eat(wparam)
            except Exception:
                pass
            return 0
        if msg == win32con.WM_LBUTTONDOWN:
            self.dragging, self.moved = True, False
            self.sq_target = HOLD_STRETCH
            self.sqv = 0.0
            self._moving = False
            self._impulse(IMP_GRAB)
            cx, cy = win32gui.GetCursorPos()
            self.drag_off = (cx - self.x, cy - self.y)
            return 0
        if msg == win32con.WM_MOUSEMOVE and self.dragging:
            cx, cy = win32gui.GetCursorPos()
            nx, ny = cx - self.drag_off[0], cy - self.drag_off[1]
            if abs(nx - self.x) > 2 or abs(ny - self.y) > 2:
                self.moved = True
            nx, ny = self._clamp(nx, ny)
            spd = math.hypot(nx - self.fx, ny - self.fy)
            if spd > 0.5:
                self._impulse(-min(0.055, spd * 0.0022))
            self._move_to(nx, ny)
            tnow = time.time()
            if tnow - self._last_move_t >= 0.012:
                self._last_move_t = tnow
                self._redraw()
            return 0
        if msg == win32con.WM_LBUTTONUP:
            self.dragging = False
            self.sq_target = 0.0
            if self.moved:
                self._snap()
                self._set_pos(self.fx, self.fy)     # 吸附立刻生效,别等下次重绘才跳
                self._save_cfg()
                self.sqv += 0.02
                self._go_calm(CALM_AFTER_DRAG)      # 被抓住过 → 老实很长一段时间
            elif not self.key:
                self.override_txt = "还没填 API Key 呢,笨蛋。右键→设置。"
                self.override_until = time.time() + OVERRIDE_SECONDS
                self._go_calm(CALM_AFTER)
                self._bounce(1.0, pop=True)
                self._redraw()
                self.open_settings()
            else:
                self.info_until = time.time() + INFO_SECONDS
                self._go_calm(CALM_AFTER)
                self._bounce(1.0, pop=True)
                threading.Thread(target=self._refresh_once, daemon=True).start()
                self._redraw()
            return 0
        if msg == win32con.WM_RBUTTONUP:
            self._menu()
            return 0
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def start(self):
        threading.Thread(target=self._balance_loop, daemon=True).start()
        threading.Thread(target=self._fullscreen_loop, daemon=True).start()
        self._redraw()
        self._set_tick(TICK_WALK if self.wander else TICK_IDLE)
        if not self.cfg.get("first_run_done"):
            self.cfg["first_run_done"] = True
            self._save_cfg()
            win32gui.PostMessage(self.hwnd, WM_APP_RELOAD + 1, 0, 0)   # 首次运行:稍后弹设置
        self._dbg("start v%s" % VERSION)
        win32gui.PumpMessages()
