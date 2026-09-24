# -*- coding: utf-8 -*-
"""设置窗口(tkinter,标准库,不额外装东西)

数据流:打开时读 config → 用户改 → 保存时写盘 + 回调通知桌宠主线程重载。
"""
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import APP_TITLE, VERSION, autostart, balance, config
from .paths import config_path, resource_path

PAD = 10
LABEL_W = 16
LEVEL_TEXT = ["最小", "小", "中", "大", "最大"]


class SettingsWindow(object):
    def __init__(self, cfg, on_close=None):
        self.cfg = dict(cfg)
        self.on_close = on_close
        self.saved = False
        self.root = tk.Tk()
        self.root.title("%s · 设置 v%s" % (APP_TITLE, VERSION))
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        try:
            ico = resource_path("fish.ico")
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass
        self._style()
        self._build()
        self._center()
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)

    # ---------- 样式 / 布局 ----------
    def _style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except Exception:
            pass
        self.style.configure("Head.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        self.style.configure("Hint.TLabel", foreground="#678")
        self.style.configure("Ok.TLabel", foreground="#2ba35c")
        self.style.configure("Bad.TLabel", foreground="#d64545")

    def _row(self, parent, text):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=text, width=LABEL_W, anchor="w").pack(side="left")
        return f

    def _build(self):
        root = self.root
        pad = ttk.Frame(root, padding=PAD)
        pad.pack(fill="both", expand=True)

        # --- API Key ---
        ttk.Label(pad, text="DeepSeek 账号", style="Head.TLabel").pack(anchor="w")
        ttk.Label(pad, text="余额功能需要你自己的 API Key(只读接口,不消耗 token;不填也能用,只是不显示余额)",
                  style="Hint.TLabel", wraplength=440).pack(anchor="w", pady=(2, 6))
        f = self._row(pad, "API Key")
        self.var_key = tk.StringVar(value=config.get_api_key(self.cfg))
        self.ent_key = ttk.Entry(f, textvariable=self.var_key, width=34, show="•")
        self.ent_key.pack(side="left", fill="x", expand=True)
        self.var_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="显示", variable=self.var_show,
                        command=self._toggle_show).pack(side="left", padx=(6, 0))
        f2 = ttk.Frame(pad)
        f2.pack(fill="x", pady=(2, 2))
        ttk.Label(f2, text="", width=LABEL_W).pack(side="left")
        ttk.Button(f2, text="测试连接", command=self._test).pack(side="left")
        self.lbl_test = ttk.Label(f2, text="", style="Hint.TLabel")
        self.lbl_test.pack(side="left", padx=8)
        self.lbl_help = ttk.Label(
            pad, text="去哪拿 Key:platform.deepseek.com → API Keys → 创建",
            style="Hint.TLabel", wraplength=440)
        self.lbl_help.pack(anchor="w", pady=(0, 8))

        ttk.Separator(pad).pack(fill="x", pady=6)

        # --- 行为 ---
        ttk.Label(pad, text="行为", style="Head.TLabel").pack(anchor="w", pady=(0, 4))
        f = self._row(pad, "大小")
        self.var_level = tk.IntVar(value=int(self.cfg.get("size_level", 1)))
        self.lbl_level = ttk.Label(f, text=LEVEL_TEXT[self.var_level.get()], width=5)
        self.lbl_level.pack(side="right")
        ttk.Scale(f, from_=0, to=len(LEVEL_TEXT) - 1, variable=self.var_level,
                  orient="horizontal", command=self._on_level).pack(side="left", fill="x", expand=True)

        self.var_wander = tk.BooleanVar(value=bool(self.cfg.get("wander", True)))
        self.var_top = tk.BooleanVar(value=bool(self.cfg.get("topmost", True)))
        self.var_hide = tk.BooleanVar(value=bool(self.cfg.get("auto_hide_fullscreen", True)))
        self.var_snd = tk.BooleanVar(value=bool(self.cfg.get("sounds", True)))
        self.var_chat = tk.BooleanVar(value=bool(self.cfg.get("chat", True)))

        f = self._row(pad, "自主溜达")
        ttk.Checkbutton(f, text="让她在桌面上自己飘来飘去", variable=self.var_wander).pack(side="left")
        f = self._row(pad, "窗口置顶")
        ttk.Checkbutton(f, text="始终压在其他窗口上面", variable=self.var_top).pack(side="left")
        f = self._row(pad, "全屏游戏")
        ttk.Checkbutton(f, text="玩全屏游戏时自动躲起来(推荐)", variable=self.var_hide).pack(side="left")
        f = self._row(pad, "音效")
        ttk.Checkbutton(f, text="点击/拖拽时的语音", variable=self.var_snd).pack(side="left")
        f = self._row(pad, "碎嘴台词")
        ttk.Checkbutton(f, text="气泡里自言自语", variable=self.var_chat).pack(side="left")

        f = self._row(pad, "余额刷新")
        self.var_refresh = tk.IntVar(value=int(self.cfg.get("refresh_sec", 30)))
        ttk.Spinbox(f, from_=10, to=600, increment=10, width=6,
                    textvariable=self.var_refresh).pack(side="left")
        ttk.Label(f, text="秒", style="Hint.TLabel").pack(side="left", padx=4)

        f = self._row(pad, "喂文件")
        self.var_hard = tk.BooleanVar(value=bool(self.cfg.get("hard_delete", False)))
        ttk.Radiobutton(f, text="丢回收站(可找回)", value=False, variable=self.var_hard).pack(side="left")
        ttk.Radiobutton(f, text="彻底删除", value=True, variable=self.var_hard).pack(side="left", padx=8)

        f = self._row(pad, "开机自启")
        self.var_auto = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(f, text="登录 Windows 后自动启动", variable=self.var_auto).pack(side="left")

        ttk.Separator(pad).pack(fill="x", pady=8)

        # --- 底部按钮 ---
        f = ttk.Frame(pad)
        f.pack(fill="x")
        ttk.Button(f, text="关于", command=self._about).pack(side="left")
        ttk.Button(f, text="取消", command=self._cancel).pack(side="right")
        ttk.Button(f, text="保存并应用", command=self._save).pack(side="right", padx=6)
        ttk.Label(pad, text="配置:%s" % config_path(), style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

    def _center(self):
        self.root.update_idletasks()
        w = max(520, self.root.winfo_reqwidth() + 8)
        h = self.root.winfo_reqheight() + 6
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        h = min(h, sh - 80)
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(20, (sh - h) // 2 - 40)))

    # ---------- 事件 ----------
    def _toggle_show(self):
        self.ent_key.configure(show="" if self.var_show.get() else "•")

    def _on_level(self, _v=None):
        self.lbl_level.configure(text=LEVEL_TEXT[int(float(self.var_level.get()))])

    def _test(self):
        key = self.var_key.get().strip()
        if not key:
            self.lbl_test.configure(text="先填个 Key 吧", style="Bad.TLabel")
            return
        self.lbl_test.configure(text="测试中…", style="Hint.TLabel")

        def _work():
            try:
                v, cur = balance.fetch_balance(key)
                msg, sty = "✓ 连接成功,余额 %.2f %s" % (v, cur), "Ok.TLabel"
            except Exception as e:
                msg, sty = "✗ " + str(e), "Bad.TLabel"
            try:
                self.root.after(0, lambda: self.lbl_test.configure(text=msg, style=sty))
            except Exception:
                pass

        threading.Thread(target=_work, daemon=True).start()

    def _about(self):
        messagebox.showinfo(
            "关于",
            "%s v%s\n\n"
            "一只趴在桌面上的余额挂件,纯本地运行;\n"
            "只有查余额时会连一次 DeepSeek 官方只读接口。\n\n"
            "美术素材:大肥鱼 - 余额挂件 v0.3.0\n"
            "  © @月匠 / MeteorNOX(MIT License)\n"
            "参考:whale-purse © Suiwan(MIT License)\n"
            "本程序:MIT License,可自由分享。"
            % (APP_TITLE, VERSION))

    def _save(self):
        cfg = dict(self.cfg)
        cfg["size_level"] = int(float(self.var_level.get()))
        cfg["wander"] = bool(self.var_wander.get())
        cfg["topmost"] = bool(self.var_top.get())
        cfg["auto_hide_fullscreen"] = bool(self.var_hide.get())
        cfg["sounds"] = bool(self.var_snd.get())
        cfg["chat"] = bool(self.var_chat.get())
        cfg["refresh_sec"] = max(10, int(self.var_refresh.get()))
        cfg["hard_delete"] = bool(self.var_hard.get())
        old_key = config.get_api_key(cfg)
        new_key = self.var_key.get().strip()
        if new_key != old_key:
            config.set_api_key(cfg, new_key)
        cfg["autostart"] = bool(self.var_auto.get())
        config.save(cfg)
        ok, msg = autostart.apply(cfg["autostart"])
        if not ok:
            messagebox.showwarning("开机自启", "设置自启失败:%s" % msg)
        self.saved = True
        self._close()

    def _cancel(self):
        self._close()

    def _close(self):
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
        self.root.mainloop()


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
