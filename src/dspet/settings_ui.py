# -*- coding: utf-8 -*-
"""设置窗口 —— macOS 风格自制 UI(customtkinter + 自绘控件)

设计要点
  * 去系统边框(overrideredirect)+ 圆角(Win11 走 DWM,Win10 用窗口区域裁剪兜底)
  * 自制标题栏(红黄绿三点,可拖动)
  * 卡片分组,无边框白卡 + 发丝分隔线
  * 全部控件由 PIL 超采样渲染(见 uikit.py):左右滑块开关 / 滑动条 / 分段控件 /
    输入框 / 按钮 —— 边缘丝滑、带真实柔和阴影,不再是 tkinter 手绘的锯齿货
  * 打开/关闭:淡入 + 上滑动画;开关有滑动动画;按钮有 hover/press
  * 高 DPI 与多显示器:按窗口所在屏幕的 DPI 缩放渲染
  * 小屏自动切滚动布局

数据流:打开读 config → 用户改 → 保存写盘 + 回调通知桌宠主线程重载。
"""
import os
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from . import APP_TITLE, VERSION, autostart, balance, config
from . import uikit as ui
from .paths import config_path, resource_path
from .uikit import (ACCENT, BG, BORDER, CARD, DANGER, FAINT, GREEN, LINE, SOFT,
                    SUB, TEXT)

W, H = 580, 800
LEVEL_TEXT = ["最小", "小", "中", "大", "最大"]
REFRESH_CHOICES = [10, 15, 30, 60, 120, 300]

Toggle = ui.Switch          # 兼容旧名字


def _font(size=13, bold=False):
    return ctk.CTkFont(family="Microsoft YaHei UI", size=int(round(size)),
                       weight="bold" if bold else "normal")


# ---------------- 窗口动画 ----------------
def _animate(win, x, y, alpha_to, slide_from=None, steps=14, delay=12, on_done=None):
    start_y = y + (slide_from or 0)
    try:
        start_a = float(win.attributes("-alpha"))
    except Exception:
        start_a = 1.0

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
        super().__init__(master, fg_color="transparent", height=50, corner_radius=0)
        self.win = win
        self.pack_propagate(False)

        dots = ctk.CTkFrame(self, fg_color="transparent")
        dots.pack(side="left", padx=(16, 0))
        ui.Dot(dots, 13, ui.TL_CLOSE, bg=BG, command=win._close_anim).pack(side="left")
        for c, cmd in ((ui.TL_MIN, self._minimize), (ui.TL_ZOOM, lambda: None)):
            ui.Dot(dots, 13, c, bg=BG, command=cmd).pack(side="left", padx=(8, 0))

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(side="left", expand=True)
        try:
            ico = Image.open(resource_path("DSniang1.png")).convert("RGBA")
            w0, h0 = ico.size
            ico = ico.crop((int(w0 * .19), int(h0 * .23), int(w0 * .61), int(h0 * .65)))
            ico = ico.resize((24, 24), Image.LANCZOS)
            mask = Image.new("L", (24, 24), 0)
            from PIL import ImageDraw
            ImageDraw.Draw(mask).ellipse((0, 0, 23, 23), fill=255)
            ico.putalpha(mask)
            self._ico = ctk.CTkImage(light_image=ico, size=(24, 24))
            ctk.CTkLabel(center, image=self._ico, text="").pack(side="left", padx=(0, 8))
        except Exception:
            self._ico = None
        ctk.CTkLabel(center, text="设置", font=_font(13.5, True),
                     text_color=TEXT).pack(side="left")
        ctk.CTkFrame(self, fg_color="transparent", width=88, height=1).pack(side="right")

        for widget in (self, dots, center):
            widget.bind("<Button-1>", self._press)
            widget.bind("<B1-Motion>", self._drag)

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
    """无边框白色圆角卡片 + 底下一道柔和投影 + 左上角小节标题"""

    def __init__(self, master, title, sc=1.0):
        holder = ctk.CTkFrame(master, fg_color="transparent")
        holder.pack(fill="x", padx=18, pady=(0, 12))
        if title:
            ctk.CTkLabel(holder, text=title, font=_font(10.5, True), text_color=SUB,
                         anchor="w").pack(anchor="w", padx=4, pady=(0, 6))
        super().__init__(holder, fg_color=CARD, corner_radius=12, border_width=0)
        self.pack(fill="x")
        self._strip = tk.Label(holder, bd=0, highlightthickness=0, bg=BG)
        self._strip.pack(fill="x", padx=1)
        self._strip_ph = None
        self._w_done = 0
        self.bind("<Configure>", self._on_size)

    def _on_size(self, e):
        if abs(e.width - self._w_done) < 2:
            return
        self._w_done = e.width
        img = ui.card_shadow_strip(max(8, e.width - 2))
        if img is not None:
            self._strip_ph = ImageTk.PhotoImage(img)
            self._strip.configure(image=self._strip_ph)


class SwitchCell(ctk.CTkFrame):
    """两列网格里的一格:左标题+说明,右自绘滑块"""

    def __init__(self, master, title, desc, var, sc=1.0):
        super().__init__(master, fg_color="transparent")
        self.toggle = Toggle(self, var, bg=CARD, sc=sc)
        self.toggle.pack(side="right", padx=(8, 0), pady=2)
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=title, font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        if desc:
            ctk.CTkLabel(text, text=desc, font=_font(10), text_color=FAINT,
                         anchor="w").pack(anchor="w", pady=(1, 0))


# ---------------- 主窗口 ----------------
class SettingsWindow(object):
    def __init__(self, cfg, on_close=None):
        self.cfg = dict(cfg)
        self.on_close = on_close
        self.saved = False
        self._closing = False
        self.sc = 1.0

        ctk.set_appearance_mode("light")
        self.root = ctk.CTk()
        self.root.title("%s · 设置" % APP_TITLE)
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.0)
        self.root.attributes("-topmost", True)
        self.root.configure(fg_color=BG)

        try:
            self.sc = max(1.0, min(2.0, float(self.root.winfo_fpixels("1i")) / 96.0))
        except Exception:
            self.sc = 1.0

        self._shell = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0, border_width=0)
        self._shell.pack(fill="both", expand=True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        wa_h = sh - 70
        self._x = max(8, (sw - W) // 2)
        self.root.geometry("%dx%d+%d+%d" % (W, 600, self._x, 0))

        self._titlebar = TitleBar(self._shell, self)
        self._titlebar.pack(fill="x")
        ui.hairline(self._shell, "#DFE0E6").pack(fill="x")

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
                self._shell, fg_color="transparent", corner_radius=0,
                scrollbar_button_color="#CFD1D8", scrollbar_button_hover_color="#B8BBC4")
            self._scroll.pack(fill="both", expand=True)
            return self._scroll
        f = ctk.CTkFrame(self._shell, fg_color="transparent", corner_radius=0)
        f.pack(fill="both", expand=True)
        return f

    def _build_body(self, body=None):
        body = body if body is not None else self._body_parent()
        ctk.CTkFrame(body, fg_color="transparent", height=4).pack(fill="x")
        self._api_card(body)
        self._behaviour_card(body)
        self._details_card(body)
        self._footer(body)
        return body

    def _api_card(self, body):
        card = Card(body, "DEEPSEEK 账号", self.sc)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(13, 15))

        ctk.CTkLabel(inner, text="API Key", font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text="余额功能需要你自己的 Key —— 只读接口,不消耗 token;"
                                "不填也能用,只是不显示余额",
                     font=_font(10), text_color=FAINT, anchor="w").pack(anchor="w", pady=(2, 9))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.var_key = tk.StringVar(value=config.get_api_key(self.cfg))
        self.ent = ui.Entry(row, self.var_key, bg=CARD, width=300, height=36,
                            font=_font(12), show="•", sc=self.sc)
        self.ent.pack(side="left", fill="x", expand=True)
        self._show = False
        self.btn_eye = ui.Button(row, "显示", command=self._toggle_show, bg=CARD,
                                 kind="soft", width=58, height=36, font=_font(12),
                                 sc=self.sc)
        self.btn_eye.pack(side="left", padx=(9, 0))

        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(10, 0))
        self.btn_test = ui.Button(row2, "测试连接", command=self._test, bg=CARD,
                                  kind="soft", width=96, height=32, font=_font(12),
                                  sc=self.sc)
        self.btn_test.pack(side="left")
        self.lbl_test = ctk.CTkLabel(row2, text="", font=_font(11), text_color=SUB)
        self.lbl_test.pack(side="left", padx=10)

    def _behaviour_card(self, body):
        card = Card(body, "外观与行为", self.sc)
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
        grid.pack(fill="x", padx=12, pady=12)
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")
        for i, (t, d, v) in enumerate(rows):
            cell = SwitchCell(grid, t, d, v, self.sc)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=6, pady=7)

    def _details_card(self, body):
        card = Card(body, "细节", self.sc)

        # 大小
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(row, text="大小", font=_font(12.5), text_color=TEXT, width=56,
                     anchor="w").pack(side="left")
        self.var_level = tk.IntVar(value=int(self.cfg.get("size_level", 1)))
        self.lbl_level = ctk.CTkLabel(row, text=LEVEL_TEXT[self.var_level.get()],
                                      font=_font(11), text_color=SUB, width=36)
        self.lbl_level.pack(side="right")
        self.sld_level = ui.Slider(row, 0, len(LEVEL_TEXT) - 1, self.var_level.get(),
                                   bg=CARD, command=self._on_level, steps=len(LEVEL_TEXT),
                                   width=300, sc=self.sc)
        self.sld_level.pack(side="left", fill="x", expand=True, padx=(10, 10))

        # 余额刷新
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(row2, text="余额刷新", font=_font(12.5), text_color=TEXT, width=56,
                     anchor="w").pack(side="left")
        _cur = int(self.cfg.get("refresh_sec", 30))
        _ri = min(range(len(REFRESH_CHOICES)), key=lambda i: abs(REFRESH_CHOICES[i] - _cur))
        self.var_ridx = tk.IntVar(value=_ri)
        self.var_refresh = tk.IntVar(value=REFRESH_CHOICES[_ri])
        self.lbl_refresh = ctk.CTkLabel(row2, text="%d 秒" % REFRESH_CHOICES[_ri],
                                        font=_font(11), text_color=SUB, width=36)
        self.lbl_refresh.pack(side="right")
        ui.Slider(row2, 0, len(REFRESH_CHOICES) - 1, _ri, bg=CARD,
                  command=self._on_refresh, steps=len(REFRESH_CHOICES), width=300,
                  sc=self.sc).pack(side="left", fill="x", expand=True, padx=(10, 10))

        # 喂文件
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(4, 15))
        ctk.CTkLabel(row3, text="喂文件", font=_font(12.5), text_color=TEXT, width=56,
                     anchor="w").pack(side="left")
        self.var_feed = tk.StringVar(value="彻底删除" if self.cfg.get("hard_delete")
                                     else "回收站")
        self.seg = ui.Segmented(row3, ["回收站", "彻底删除"], self.var_feed, bg=CARD,
                                command=self._on_feed, width=240, height=32,
                                font=_font(11.5), sc=self.sc)
        self.seg.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _footer(self, body):
        span = ctk.CTkFrame(body, fg_color="transparent")
        span.pack(fill="x", padx=18, pady=(2, 14))
        ui.hairline(span, "#DFE0E6").pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(span, text="配置:%s" % config_path(), font=_font(10),
                     text_color="#B0B2B8", anchor="w").pack(anchor="w")
        row = ctk.CTkFrame(span, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ui.Button(row, "关于", command=self._about, bg=BG, kind="ghost", width=68,
                  height=34, font=_font(12), text_color=SUB, sc=self.sc).pack(side="left")
        self.btn_save = ui.Button(row, "保存并应用", command=self._save, bg=BG,
                                  kind="primary", width=130, height=34,
                                  font=_font(12, True), sc=self.sc)
        self.btn_save.pack(side="right")
        ui.Button(row, "取消", command=self._close_anim, bg=BG, kind="soft", width=80,
                  height=34, font=_font(12), sc=self.sc).pack(side="right", padx=(0, 9))

    # ---------- 适配 ----------
    def _round_corners(self):
        """Win11 → DWM 真圆角;Win10(DWM 不支持)→ 用窗口区域裁剪兜底"""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or \
                self.root.winfo_id()
            pref = ctypes.c_int(2)                      # DWMWCP_ROUND
            hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            if hr != 0:
                r = int(14 * self.sc)
                rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, W + 1, self.h + 1,
                                                             r, r)
                ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
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
        self.ent.set_show("" if self._show else "•")
        self.btn_eye.set_text("隐藏" if self._show else "显示")

    def _on_level(self, v):
        self.var_level.set(int(v))
        self.lbl_level.configure(text=LEVEL_TEXT[max(0, min(len(LEVEL_TEXT) - 1, int(v)))])

    def _on_refresh(self, i):
        i = max(0, min(len(REFRESH_CHOICES) - 1, int(i)))
        self.var_ridx.set(i)
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
        top.geometry("430x310")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.configure(fg_color=BG)
        f = ctk.CTkFrame(top, fg_color=CARD, corner_radius=12, border_width=0)
        f.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(f, text="%s  v%s" % (APP_TITLE, VERSION), font=_font(15, True),
                     text_color=TEXT).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            f, justify="left", font=_font(11), text_color=SUB,
            text=("一只趴在桌面上的余额挂件,纯本地运行;\n"
                  "只有查余额时会连一次 DeepSeek 官方只读接口。\n\n"
                  "美术素材:大肥鱼 - 余额挂件 v0.3.0\n"
                  "  © @月匠 / MeteorNOX(MIT License)\n"
                  "参考:whale-purse © Suiwan(MIT License)\n"
                  "本程序:MIT License,可自由分享。")
        ).pack(anchor="w", padx=18)
        ui.Button(f, "好的", command=top.destroy, bg=CARD, kind="primary", width=92,
                  height=32, font=_font(12), sc=self.sc).pack(pady=14)

    def _save(self):
        cfg = dict(self.cfg)
        cfg["size_level"] = int(self.var_level.get())
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
        self.btn_save.set_kind("success")
        self.btn_save.set_text("✓ 已保存")
        self.root.after(420, self._close_anim)

    # ---------- 生命周期 ----------
    def _close_anim(self):
        if self._closing:
            return
        self._closing = True
        _animate(self.root, self._x, self._y, 0.0, slide_from=16, steps=10, delay=11,
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
            self.ent.entry.focus_set()
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
