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
import math
import os
import threading
import time
import tkinter as tk

import customtkinter as ctk
from PIL import ImageTk

from . import APP_TITLE, VERSION, balance, config

# 轻量版:只保留游玩/观赏/陪伴/看余额
LITE = os.environ.get("DSPET_EDITION", "") == "lite"
if not LITE:
    from . import autostart, memopt
from . import uikit as ui
from .paths import app_dir, config_dir, config_path
from .uikit import (ACCENT, ACCENT_HOVER, BG, CARD, DANGER, FAINT, GREEN, SUB, TEXT)

W, H = 580, 800
_SESSION = {}
_QUEUE = []
_LOCK = threading.Lock()
LEVEL_TEXT = ["最小", "小", "中", "大", "最大"]
REFRESH_CHOICES = [10, 15, 30, 60, 120, 300]

# 设置界面尺寸(单档:固定小尺寸,不再让用户切档)
# ⚠️ 东家定调:只保留小尺寸 —— 宽度固定 860
UI_WIDTHS = [860]
UI_HEIGHT_K = [1.0]     # 高度系数(内容自然高;下面再拉高下限,别太扁)
_UIK = [1.0]                # 保留但恒为 1.0:字号/间距不再随档位缩放

# 左导航栏:收起=图标栏宽,展开=完整条宽;每项做得小而紧凑(不用滚动)
NAV_COLLAPSED = 46
NAV_EXPANDED = 196
NAV_H = 34

Toggle = ui.Switch          # 兼容旧名字


def _font(size=13, bold=False):
    return ctk.CTkFont(family="Microsoft YaHei UI",
                       size=max(7, int(round(size))),
                       weight="bold" if bold else "normal")


def _all_data_dirs():
    """程序可能落数据的全部目录(便携=exe 同目录 / %APPDATA% 下的 DeepSeekPet)"""
    dirs = [config_dir(), app_dir()]
    roaming = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                           "DeepSeekPet")
    dirs.append(roaming)
    out = []
    for d in dirs:
        if d and d not in out:
            out.append(d)
    return out


def _p(n):
    """间距/尺寸(不随档位变;留着这个名字是为了少改调用点)"""
    return int(n)


def _ease_out_cubic(k):
    """Material 风格缓出:起步快、尾段慢,观感上"跟手"不粘滞。k∈[0,1]"""
    k = max(0.0, min(1.0, k))
    return 1.0 - (1.0 - k) ** 3


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


def _intro_reveal(win, x, y, w, h, on_done=None, hold_ms=0):
    """设置窗出场:只做**一次**干净、单调的淡入。

    东家原话:「圆标结束之后 UI 出现太丑了,动画太恶心了,几乎可以称作 bug;
    你哪怕直接把 UI 跳出来都比现在这个强。」

    旧版为什么丑:窗口先被 _phase_open 直接 deiconify 到最终几何(硬跳),
    紧接着又被本函数按 0.80 倍重设尺寸再"冒头→停 420ms→铺开"——窗口明明
    已经全尺寸可见,却又缩回去重放一遍,于是出现"弹一下 / 卡一下"的抖动。

    现在:窗口从头到尾停在**最终几何**,alpha 从 0 单调升到 1,约 200ms。
    没有中途停顿、没有尺寸变化、没有第二段动画 —— 观感就是"一次性淡出"。
    圆标记(IntroCircle)由调用方负责在同一时间窗内淡出,两者交叉,不打架。
    """
    wx, wy = max(0, x), max(0, y)

    def _finish():
        try:
            win.geometry("%dx%d+%d+%d" % (w, h, wx, wy))
            win.attributes("-alpha", 1.0)
            win.lift()
            win.focus_force()
        except Exception:
            pass
        if on_done:
            try:
                on_done()
            except Exception:
                pass

    try:
        win.geometry("%dx%d+%d+%d" % (w, h, wx, wy))
        win.attributes("-alpha", 0.0)
    except Exception:
        pass

    n = 12

    def _step(i):
        if i > n:
            _finish()
            return
        k = i / float(n)
        e = 1 - (1 - k) ** 2                       # easeOutQuad:快起、轻收
        try:
            win.attributes("-alpha", e)
        except Exception:
            pass
        try:
            win.after(16, lambda: _step(i + 1))
        except Exception:
            _finish()

    try:
        win.after(16, lambda: _step(0))
    except Exception:
        _finish()


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
        self.sc = 1.0

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
        self._y = max(0, (sh - min(760, self._sh - 160)) // 2)
        self.root.geometry("%dx%d+%d+%d" % (self._ww(), min(760, self._sh - 160),
                                           self._x, self._y))

        self.compact = False
        self._foot_host = None
        self._layout_all()
        self._style_titlebar()
        self._bind_keys()

    # ---------- 尺寸 / 缩放 ----------
    def _ww(self):
        """窗口内容区宽度 —— 固定小尺寸,字号/控件大小一律不变"""
        return UI_WIDTHS[0]

    def _wh(self):
        """窗口内容区高度 —— 由 _layout_all() 算好后存在 self.h"""
        return int(getattr(self, "h", 720))

    def _wa_h(self):
        # 窗不能太高,也不能太扁:目标 ~460 高(约屏幕 32%),上限屏幕 62%
        return max(420, int(self._sh * 0.62))

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
        # 想要的高度 = 内容自然高 × 档位系数(小档故意矮一截 → 自动转成可滚动)
        want = int(round(need * UI_HEIGHT_K[0]))
        want = int(min(max(want, 460), self._wa_h()))
        if want < need:                                   # 装不下 → 内容可滚动
            body.destroy()
            self.compact = True
            body = self._body_parent()
            self._build_body(body, with_footer=False)     # 底栏已经建好了,别重复
            self.root.update_idletasks()
        self.h = want
        self._size = (self._ww(), self.h)
        # 窗口居中显示(东家要求:生成在中央)
        self._x = max(8, (self._sw - self._ww()) // 2)
        self._y = max(0, (self._sh - self.h) // 2)
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
        ctk.CTkFrame(body, fg_color="transparent", height=_p(10)).pack(fill="x")
        # PCL 风格:左侧导航栏(固定不动)+ 右侧详细配置区(可滚动)
        cols = ctk.CTkFrame(body, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure(0, weight=0, minsize=int(NAV_COLLAPSED * self.sc))
        cols.grid_columnconfigure(1, weight=1)       # 右详情:占满剩余(跟随左边收放)
        cols.grid_rowconfigure(0, weight=1)
        self._cols = cols

        # --- 左导航:固定式(PCL 风)。
        # 不做悬停展开动画 —— 悬停展开 + 动态宽度在 Tk 里就是脆:
        # 改 grid 列宽会触发整窗重排(最坏 50~100ms/帧),而不改列宽 rail 又展不开。
        # 两者互斥,且兜底轮询会和鼠标事件抢主线程 → 实测"碰上去愣一下"。
        # 固定式:栏宽恒为 NAV_EXPANDED,按钮永久展开,零动画、零轮询。
        self._nav_rail = ctk.CTkFrame(cols, width=int(NAV_EXPANDED * self.sc),
                                      fg_color="transparent", corner_radius=0)
        self._nav_rail.grid(row=0, column=0, sticky="nsew")
        self._nav_rail.grid_propagate(False)
        nav = ctk.CTkFrame(self._nav_rail, fg_color="transparent", corner_radius=0,
                           width=int(NAV_EXPANDED * self.sc))
        nav.place(x=0, y=0, relheight=1.0, anchor="nw")
        self._nav_inner = nav
        self._nav_expanded = True            # 固定展开态(兼容旧引用)
        self._nav_t = 1.0
        self._nav_t_start = 1.0
        self._nav_t0 = 0.0
        self._nav_anim_job = None
        self._nav_collapse_job = None
        self._nav_watch_job = None
        self._nav_away_since = None

        # --- 右详情:grid 占满剩余(column-1 weight=1),与 rail 同属 cols ---
        right_out = ctk.CTkFrame(cols, fg_color="transparent")
        right_out.grid(row=0, column=1, sticky="nsew", padx=(_p(6), _p(14)))
        right_out.grid_columnconfigure(0, weight=1)
        right_out.grid_rowconfigure(0, weight=1)
        right = ctk.CTkScrollableFrame(
            right_out, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#CFD1D8",
            scrollbar_button_hover_color="#B8BBC4")
        right.grid(row=0, column=0, sticky="nsew")
        self._right_out = right_out

        self._nav_buttons = {}
        self._pages = {}
        self._nav_order = []
        self._nav_icons = {
            "account": "account", "behaviour": "behaviour", "details": "details",
            "toolbox": "toolbox", "uninstall": "uninstall",
        }

        def add_page(key, label):
            page = ctk.CTkFrame(right, fg_color="transparent")
            self._pages[key] = page
            self._nav_order.append(key)
            btn = ui.NavButton(
                nav, label, command=lambda k=key: self._show_page(k),
                bg=BG, width=NAV_EXPANDED, height=NAV_H, font=_font(12),
                sc=self.sc, icon=self._nav_icons.get(key), compact_w=NAV_COLLAPSED,
                icon_size=20, expanding=True)
            btn.pack(fill="x", pady=(0, _p(6)))
            btn.set_wide(1.0)     # 固定展开:按钮永远显图标+文字
            self._nav_buttons[key] = btn
            return page

        # --- 顶部 logo/标题区(PCL 风:图标 + 应用名) ---
        # 必须在包导航项之前 pack,才能占据顶部。
        # 宽高固定不随展开变 —— 它只是招牌,不参与导航项的重排。
        head = ctk.CTkFrame(nav, fg_color="transparent", corner_radius=0)
        head.pack(side="top", fill="x", pady=(0, _p(10)))
        head_h = int(54 * self.sc)
        head.configure(height=head_h)
        head.pack_propagate(False)
        icon_px = int(self._nav_collapsed_size())
        self._head_icon = tk.Canvas(head, width=icon_px, height=head_h, bg=BG,
                                    bd=0, highlightthickness=0)
        self._head_icon.pack(side="left")
        try:
            ph = ui.icon_image("fish", 26, ACCENT, 2.0, self.sc)
            self._head_icon.create_image(icon_px / 2.0, head_h / 2.0, image=ph)
            self._head_icon._ph = ph     # 防 GC
        except Exception:
            pass
        # 固定展开:标题直接显示(不再随展开淡入)
        self._head_title = ctk.CTkLabel(
            head, text="DeepSeek Pet", font=_font(13, "bold"),
            text_color=TEXT, anchor="w", justify="left")
        self._head_title.pack(side="left", padx=(_p(8), 0))
        self._head_title_shown = True

        # 页 1:账号
        pg = add_page("account", "账号")
        self._api_card(pg)
        # 页 2:外观与行为
        pg = add_page("behaviour", "外观与行为")
        self._behaviour_card(pg)
        # 页 3:细节
        pg = add_page("details", "细节")
        self._details_card(pg)
        # 页 4:工具箱
        if not LITE:
            pg = add_page("toolbox", "工具箱")
            self._toolbox_card(pg)
        # 页 5:卸载(单独一栏)
        if not LITE:
            pg = add_page("uninstall", "卸载")
            self._uninstall_card(pg)

        # 默认停在第一页
        self._cur_page = None
        self._show_page(self._nav_order[0])
        if with_footer:
            self._footer(self._foot_host)
        return body

    def _show_page(self, key):
        """切换右侧详情区:只显示当前页,其余隐藏(保留控件状态)"""
        self._cur_page = key
        for k, pg in self._pages.items():
            if k == key:
                pg.pack(fill="both", expand=True)
            else:
                pg.pack_forget()
        for k, btn in self._nav_buttons.items():
            try:
                btn.set_active(k == key)
            except Exception:
                pass

    # ---------- 左导航:悬停向左展开(帧驱动补间 + 迟滞判定) ----------
    def _nav_expanded_size(self):
        return int(NAV_EXPANDED * self.sc)

    def _nav_collapsed_size(self):
        return int(NAV_COLLAPSED * self.sc)

    def _set_nav_expanded(self, on):
        """固定式导航:无展开/收起,保留此方法仅为兼容外部调用。"""
        self._nav_expanded = True

    def _nav_apply(self, t):
        """固定式:栏宽恒为 NAV_EXPANDED,按钮永久展开。仅初始化时调一次。"""
        try:
            self._nav_rail.configure(width=self._nav_expanded_size())
        except Exception:
            pass
        for b in self._nav_buttons.values():
            try:
                b.set_wide(1.0)
            except Exception:
                pass

    def _head_follow(self, t):
        """固定式:标题常驻,无需跟随。兼容保留。"""
        pass

    def _nav_apply_legacy_unused(self, t):
        """(已弃用)旧动画帧实现,留作参考。不再调用。"""
        try:
            show = t > 0.55
            if show != getattr(self, "_head_title_shown", None):
                self._head_title_shown = show
                if show:
                    self._head_title.pack(side="left", padx=(_p(8), 0))
                else:
                    self._head_title.pack_forget()
        except Exception:
            pass

    def _nav_hit(self, x, y):
        """鼠标 (x,y)(屏幕坐标)是否落在导航栏的**可见区域**内。
        收起态栏只有 NAV_COLLAPSED 宽;展开态是 NAV_EXPANDED 宽——
        两条矩形都要认,否则"栏已展开、鼠标落在加宽出来的那一段"会被误判在外
        → 栏刚展开就自己收,抖动(实测根因)。"""
        try:
            x0 = self._nav_rail.winfo_rootx()
            y0 = self._nav_rail.winfo_rooty()
            h = self._nav_rail.winfo_height()
            if not (y0 <= y <= y0 + h):
                return False
            w_exp = self._nav_expanded_size()
            return x0 <= x <= x0 + w_exp
        except Exception:
            return False

    def _nav_maybe_collapse(self):
        """收到 Leave 后立刻判定:鼠标真在外面就收,还在栏上就不动。
        不做延迟——延迟会让人感到"反应慢"。躲开子控件间的瞬时 Leave
        靠的是 _nav_hit 按真实指针位置判定,而不是靠等。"""
        if self._nav_collapse_job:
            try:
                self.root.after_cancel(self._nav_collapse_job)
            except Exception:
                pass
        self._nav_collapse_job = None
        self._nav_collapse_now()

    def _nav_collapse_now(self):
        self._nav_collapse_job = None
        try:
            x, y = self.root.winfo_pointerxy()
            if self._nav_hit(x, y):
                return                       # 鼠标还在栏(含加宽区),别收
        except Exception:
            pass
        self._set_nav_expanded(False)

    def _nav_watch(self):
        """收起兜底:鼠标确实不在栏上就收起(轮询间隔 40ms,所以反应快)。
        它只是兜"<Leave> 漏事件"的安全网;正常收起靠 _nav_maybe_collapse 立即判。"""
        self._nav_watch_job = None
        if not self._nav_expanded and self._nav_anim_job is None:
            self._nav_away_since = None
            return
        try:
            x, y = self.root.winfo_pointerxy()
            inside = self._nav_hit(x, y)
        except Exception:
            inside = True
        if inside:
            self._nav_away_since = None
        elif self._nav_anim_job is None and self._nav_expanded:
            self._set_nav_expanded(False)
        if self._nav_expanded or self._nav_anim_job is not None:
            try:
                self._nav_watch_job = self.root.after(40, self._nav_watch)
            except Exception:
                pass

    def _uninstall_card(self, body):
        card = Card(body, "卸载", self.sc)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=_p(16), pady=(_p(13), _p(15)))
        ctk.CTkLabel(inner, text="一键卸载桌面宠物", font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text="退出程序、移除开机自启,并彻底清除本程序的配置与数据,"
                                "不留任何痕迹。",
                     font=_font(10), text_color=FAINT, anchor="w",
                     justify="left").pack(anchor="w", pady=(_p(2), _p(12)))
        self.btn_uninstall = ui.Button(inner, "一键卸载", command=self._uninstall,
                                       bg=CARD, kind="danger", width=120, height=34,
                                       font=_font(12, True), sc=self.sc)
        self.btn_uninstall.pack(anchor="w")
        ctk.CTkLabel(inner, text="点击后会弹窗二次确认。", font=_font(10),
                     text_color=FAINT, anchor="w").pack(anchor="w", pady=(_p(8), 0))

    def _uninstall(self):
        from tkinter import messagebox
        msg = ("确定要卸载「%s」吗?\n\n"
               "将退出程序、移除开机自启,并删除全部配置与数据,不留痕迹。"
               % APP_TITLE)
        if not messagebox.askyesno("卸载确认", msg, parent=self.root):
            return
        # 二次确认:用户再点一次"确定"才真正清除
        msg2 = ("再次确认:所有配置、数据与程序文件将被永久删除,"
                "且无法恢复。\n\n确定继续吗?")
        if not messagebox.askyesno("最终确认", msg2, parent=self.root,
                                   icon="warning", default="no"):
            return
        self._do_uninstall()

    def _do_uninstall(self):
        """彻底卸载:关自启 → 删配置/数据 → 删快捷方式 → 清标记 → 删程序自身"""
        import os
        import shutil
        import subprocess
        # 1) 关自启(删启动文件夹里的 .lnk)
        try:
            autostart.apply(False)
        except Exception:
            pass
        # 2) 删配置/数据目录(便携=exe 同目录;否则 %APPDATA%\DeepSeekPet)
        for d in _all_data_dirs():
            try:
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        # 3) 删桌面快捷方式
        try:
            for name in ("%s.lnk" % APP_TITLE, "DeepSeekPet.lnk"):
                lnk = os.path.join(os.path.expanduser("~"), "Desktop", name)
                if os.path.exists(lnk):
                    os.remove(lnk)
        except Exception:
            pass
        # 4) 清任何历史标记文件(不留痕迹)
        for name in (".dspet_uninstalled", "dspet.log"):
            try:
                p = os.path.join(os.path.expanduser("~"), name)
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        # 5) 延迟自我删除:写批处理,等本进程退出后删掉 exe 与遗留文件
        try:
            exe = sys.executable
            if exe.lower().endswith(".exe") and "DeepSeekPet" in os.path.basename(exe):
                bat = os.path.join(os.environ.get("TEMP", "."), "_dspet_uninst.bat")
                with open(bat, "w", encoding="gbk") as f:
                    f.write("@echo off\r\n")
                    f.write("timeout /t 2 /nobreak >nul\r\n")
                    f.write('del /f /q "%s"\r\n' % exe)
                    f.write('del /f /q "%s\r\n' % os.path.join(
                        os.path.dirname(exe), "config.json"))
                    f.write('del /f /q "%s\r\n' % os.path.join(
                        os.path.dirname(exe), "dspet.log"))
                    # 删不掉(只读目录/权限不足)就给个提示,别默默失败
                    f.write('if exist "%s" (\r\n' % exe)
                    f.write('  echo 无法自动删除程序文件,请手动删除此目录:> "%%TEMP%%\\_dspet_hint.txt"\r\n')
                    f.write('  echo %s>> "%%TEMP%%\\_dspet_hint.txt"\r\n' % os.path.dirname(exe))
                    f.write('  start "" notepad "%%TEMP%%\\_dspet_hint.txt"\r\n')
                    f.write(')\r\n')
                    f.write('del /f /q "%%~f0"\r\n')
                subprocess.Popen(["cmd", "/c", bat], shell=False,
                                 creationflags=0x08000000)
        except Exception:
            pass
        # 7) 兜底:exe 不在可删目录(如 Program Files)时,弹窗告知手动删除
        try:
            exe = sys.executable
            if exe.lower().endswith(".exe") and "DeepSeekPet" not in os.path.basename(exe):
                from tkinter import messagebox
                messagebox.showinfo(
                    "卸载提示",
                    "配置与数据已清除。\n\n程序文件未能自动删除,\n"
                    "请手动删除此目录:\n%s" % os.path.dirname(exe),
                    parent=self.root)
        except Exception:
            pass
        self.root.after(120, lambda: os._exit(0))

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
        self.var_auto = tk.BooleanVar(value=(not LITE) and autostart.is_enabled())

        rows = [
            ("自主溜达", "没事时自己飘来飘去", self.var_wander),
            ("安静模式", "冷落一会儿才溜达", self.var_calm),
            ("窗口置顶", "压在其他窗口上面", self.var_top),
            ("全屏游戏让位", "游戏一开就自动躲开", self.var_hide),
            ("音效", "点击/拖拽时的语音", self.var_snd),
            ("碎嘴台词", "气泡里自言自语", self.var_chat),
            ("开机自启", "登录 Windows 后出现", self.var_auto),
        ]
        if LITE:
            rows = [r for r in rows if r[2] is not self.var_auto]

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

        # 界面大小切换已移除(东家要求:只保留小尺寸,不再让用户切档)
        row3.pack_configure(pady=(_p(4), _p(15)))

    def _toolbox_card(self, body):
        """工具箱 —— 目前一个「内存优化」(对标 PCL2 启动器那个)"""
        card = Card(body, "工具箱", self.sc)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=_p(16), pady=(_p(14), 0))
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text="内存优化", font=_font(12.5), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(left, text="清掉系统待机内存和修改页,腾出可用内存",
                     font=_font(10), text_color=FAINT, anchor="w").pack(
                         anchor="w", pady=(_p(2), 0))
        self.btn_mem = ui.Button(row, "立即优化", command=self._mem_optimize, bg=CARD,
                                 kind="primary", width=92, height=32, font=_font(12),
                                 sc=self.sc)
        self.btn_mem.pack(side="right")
        self._mem_busy = False
        self._mem_hint = "清系统缓存需要管理员权限 —— 会弹一次 UAC,点『是』即可"
        try:
            self._mem_now = memopt.lines_now()
        except Exception:
            self._mem_now = ""
        self.lbl_mem = ctk.CTkLabel(card, text=self._mem_text(), font=_font(10.5),
                                    text_color=SUB, anchor="w", justify="left",
                                    wraplength=int(420 * self.sc))
        self.lbl_mem.pack(fill="x", padx=_p(16), pady=(_p(7), _p(15)))

    def _mem_text(self):
        lines = []
        if getattr(self, "_mem_now", ""):
            lines.append(self._mem_now)
        lines.append(getattr(self, "_mem_hint", ""))
        return "\n".join([ln for ln in lines if ln])

    def _mem_optimize(self):
        if self._mem_busy:
            return
        self._mem_busy = True
        self._mem_result = None
        self.btn_mem.set_text("优化中…")
        self._mem_hint = "正在清理…(若弹出 UAC,请点『是』,不然清不了系统缓存)"
        self.lbl_mem.configure(text=self._mem_text(), text_color=SUB)
        threading.Thread(target=self._mem_work, daemon=True).start()
        # ⚠️ 结果用主线程轮询取回:从工作线程直接调 tk 的 after 在有些环境会失败
        self._mem_poll()

    def _mem_work(self):
        try:
            from . import memopt
            _ok, res = memopt.optimize()
            l1, l2 = memopt.report(res)
            self._mem_now, self._mem_hint = l1, l2
            self._mem_result = "%s\n%s" % (l1, l2)
        except Exception as e:                      # 别让 UI 线程炸
            self._mem_result = "失败:%s" % e

    def _mem_poll(self):
        if self._mem_result is None:
            try:
                self.root.after(120, self._mem_poll)
            except Exception:
                pass
            return
        self._mem_busy = False
        self.btn_mem.set_text("立即优化")
        self.lbl_mem.configure(text=self._mem_result, text_color=SUB)

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

    def _rebuild(self):
        """换个档位就地重建控件(只换窗口宽度,字号不动)。
        重建瞬间整窗淡出 → 圆形标记居中冒出 → 换完淡入,避免看到控件闪一下。"""
        self.cfg = self._collect()            # ⬅️ 先存档,再重建
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass
        self._x = max(8, (self._sw - self._ww()) // 2)
        self._layout_all()
        self._style_titlebar()

        # 换档位也放一遍开场圆动画(与开窗同款):圆居中冒出 → 圆淡出+窗口淡入
        w, h = self._ww(), self._wh()

        def _phase_reveal():
            _animate(self.root, self._x, self._y, 1.0, slide_from=0, steps=7, delay=10)

        c = None
        try:
            from . import introcircle
            c = introcircle.IntroCircle(
                self._x, self._y, w, h, size=240, text="九",
                logo=introcircle.BADGE)
            if not c.show():
                c = None
        except Exception:
            c = None

        if c is None:
            try:
                self.root.deiconify()
                self.root.update_idletasks()
            except Exception:
                pass
            _phase_reveal()
            return

        def _fade_circle():
            try:
                self.root.deiconify()
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass
            _phase_reveal()

        try:
            self.root.after(320, _fade_circle)
        except Exception:
            _fade_circle()

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
        cfg["ui_scale"] = 0            # 固定小尺寸(切档已移除)
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
        _animate(self.root, self._x, self._y, 0.0, slide_from=20, steps=14, delay=13,
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
        try:
            self.sc = max(0.75, min(2.4, float(self.root.winfo_fpixels("1i")) / 96.0))
        except Exception:
            self.sc = 1.0
        self._sw = self.root.winfo_screenwidth()
        self._sh = self.root.winfo_screenheight()
        self._x = max(8, (self._sw - self._ww()) // 2)
        # 窗口居中(东家要求:生成在中央)— 高度算好后 _layout_all 会再定一次
        self._y = max(0, (self._sh - self._wh()) // 2)
        self._layout_all()
        self._style_titlebar()
        self._bind_keys()
        self.show()
        # 开场动画照旧,但**额外把窗口提到最前** ——
        # 设置 UI 已经开着时再点启动设置,窗口可能被别的窗口盖住,
        # 得让它冒到最上方(东家反馈)。
        self._raise_front()

    def _raise_front(self):
        """把已存在的窗口提到最前并给焦点(不改变开场动画)。
        topmost 只短暂置顶(~350ms)后自动解除,不霸屏。"""
        try:
            self.root.after(260, self._raise_front_now)
        except Exception:
            self._raise_front_now()

    def _raise_front_now(self):
        try:
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(350, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def show(self):
        """Office 式开场:圆形标记冒出来 -> 停顿 -> 铺开成完整窗。

        东家原话:「我想要的是有那个圆形图标啊,那个我没看到」——
        所以起点不是"缩小版的窗口",而是一个**真正的圆形标记**
        (WS_EX_LAYERED 分层窗,圆外全透明,见 introcircle.py)。

        节奏:
          ① 圆形标记淡入 + 轻微弹出(约 120ms),停在**屏幕正中**
          ② 停顿 420ms —— 吊一下(Office 的"顿")
          ③ 圆淡出,窗口从 0.86 倍铺开到 100% + 淡入
        """
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass

        w, h = self._ww(), self._wh()

        def _phase_circle():
            """① 圆出现(大一点,240,居中屏幕)"""
            c = None
            try:
                from . import introcircle
                c = introcircle.IntroCircle(
                    self._x, self._y, w, h, size=240, text="九",
                    logo=introcircle.BADGE)
                if not c.show():
                    c = None
            except Exception:
                c = None

            if c is None:
                # 圆起不来(非 Windows / 依赖缺失) -> 直接让窗口淡入,别把窗也丢了
                try:
                    self.root.deiconify()
                    self.root.update_idletasks()
                except Exception:
                    pass
                _intro_reveal(self.root, self._x, self._y, w, h, on_done=self._focus)
                return

            try:
                self.root.after(420, lambda: _phase_fade_circle(c))
            except Exception:
                _phase_fade_circle(c)

        def _phase_fade_circle(c):
            """② 停顿结束 -> 圆淡出,同时窗口在**最终几何**上淡入。

            ?? 关键:先 deiconify 但保持 alpha=0,让窗口就位;圆的淡出与
               窗口的淡入在时间上重叠(圆先各走各的,不再"圆没了窗口砰地跳出")。
               c.close() 内部自带收缩+淡出,这里不阻塞,交给窗口淡入并行。
            """
            try:
                self.root.deiconify()
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass
            _intro_reveal(self.root, self._x, self._y, w, h, on_done=self._focus)

        try:
            self.root.after(30, _phase_circle)
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
