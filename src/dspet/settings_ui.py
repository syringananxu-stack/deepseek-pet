# -*- coding: utf-8 -*-
"""设置窗口 —— 自制精致 UI(customtkinter + PIL 自绘控件)

设计要点
  * **正经 Windows 窗口**:用系统标题栏/边框(能拖、能最小化、能关),**不置顶**
    —— 只有桌宠置顶;设置窗是普通窗口,该被盖住就被盖住。
  * 标题栏染成跟内容一致的颜色(Win11 的 DWMWA_CAPTION_COLOR;Win10 忽略也不难看)
  * 卡片分组,无边框白卡 + 底部柔和投影
  * 全部控件由 PIL 超采样渲染(见 uikit.py):左右滑块开关 / 滑动条 / 分段控件 /
    输入框 / 按钮 —— 边缘丝滑、带真实柔和阴影,不再是 tkinter 手绘的锯齿货
  * 打开/关闭:淡入 + 上滑动画;开关有滑动动画;按钮有 hover/press
  * 高 DPI 与多显示器:按窗口所在屏幕的 DPI 缩放渲染
  * 小屏自动切滚动布局

数据流:打开读 config → 用户改 → 保存写盘 + 回调通知桌宠主线程重载。
"""
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import ImageTk

from . import APP_TITLE, VERSION, autostart, balance, config
from . import uikit as ui
from .paths import config_path
from .uikit import (ACCENT, BG, BORDER, CARD, DANGER, FAINT, GREEN, LINE, SOFT,
                    SUB, TEXT)

W, H = 580, 800
_SESSION = {}
_QUEUE = []
_LOCK = threading.Lock()
LEVEL_TEXT = ["最小", "小", "中", "大", "最大"]
REFRESH_CHOICES = [10, 15, 30, 60, 120, 300]

# 设置界面大小:小 / 中 / 大(三档,只在设置里调)
# ⚠️ 东家定调:三档**只改内容区宽度**(窄一点行就挤/换行),**字号和控件大小一律不变**
UI_WIDTHS = [470, 580, 700]
UI_SCALE_TEXT = ["小", "中", "大"]
_UIK = [1.0]                # 保留但恒为 1.0:字号/间距不再随档位缩放

Toggle = ui.Switch          # 兼容旧名字


def _font(size=13, bold=False):
    return ctk.CTkFont(family="Microsoft YaHei UI",
                       size=max(7, int(round(size))),
                       weight="bold" if bold else "normal")


def _p(n):
    """间距/尺寸(不随档位变;留着这个名字是为了少改调用点)"""
    return int(n)


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
        return

    step(1)


# ---------------- 卡片 ----------------
class Card(ctk.CTkFrame):
    """无边框白色圆角卡片 + 底下一道柔和投影 + 左上角小节标题"""

    def __init__(self, master, title, sc=1.0):
        k = _UIK[0]
        holder = ctk.CTkFrame(master, fg_color="transparent")
        holder.pack(fill="x", padx=int(round(18 * k)), pady=(0, int(round(12 * k))))
        if title:
            ctk.CTkLabel(holder, text=title, font=_font(10.5, True), text_color=SUB,
                         anchor="w").pack(anchor="w", padx=4, pady=(0, int(round(6 * k))))
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
        self.toggle.pack(side="right", padx=(_p(8), 0), pady=_p(2))
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=title, font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        if desc:
            ctk.CTkLabel(text, text=desc, font=_font(10), text_color=FAINT,
                         anchor="w").pack(anchor="w", pady=(_p(1), 0))


# ---------------- 主窗口 ----------------
class SettingsWindow(object):
    def __init__(self, cfg, on_close=None, root=None):
        self.cfg = dict(cfg)
        self.on_close = on_close
        self.saved = False
        self._closing = False
        self._hidden = False
        self._rebuilding = False
        self.sc = 1.0

        # 界面大小(小/中/大)—— 必须在建任何控件之前设好
        self.ui_level = max(0, min(len(UI_WIDTHS) - 1, int(self.cfg.get("ui_scale", 1))))

        ctk.set_appearance_mode("light")
        # ⚠️ root 由外面传进来(一个进程只建一次):customtkinter 的 ScalingTracker 是
        #    单例、绑死第一个 root,destroy 之后再建新 root 必炸 → 所以关了只是隐藏
        self.root = root if root is not None else ctk.CTk()
        self.root.title("设置 — %s" % APP_TITLE)
        # ⚠️ 正经 Windows 窗口:系统标题栏(能拖、能最小化、能关),**不置顶**
        self.root.resizable(False, False)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(fg_color=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._close_anim)

        try:
            self.sc = max(0.75, min(2.4, float(self.root.winfo_fpixels("1i")) / 96.0))
        except Exception:
            self.sc = 1.0

        self._shell = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0, border_width=0)
        self._shell.pack(fill="both", expand=True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self._sw, self._sh = sw, sh
        self._x = max(8, (sw - self._ww()) // 2)
        self.root.geometry("%dx%d+%d+%d" % (self._ww(), min(760, self._sh - 160),
                                           self._x, 0))

        self.compact = False
        self._foot_host = None
        self._layout_all()
        self._style_titlebar()
        self._bind_keys()

    # ---------- 尺寸 / 缩放 ----------
    def _ww(self):
        """窗口内容区宽度 —— 三档只改这里,字号/控件大小一律不变"""
        return UI_WIDTHS[self.ui_level]

    def _wa_h(self):
        return self._sh - 120

    def _layout_all(self):
        """(重)建全部控件 + 定尺寸。换界面大小档位时直接重跑这个(不重建 root:
        customtkinter 的 ScalingTracker 是单例,root 重建会炸)"""
        for ch in self._shell.winfo_children():
            ch.destroy()
        self.compact = False
        # 底栏固定在窗口底部(两种布局都如此):保存/取消永远可见
        self._foot_host = ctk.CTkFrame(self._shell, fg_color=BG, corner_radius=0)
        self._foot_host.pack(side="bottom", fill="x")
        body = self._body_parent()
        self._build_body(body)
        self.root.update_idletasks()
        need = self.root.winfo_reqheight()
        if need > self._wa_h():
            body.destroy()
            self.compact = True
            body = self._body_parent()
            self._build_body(body, with_footer=False)     # 底栏已经建好了,别重复
            self.root.update_idletasks()
            need = self._wa_h()
        self.h = int(min(need, self._wa_h()))
        self._size = (self._ww(), self.h)
        self._y = max(12, (self._sh - self.h) // 2 - 26)
        self.root.geometry("%dx%d+%d+%d" % (self._ww(), self.h, self._x, self._y))
        self.root.update_idletasks()

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

    def _build_body(self, body=None, with_footer=True):
        body = body if body is not None else self._body_parent()
        ctk.CTkFrame(body, fg_color="transparent", height=_p(12)).pack(fill="x")
        self._api_card(body)
        self._behaviour_card(body)
        self._details_card(body)
        if with_footer:
            self._footer(self._foot_host)
        return body

    def _api_card(self, body):
        card = Card(body, "DEEPSEEK 账号", self.sc)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=_p(16), pady=(_p(13), _p(15)))

        ctk.CTkLabel(inner, text="API Key", font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text="余额功能需要你自己的 Key —— 只读接口,不消耗 token;"
                                "不填也能用,只是不显示余额",
                     font=_font(10), text_color=FAINT, anchor="w").pack(
                         anchor="w", pady=(_p(2), _p(9)))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.var_key = tk.StringVar(value=config.get_api_key(self.cfg))
        self.ent = ui.Entry(row, self.var_key, bg=CARD, width=300, height=36,
                            font=_font(12), show="•", sc=self.sc)
        self.ent.on_submit = self._save            # 输入框里回车 = 保存并应用
        self.ent.pack(side="left", fill="x", expand=True)
        self._show = False
        self.btn_eye = ui.Button(row, "显示", command=self._toggle_show, bg=CARD,
                                 kind="soft", width=58, height=36, font=_font(12),
                                 sc=self.sc)
        self.btn_eye.pack(side="left", padx=(_p(9), 0))

        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(_p(10), 0))
        self.btn_test = ui.Button(row2, "测试连接", command=self._test, bg=CARD,
                                  kind="soft", width=96, height=32, font=_font(12),
                                  sc=self.sc)
        self.btn_test.pack(side="left")
        self.lbl_test = ctk.CTkLabel(row2, text="", font=_font(11), text_color=SUB)
        self.lbl_test.pack(side="left", padx=_p(10))

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
        grid.pack(fill="x", padx=_p(12), pady=_p(12))
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")
        for i, (t, d, v) in enumerate(rows):
            cell = SwitchCell(grid, t, d, v, self.sc)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=_p(6), pady=_p(7))

    def _details_card(self, body):
        card = Card(body, "细节", self.sc)

        # 大小
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=_p(16), pady=(_p(14), _p(4)))
        ctk.CTkLabel(row, text="大小", font=_font(12.5), text_color=TEXT, width=_p(56),
                     anchor="w").pack(side="left")
        self.var_level = tk.IntVar(value=int(self.cfg.get("size_level", 1)))
        self.lbl_level = ctk.CTkLabel(row, text=LEVEL_TEXT[self.var_level.get()],
                                      font=_font(11), text_color=SUB, width=_p(36))
        self.lbl_level.pack(side="right")
        self.sld_level = ui.Slider(row, 0, len(LEVEL_TEXT) - 1, self.var_level.get(),
                                   bg=CARD, command=self._on_level, steps=len(LEVEL_TEXT),
                                   width=300, sc=self.sc)
        self.sld_level.pack(side="left", fill="x", expand=True, padx=(_p(10), _p(10)))

        # 余额刷新
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=_p(16), pady=(_p(4), _p(4)))
        ctk.CTkLabel(row2, text="余额刷新", font=_font(12.5), text_color=TEXT, width=_p(56),
                     anchor="w").pack(side="left")
        _cur = int(self.cfg.get("refresh_sec", 30))
        _ri = min(range(len(REFRESH_CHOICES)), key=lambda i: abs(REFRESH_CHOICES[i] - _cur))
        self.var_ridx = tk.IntVar(value=_ri)
        self.var_refresh = tk.IntVar(value=REFRESH_CHOICES[_ri])
        self.lbl_refresh = ctk.CTkLabel(row2, text="%d 秒" % REFRESH_CHOICES[_ri],
                                        font=_font(11), text_color=SUB, width=_p(36))
        self.lbl_refresh.pack(side="right")
        ui.Slider(row2, 0, len(REFRESH_CHOICES) - 1, _ri, bg=CARD,
                  command=self._on_refresh, steps=len(REFRESH_CHOICES), width=300,
                  sc=self.sc).pack(side="left", fill="x", expand=True, padx=(_p(10), _p(10)))

        # 喂文件
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=_p(16), pady=(_p(4), _p(4)))
        ctk.CTkLabel(row3, text="喂文件", font=_font(12.5), text_color=TEXT, width=_p(56),
                     anchor="w").pack(side="left")
        self.var_feed = tk.StringVar(value="彻底删除" if self.cfg.get("hard_delete")
                                     else "回收站")
        self.seg = ui.Segmented(row3, ["回收站", "彻底删除"], self.var_feed, bg=CARD,
                                command=self._on_feed, width=240, height=32,
                                font=_font(11.5), sc=self.sc)
        self.seg.pack(side="right", fill="x", expand=True, padx=(_p(10), 0))

        # 界面大小(小/中/大)—— 即改即生效;小档装不下就自动上下滚
        row4 = ctk.CTkFrame(card, fg_color="transparent")
        row4.pack(fill="x", padx=_p(16), pady=(_p(4), _p(15)))
        ctk.CTkLabel(row4, text="界面大小", font=_font(12.5), text_color=TEXT, width=_p(56),
                     anchor="w").pack(side="left")
        self.var_uiscale = tk.StringVar(value=UI_SCALE_TEXT[self.ui_level])
        self.seg_ui = ui.Segmented(row4, UI_SCALE_TEXT, self.var_uiscale, bg=CARD,
                                   command=self._on_ui_scale, width=170, height=32,
                                   font=_font(11.5), sc=self.sc)
        self.seg_ui.pack(side="right", padx=(_p(10), 0))
        self.lbl_uihint = ctk.CTkLabel(row4, text="装不下会自动上下滚",
                                       font=_font(10), text_color=FAINT)
        self.lbl_uihint.pack(side="right", padx=(0, _p(8)))

    def _footer(self, body):
        span = ctk.CTkFrame(body, fg_color="transparent")
        span.pack(fill="x", padx=_p(18), pady=(_p(2), _p(14)))
        ui.hairline(span, "#DFE0E6").pack(fill="x", pady=(0, _p(10)))
        ctk.CTkLabel(span, text="配置:%s" % config_path(), font=_font(10),
                     text_color="#B0B2B8", anchor="w").pack(anchor="w")
        row = ctk.CTkFrame(span, fg_color="transparent")
        row.pack(fill="x", pady=(_p(10), 0))
        ui.Button(row, "关于", command=self._about, bg=BG, kind="ghost", width=68,
                  height=34, font=_font(12), text_color=SUB, sc=self.sc).pack(side="left")
        self.btn_save = ui.Button(row, "保存并应用", command=self._save, bg=BG,
                                  kind="primary", width=130, height=34,
                                  font=_font(12, True), sc=self.sc)
        self.btn_save.pack(side="right")
        ui.Button(row, "取消", command=self._close_anim, bg=BG, kind="soft", width=80,
                  height=34, font=_font(12), sc=self.sc).pack(side="right", padx=(0, 9))

    # ---------- 适配 ----------
    def _style_titlebar(self):
        """把 Windows 系统标题栏染成跟内容一致的颜色(Win11 生效;Win10 忽略,不影响)"""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or \
                self.root.winfo_id()
            # COLORREF = 0x00BBGGRR
            for attr, val in ((35, 0x00F2EEEC),    # DWMWA_CAPTION_COLOR ← #ECEEF2
                              (36, 0x001F1D1D)):   # DWMWA_TEXT_COLOR    ← #1D1D1F
                c = ctypes.c_int(val)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c),
                                                          ctypes.sizeof(c))
            dark = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark),
                                                       ctypes.sizeof(dark))
            # 圆角(本来就是 Windows 窗口,Win11 会给;显式要一下更保险)
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref),
                                                       ctypes.sizeof(pref))
        except Exception:
            pass

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self._close_anim())

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

    def _on_ui_scale(self, value=None):
        """界面大小:即改即生效 —— 记下新档位,把当前(未保存的)改动一起带过去重建窗口"""
        try:
            lv = UI_SCALE_TEXT.index(value)
        except Exception:
            return
        if lv == self.ui_level:
            return
        self.ui_level = lv
        self.var_uiscale.set(UI_SCALE_TEXT[lv])
        if not self._rebuilding:
            self._rebuilding = True
            self.root.after(40, self._rebuild)

    def _rebuild(self):
        """换个档位就地重建控件(只换窗口宽度,字号不动)。
        重建瞬间整窗淡出 → 换完淡入,避免看到控件闪一下。"""
        self.cfg = self._collect()            # ⬅️ 先存档,再重建
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass
        self._x = max(8, (self._sw - self._ww()) // 2)
        self._layout_all()
        self._style_titlebar()
        _animate(self.root, self._x, self._y, 1.0, slide_from=0, steps=7, delay=10)
        self._rebuilding = False

    def _collect(self):
        """把界面上所有当前值收进一份 cfg(不落盘)—— 保存 / 换挡都用它"""
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
        cfg["ui_scale"] = int(self.ui_level)
        old_key = config.get_api_key(cfg)
        new_key = self.var_key.get().strip()
        if new_key != old_key:
            config.set_api_key(cfg, new_key)
        cfg["autostart"] = bool(self.var_auto.get())
        return cfg

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
        cfg = self._collect()
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
        # ⚠️ 兜底:动画万一被打断(异常/无焦点),也必须真的关掉并回调,
        #    否则桌宠那边的"设置已打开"标志会永久卡住 → 再也打不开设置
        try:
            self.root.after(600, self._destroy)
        except Exception:
            pass
        _animate(self.root, self._x, self._y, 0.0, slide_from=16, steps=10, delay=11,
                 on_done=self._destroy)

    def _hide(self):
        """关闭 = 隐藏(不销毁 root:见 __init__ 里的说明),并回调桌宠"""
        if getattr(self, "_destroyed", False):
            return
        self._destroyed = True
        self._hidden = True
        self._closing = False
        try:
            self.root.withdraw()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

    _destroy = _hide          # 兼容旧名字

    def reopen(self, cfg, on_close=None):
        """复用同一个窗口再开一次(带最新的配置)"""
        self.cfg = dict(cfg)
        self.on_close = on_close
        self.saved = False
        self._closing = False
        self._hidden = False
        self._destroyed = False
        self._rebuilding = False
        self.ui_level = max(0, min(len(UI_WIDTHS) - 1, int(self.cfg.get("ui_scale", 1))))
        try:
            self.sc = max(0.75, min(2.4, float(self.root.winfo_fpixels("1i")) / 96.0))
        except Exception:
            self.sc = 1.0
        self._sw = self.root.winfo_screenwidth()
        self._sh = self.root.winfo_screenheight()
        self._x = max(8, (self._sw - self._ww()) // 2)
        self._layout_all()
        self._style_titlebar()
        self._bind_keys()
        self.show()

    def show(self):
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass

        def _s():
            try:
                self.root.deiconify()
                self.root.lift()          # 打开时提到最前
            except Exception:
                pass
            _animate(self.root, self._x, self._y, 1.0, slide_from=26, on_done=self._focus)

        try:
            self.root.after(30, _s)
        except Exception:
            pass

    def run(self):
        self.show()
        self.root.mainloop()

    def _focus(self):
        try:
            self.ent.entry.focus_set()
        except Exception:
            pass


def open_settings(cfg, on_close=None):
    """开/复用设置窗口。
    ⚠️ 一个进程只建一次 Tk root(customtkinter 的 ScalingTracker 绑死第一个 root,
       destroy 后再新建必崩)→ 关掉只是 withdraw,再开就复用同一个窗口。
    桌宠线程通过队列发请求,设置线程用 after 轮询处理(Tk 不能跨线程调用)。"""
    th = _SESSION.get("thread")
    with _LOCK:
        _QUEUE.append((cfg, on_close))
    if th is not None and th.is_alive():
        return th
    th = threading.Thread(target=_session_run, daemon=True)
    _SESSION["thread"] = th
    th.start()
    return th


def _session_run():
    root = ctk.CTk()
    root.withdraw()
    state = {"win": None}

    def _poll():
        req = None
        with _LOCK:
            if _QUEUE:
                req = _QUEUE.pop(0)
        if req is not None:
            cfg, on_close = req
            try:
                if state["win"] is None:
                    state["win"] = SettingsWindow(cfg, on_close, root=root)
                    state["win"].show()
                else:
                    state["win"].reopen(cfg, on_close)
            except Exception:
                if on_close:
                    try:
                        on_close()
                    except Exception:
                        pass
        try:
            root.after(80, _poll)
        except Exception:
            pass

    root.after(80, _poll)
    root.mainloop()
