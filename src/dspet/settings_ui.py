# -*- coding: utf-8 -*-
"""设置窗口 —— macOS 风格自制 UI(customtkinter)

设计要点
  * 去系统边框(overrideredirect)+ Win11 DWM 圆角 + 自制标题栏(红黄绿三点,可拖动)
  * 卡片分组 + 右侧自绘"左右滑块"开关(带平滑动画,绿=开)
  * 打开/关闭都是"淡入 + 上滑"动画;保存按钮有 ✓ 反馈
  * 小屏自动切滚动布局;高 DPI 交给 customtkinter 做缩放

数据流:打开读 config → 用户改 → 保存写盘 + 回调通知桌宠主线程重载。
"""
import math
import os
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from . import APP_TITLE, VERSION, autostart, balance, config
from .paths import config_path, resource_path

# ---------------- 配色(macOS 浅色) ----------------
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
TRACK_OFF = "#DCDDE3"
LINE = "#EDEEF2"
BORDER = "#DFE1E6"

W, H = 580, 800
LEVEL_TEXT = ["最小", "小", "中", "大", "最大"]
REFRESH_CHOICES = [10, 15, 30, 60, 120, 300]


def _font(size=13, bold=False):
    return ctk.CTkFont(family="Microsoft YaHei UI", size=int(round(size)),
                       weight="bold" if bold else "normal")


def _mix(c1, c2, k):
    """两个 #rrggbb 按 k 混合(k=0 → c1)"""
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


# ---------------- 自绘开关(macOS 风,滑动动画) ----------------
class Toggle(tk.Canvas):
    SW, SH = 46, 26

    def __init__(self, master, variable, bg=CARD, command=None):
        super().__init__(master, width=self.SW, height=self.SH, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.command = command
        self._t = 1.0 if variable.get() else 0.0
        self._target = self._t
        self._anim = False
        self.bind("<Button-1>", self.toggle)
        self.bind("<Configure>", lambda e: self._draw())
        try:
            self.var.trace_add("write", lambda *a: self._sync())
        except Exception:
            pass
        self._draw()

    # --- 对外 ---
    def toggle(self, _e=None):
        self.var.set(not bool(self.var.get()))
        if self.command:
            self.command(bool(self.var.get()))

    def _sync(self):
        want = 1.0 if self.var.get() else 0.0
        if abs(want - self._target) < 0.001:
            return
        self._start = self._t                       # 从当前位置接着走(连点也顺滑)
        self._target = want
        if not self._anim:
            self._anim = True
            self._animate(0, 12)

    def _animate(self, i, total):
        k = min(1.0, i / float(max(1, total)))
        ease = 0.5 - 0.5 * math.cos(math.pi * k)    # easeInOutSine
        self._t = self._start + (self._target - self._start) * ease
        self._draw()
        if k < 1.0:
            self.after(12, lambda: self._animate(i + 1, total))
        else:
            self._t = self._target
            self._draw()
            self._anim = False
            self._sync()

    # --- 绘制 ---
    def _rr(self, x0, y0, x1, y1, r, fill, outline=""):
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=fill, outline=outline)
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=fill, outline=outline)
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=outline)

    def _draw(self):
        self.delete("all")
        t = self._t
        w, h = self.SW, self.SH
        track = _mix(TRACK_OFF, GREEN, t)
        self._rr(1, 1, w - 1, h - 1, (h - 2) // 2, track)
        # 旋钮
        pad = 3
        d = h - 2 * pad
        x0 = pad + t * (w - 2 * pad - d)
        self.create_oval(x0 + 1, pad + 1.5, x0 + d + 1, pad + d + 1.5,
                         fill="#D3D5DB", outline="")
        self.create_oval(x0, pad, x0 + d, pad + d, fill="#FFFFFF", outline="#D9DBE1")


# ---------------- 分段控件(macOS 风,选中=蓝底白字) ----------------
class Segmented(ctk.CTkFrame):
    def __init__(self, master, values, variable, command=None, width=250, height=30,
                 font=None):
        super().__init__(master, fg_color="#F0F1F4", corner_radius=9,
                         width=width, height=height)
        self.pack_propagate(False)
        self.values = list(values)
        self.var = variable
        self.command = command
        self._font = font or _font(11)
        self._btns = []
        for i, v in enumerate(self.values):
            b = ctk.CTkButton(self, text=v, font=self._font, corner_radius=7,
                              fg_color="transparent", hover_color="#E4E6EA",
                              text_color=TEXT, border_width=0,
                              command=lambda i=i: self.select(self.values[i]))
            b.pack(side="left", fill="both", expand=True, padx=(3 if i == 0 else 2,
                                                                3 if i == len(self.values) - 1 else 2),
                    pady=3)
            self._btns.append(b)
        var_value = self.var.get()
        if isinstance(var_value, int) and not isinstance(var_value, bool):
            self.select(self.values[var_value] if var_value < len(self.values) else self.values[0])
        else:
            self.select(self.values[0] if var_value not in self.values else var_value)

    def select(self, value):
        self.var.set(value)
        for b, v in zip(self._btns, self.values):
            if v == value:
                b.configure(fg_color=ACCENT, hover_color=ACCENT, text_color="#FFFFFF")
            else:
                b.configure(fg_color="transparent", hover_color="#E4E6EA", text_color=TEXT)
        if self.command:
            self.command(value)


# ---------------- 窗口动画 ----------------
def _animate(win, x, y, alpha_to, slide_from=None, steps=13, delay=13, on_done=None):
    start_y = y + (slide_from or 0)
    start_a = float(win.attributes("-alpha"))

    def step(i):
        k = i / float(steps)
        ease = 1 - (1 - k) ** 3
        try:
            win.attributes("-alpha", start_a + (alpha_to - start_a) * ease)
            win.geometry("+%d+%d" % (x, int(start_y + (y - start_y) * ease)))
        except Exception:
            return
        if i < steps:
            win.after(delay, lambda: step(i + 1))
        elif on_done:
            on_done()

    step(1)


# ---------------- 标题栏 ----------------
class TitleBar(ctk.CTkFrame):
    def __init__(self, master, win):
        super().__init__(master, fg_color="transparent", height=50)
        self.win = win
        self.pack_propagate(False)

        dots = ctk.CTkFrame(self, fg_color="transparent")
        dots.pack(side="left", padx=(14, 0))
        self._dot(dots, TL_CLOSE, lambda: win._close_anim())
        self._dot(dots, TL_MIN, self._minimize)
        self._dot(dots, TL_ZOOM, lambda: None)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(side="left", expand=True)
        try:
            ico = Image.open(resource_path("DSniang1.png")).convert("RGBA")
            w0, h0 = ico.size
            # 抓她的脸当标题栏图标
            ico = ico.crop((int(w0 * .19), int(h0 * .23), int(w0 * .61), int(h0 * .65)))
            ico = ico.resize((22, 22), Image.LANCZOS)
            self._ico = ctk.CTkImage(light_image=ico, size=(22, 22))
            ctk.CTkLabel(center, image=self._ico, text="").pack(side="left", padx=(0, 8))
        except Exception:
            self._ico = None
        ctk.CTkLabel(center, text="设置", font=_font(13, True), text_color=TEXT).pack(side="left")

        ctk.CTkFrame(self, fg_color="transparent", width=78, height=1).pack(side="right")

        for widget in (self, dots, center):
            widget.bind("<Button-1>", self._press)
            widget.bind("<B1-Motion>", self._drag)

    def _dot(self, parent, color, cmd):
        b = ctk.CTkButton(parent, width=13, height=13, corner_radius=7, text="",
                          fg_color=color, hover_color=color, border_width=0, command=cmd)
        b.pack(side="left", padx=4)
        return b

    def _press(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.win.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def _minimize(self):
        try:
            self.win.overrideredirect(False)
            self.win.iconify()
        except Exception:
            pass


# ---------------- 卡片 ----------------
class Card(ctk.CTkFrame):
    def __init__(self, master, title):
        holder = ctk.CTkFrame(master, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(0, 14))
        if title:
            ctk.CTkLabel(holder, text=title, font=_font(11, True), text_color=SUB,
                         anchor="w").pack(anchor="w", padx=4, pady=(0, 6))
        super().__init__(holder, fg_color=CARD, corner_radius=13, border_width=1,
                         border_color=BORDER)
        self.pack(fill="x")


class SwitchCell(ctk.CTkFrame):
    """两列网格里的一格:左标题+说明,右自绘滑块"""

    def __init__(self, master, title, desc, var):
        super().__init__(master, fg_color="transparent")
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=title, font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        if desc:
            ctk.CTkLabel(text, text=desc, font=_font(10), text_color=FAINT,
                         anchor="w").pack(anchor="w")
        self.toggle = Toggle(self, var)
        self.toggle.pack(side="right", padx=(6, 0))


# ---------------- 主窗口 ----------------
class SettingsWindow(object):
    def __init__(self, cfg, on_close=None):
        self.cfg = dict(cfg)
        self.on_close = on_close
        self.saved = False
        self._closing = False

        ctk.set_appearance_mode("light")
        self.root = ctk.CTk()
        self.root.title("%s · 设置" % APP_TITLE)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.0)
        self.root.attributes("-topmost", True)

        self._shell = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0, border_width=0)
        self._shell.pack(fill="both", expand=True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        wa_h = sh - 60
        self._x = max(8, (sw - W) // 2)
        self.root.geometry("%dx%d+%d+%d" % (W, 600, self._x, 0))

        self._titlebar = TitleBar(self._shell, self)
        self._titlebar.pack(fill="x")

        # 先按"不滚动"排一遍,量出真实需要的高度;放不下再切换成滚动布局(适配小屏)
        self.compact = False
        body = self._body_parent()
        self._build_body(body)
        self.root.update_idletasks()
        need = self.root.winfo_reqheight()
        if need > wa_h:
            body.destroy()
            self.compact = True
            body = self._body_parent()
            self._build_body(body)
            self.root.update_idletasks()
            need = wa_h
        self.h = int(min(need, wa_h))
        self._size = (W, self.h)
        self._y = max(12, (sh - self.h) // 2 - 26)
        self.root.geometry("%dx%d+%d+%d" % (W, self.h, self._x, self._y))
        self.root.update_idletasks()
        self._round_corners()
        self._bind_keys()

    # ---------- 布局 ----------
    def _body_parent(self):
        if self.compact:
            self._scroll = ctk.CTkScrollableFrame(
                self._shell, fg_color="transparent",
                scrollbar_button_color="#CFD1D8", scrollbar_button_hover_color="#B8BBC4")
            self._scroll.pack(fill="both", expand=True)
            return self._scroll
        f = ctk.CTkFrame(self._shell, fg_color="transparent")
        f.pack(fill="both", expand=True)
        return f

    def _build_body(self, body=None):
        body = body if body is not None else self._body_parent()
        self._api_card(body)
        self._behaviour_card(body)
        self._details_card(body)
        self._footer(body)
        return body

    def _api_card(self, body):
        card = Card(body, "DEEPSEEK 账号")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=(12, 14))

        ctk.CTkLabel(inner, text="API Key", font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text="余额功能需要你自己的 Key —— 只读接口,不消耗 token;不填也能用,只是不显示余额",
                     font=_font(10), text_color=FAINT, anchor="w").pack(anchor="w", pady=(1, 8))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.var_key = tk.StringVar(value=config.get_api_key(self.cfg))
        self.ent = ctk.CTkEntry(row, textvariable=self.var_key, show="•", height=34,
                                corner_radius=9, border_color=BORDER, fg_color="#F7F7F9",
                                text_color=TEXT, font=_font(12), placeholder_text="sk-...")
        self.ent.pack(side="left", fill="x", expand=True)
        self._show = False
        self.btn_eye = ctk.CTkButton(row, text="显示", width=56, height=34, corner_radius=9,
                                     fg_color="#F0F1F4", hover_color="#E3E5EA",
                                     text_color=TEXT, font=_font(12), command=self._toggle_show)
        self.btn_eye.pack(side="left", padx=(8, 0))

        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(9, 0))
        self.btn_test = ctk.CTkButton(row2, text="测试连接", width=92, height=32,
                                      corner_radius=9, fg_color="#F0F1F4",
                                      hover_color="#E3E5EA", text_color=TEXT,
                                      font=_font(12), command=self._test)
        self.btn_test.pack(side="left")
        self.lbl_test = ctk.CTkLabel(row2, text="", font=_font(11), text_color=SUB)
        self.lbl_test.pack(side="left", padx=10)

    def _behaviour_card(self, body):
        card = Card(body, "外观与行为")
        self.var_wander = tk.BooleanVar(value=bool(self.cfg.get("wander", True)))
        self.var_calm = tk.BooleanVar(value=bool(self.cfg.get("calm", True)))
        self.var_top = tk.BooleanVar(value=bool(self.cfg.get("topmost", True)))
        self.var_hide = tk.BooleanVar(value=bool(self.cfg.get("auto_hide_fullscreen", True)))
        self.var_snd = tk.BooleanVar(value=bool(self.cfg.get("sounds", True)))
        self.var_chat = tk.BooleanVar(value=bool(self.cfg.get("chat", True)))
        self.var_auto = tk.BooleanVar(value=autostart.is_enabled())

        rows = [
            ("自主溜达", "没事时自己飘来飘去", self.var_wander),
            ("安静模式", "冷落一会儿才溜达", self.var_calm),
            ("窗口置顶", "压在其他窗口上面", self.var_top),
            ("全屏游戏让位", "游戏一开就自动躲开", self.var_hide),
            ("音效", "点击/拖拽时的语音", self.var_snd),
            ("碎嘴台词", "气泡里自言自语", self.var_chat),
            ("开机自启", "登录 Windows 后出现", self.var_auto),
        ]
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=10)
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")
        for i, (t, d, v) in enumerate(rows):
            cell = SwitchCell(grid, t, d, v)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=6, pady=6)

    def _details_card(self, body):
        card = Card(body, "细节")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(row, text="大小", font=_font(12.5), text_color=TEXT, width=60,
                     anchor="w").pack(side="left")
        self.var_level = tk.IntVar(value=int(self.cfg.get("size_level", 1)))
        self.lbl_level = ctk.CTkLabel(row, text=LEVEL_TEXT[self.var_level.get()],
                                      font=_font(11), text_color=SUB, width=40)
        self.lbl_level.pack(side="right")
        ctk.CTkSlider(row, from_=0, to=len(LEVEL_TEXT) - 1, number_of_steps=4,
                      variable=self.var_level, height=14, button_length=17,
                      corner_radius=8, progress_color=ACCENT, button_color="#FFFFFF",
                      button_hover_color="#EFF0F3", fg_color=TRACK_OFF,
                      command=self._on_level).pack(side="left", fill="x", expand=True, padx=10)

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkLabel(row2, text="余额刷新", font=_font(12.5), text_color=TEXT, width=60,
                     anchor="w").pack(side="left")
        _cur = int(self.cfg.get("refresh_sec", 30))
        _ri = min(range(len(REFRESH_CHOICES)), key=lambda i: abs(REFRESH_CHOICES[i] - _cur))
        self.var_refresh = tk.IntVar(value=REFRESH_CHOICES[_ri])
        self.var_ridx = tk.IntVar(value=_ri)
        self.lbl_refresh = ctk.CTkLabel(row2, text="%d 秒" % REFRESH_CHOICES[_ri],
                                        font=_font(11), text_color=SUB, width=40)
        self.lbl_refresh.pack(side="right")
        ctk.CTkSlider(row2, from_=0, to=len(REFRESH_CHOICES) - 1,
                      number_of_steps=len(REFRESH_CHOICES) - 1, variable=self.var_ridx,
                      height=14, button_length=17, corner_radius=8, progress_color=ACCENT,
                      button_color="#FFFFFF", button_hover_color="#EFF0F3",
                      fg_color=TRACK_OFF,
                      command=self._on_refresh).pack(side="left", fill="x", expand=True, padx=10)

        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(6, 14))
        ctk.CTkLabel(row3, text="喂文件", font=_font(12.5), text_color=TEXT, width=60,
                     anchor="w").pack(side="left")
        self.var_feed = tk.StringVar(value="彻底删除" if self.cfg.get("hard_delete") else "回收站")
        self.seg = Segmented(row3, ["回收站", "彻底删除"], self.var_feed,
                             command=self._on_feed)
        self.seg.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _footer(self, body):
        span = ctk.CTkFrame(body, fg_color="transparent")
        span.pack(fill="x", padx=18, pady=(2, 14))
        ctk.CTkLabel(span, text="配置:%s" % config_path(), font=_font(10),
                     text_color="#B0B2B8", anchor="w").pack(anchor="w")
        row = ctk.CTkFrame(span, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(row, text="关于", width=64, height=34, corner_radius=10,
                      fg_color="transparent", hover_color="#E3E5EA", text_color=SUB,
                      font=_font(12), command=self._about).pack(side="left")
        self.btn_save = ctk.CTkButton(row, text="保存并应用", width=126, height=34,
                                      corner_radius=10, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER, text_color="#FFFFFF",
                                      font=_font(12, True), command=self._save)
        self.btn_save.pack(side="right")
        ctk.CTkButton(row, text="取消", width=78, height=34, corner_radius=10,
                      fg_color="#F0F1F4", hover_color="#E3E5EA", text_color=TEXT,
                      font=_font(12), command=self._close_anim).pack(side="right", padx=(0, 8))

    # ---------- 适配 ----------
    def _round_corners(self):
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            pref = ctypes.c_int(2)                      # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref),
                                                       ctypes.sizeof(pref))
        except Exception:
            pass

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self._close_anim())
        self.root.bind("<Map>", self._on_map)

    def _on_map(self, _e=None):
        try:
            if not self.root.overrideredirect():
                self.root.overrideredirect(True)
        except Exception:
            pass

    # ---------- 交互 ----------
    def _toggle_show(self):
        self._show = not self._show
        self.ent.configure(show="" if self._show else "•")
        self.btn_eye.configure(text="隐藏" if self._show else "显示")

    def _on_level(self, _v=None):
        self.lbl_level.configure(text=LEVEL_TEXT[int(float(self.var_level.get()))])

    def _on_refresh(self, _v=None):
        i = int(float(self.var_ridx.get()))
        self.var_refresh.set(REFRESH_CHOICES[i])
        self.lbl_refresh.configure(text="%d 秒" % REFRESH_CHOICES[i])

    def _on_feed(self, value=None):
        self.var_feed.set("彻底删除" if value == "彻底删除" else "回收站")

    def _test(self):
        key = self.var_key.get().strip()
        if not key:
            self.lbl_test.configure(text="先填个 Key 吧", text_color=DANGER)
            return
        self.lbl_test.configure(text="测试中…", text_color=SUB)

        def _work():
            try:
                v, cur = balance.fetch_balance(key)
                msg, col = "✓ 连接成功 · 余额 %.2f %s" % (v, cur), GREEN
            except Exception as e:
                msg, col = "✗ " + str(e), DANGER
            try:
                self.root.after(0, lambda: self.lbl_test.configure(text=msg, text_color=col))
            except Exception:
                pass

        threading.Thread(target=_work, daemon=True).start()

    def _about(self):
        top = ctk.CTkToplevel(self.root)
        top.title("关于")
        top.geometry("430x306")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.configure(fg_color=BG)
        f = ctk.CTkFrame(top, fg_color=CARD, corner_radius=13, border_width=1,
                         border_color=BORDER)
        f.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(f, text="%s  v%s" % (APP_TITLE, VERSION), font=_font(15, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            f, justify="left", font=_font(11), text_color=SUB,
            text=("一只趴在桌面上的余额挂件,纯本地运行;\n"
                  "只有查余额时会连一次 DeepSeek 官方只读接口。\n\n"
                  "美术素材:大肥鱼 - 余额挂件 v0.3.0\n"
                  "  © @月匠 / MeteorNOX(MIT License)\n"
                  "参考:whale-purse © Suiwan(MIT License)\n"
                  "本程序:MIT License,可自由分享。")
        ).pack(anchor="w", padx=16)
        ctk.CTkButton(f, text="好的", width=88, height=32, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=_font(12),
                      command=top.destroy).pack(pady=14)

    def _save(self):
        cfg = dict(self.cfg)
        cfg["size_level"] = int(float(self.var_level.get()))
        cfg["wander"] = bool(self.var_wander.get())
        cfg["calm"] = bool(self.var_calm.get())
        cfg["topmost"] = bool(self.var_top.get())
        cfg["auto_hide_fullscreen"] = bool(self.var_hide.get())
        cfg["sounds"] = bool(self.var_snd.get())
        cfg["chat"] = bool(self.var_chat.get())
        cfg["hard_delete"] = (self.var_feed.get() == "彻底删除")
        cfg["refresh_sec"] = max(10, int(self.var_refresh.get()))
        old_key = config.get_api_key(cfg)
        new_key = self.var_key.get().strip()
        if new_key != old_key:
            config.set_api_key(cfg, new_key)
        cfg["autostart"] = bool(self.var_auto.get())
        config.save(cfg)
        autostart.apply(cfg["autostart"])
        self.saved = True
        self.btn_save.configure(text="✓ 已保存", fg_color=GREEN, hover_color=GREEN)
        self.root.after(380, self._close_anim)

    # ---------- 生命周期 ----------
    def _close_anim(self):
        if self._closing:
            return
        self._closing = True
        _animate(self.root, self._x, self._y, 0.0, slide_from=14, steps=9, delay=12,
                 on_done=self._destroy)

    def _destroy(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

    def run(self):
        self.root.after(30, lambda: _animate(self.root, self._x, self._y, 1.0,
                                             slide_from=26, on_done=self._focus))
        self.root.mainloop()

    def _focus(self):
        try:
            self.root.focus_force()
            self.ent.focus_set()
        except Exception:
            pass


def open_settings(cfg, on_close=None):
    """在独立线程里开设置窗口(不阻塞桌宠的消息循环)"""
    def _go():
        try:
            SettingsWindow(cfg, on_close).run()
        except Exception:
            if on_close:
                on_close()
    th = threading.Thread(target=_go, daemon=True)
    th.start()
    return th
