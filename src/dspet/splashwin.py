# -*- coding: utf-8 -*-
"""自绘启动画面(B 方案):不依赖 PyInstaller splash,自己用 tkinter 画。

为什么不用 PyInstaller --splash:
    实测它在本机 onefile 模式下不显示(bootloader 解包耗时吃掉了整个启动窗口),
    且属打包黑盒、难调试。自绘可控、可调试、能在窗口出现前就显示。

契约:
    start()  -> 非阻塞,起一个后台线程显示 splash;失败时静默降级(绝不拖垮主程序)
    set_progress(p, t) -> 更新进度条(0..1)与文字;线程安全
    close()  -> 请求关闭;幂等
    close_now() -> 立刻关闭(桌宠即将出现时用,保证不同屏重叠)
    wait_closed(timeout) -> 等 splash 真正消失

线程模型:tkinter 必须在自己创建的线程里跑 mainloop。splash 独占一个线程,
主程序(Pet)在别的线程/主线程,互不干扰。所有跨线程操作只通过 queue 传递。

视觉(**横幅模式**):
    整张宽幅插画铺满画面,底部叠加一层由深到透明的渐变,
    再叠标题/进度条/副标题 —— 类似游戏启动画面(launcher)。
    素材比例决定窗口比例;窗口不做圆角(横幅贴边更利落)。
"""
import os
import queue
import threading
import time

_QUEUE = None          # type: queue.Queue | None
_THREAD = None         # type: threading.Thread | None
_LOCK = threading.Lock()
_STARTED = False
_CLOSED = threading.Event()

# 横幅窗口(内容区上限;实际尺寸由素材比例决定)
# 东家要求:比之前小一点。923x537 ≈ 原来的 0.84 倍。
MAX_W, MAX_H = 923, 537

FOOT_H = 104               # 底部信息区高度(渐变 + 标题 + 进度条 + 副标题)
GRAD_TOP = 0.0             # 渐变顶部透明度(0=全透)
GRAD_BOTTOM = 0.88         # 渐变底部不透明度

TITLE = "DeepSeek 大肥鱼"
BAR_FG = (86, 132, 232)          # 进度条(DeepSeek 蓝)
BAR_FG2 = (126, 168, 255)        # 进度条高光
BAR_BG = (255, 255, 255, 46)     # 进度条槽(半透明白,叠在渐变上)
TITLE_FG = (244, 247, 252)       # 标题
SUB_FG = (198, 210, 232)         # 副标题/进度文字
SHADOW = (0, 0, 0)               # 底部渐变底色


def _font(size, bold=False):
    """找一个能显示中文的字体。"""
    from PIL import ImageFont
    names = (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
             r"C:\Windows\Fonts\msyhbd.ttc",
             r"C:\Windows\Fonts\simhei.ttf",
             r"C:\Windows\Fonts\simsun.ttc")
    for fp in names:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


class _Frame(object):
    """一帧的绘制数据:横幅图 + 尺寸 + 字体。"""

    def __init__(self, art, W, H):
        self.art = art          # RGB 横幅图
        self.W = W
        self.H = H
        self.f_title = _font(max(18, int(H * 0.045)), bold=True)
        self.f_sub = _font(max(12, int(H * 0.028)))
        self.f_pct = _font(max(11, int(H * 0.026)))


def _load_art(path):
    """读素材并缩放到 MAX 内;返回 RGB(横幅不留透明)。失败抛异常由上层兜底。"""
    from PIL import Image
    src = Image.open(path).convert("RGB")
    aw, ah = src.size
    k = min(1.0, MAX_W / aw, MAX_H / ah)
    if k < 1.0:
        src = src.resize((max(1, int(aw * k)), max(1, int(ah * k))), Image.LANCZOS)
    return src


def _measure(path):
    """按素材比例算出窗口尺寸,并预读横幅图。"""
    art = _load_art(path)
    return _Frame(art, art.width, art.height)


def _paint(frame, progress, sub_text):
    """把整帧画成一张**完全不透明**的 RGB 图,交给 Tk 显示。

    关键:Tk 不做 alpha 合成,所以这里一次性合成好:
    横幅图 → 底部渐变遮罩 → 文字/进度条。
    """
    from PIL import Image, ImageDraw
    W, H = frame.W, frame.H
    art = frame.art

    out = art.copy()

    # 底部渐变:由下到上,从 GRAD_BOTTOM 渐隐到 GRAD_TOP
    foot = int(H * (FOOT_H / max(1.0, float(H)) * 1.0)) if False else FOOT_H
    foot = min(foot, H)
    grad = Image.new("L", (1, foot), 0)
    gp = grad.load()
    for y in range(foot):
        t = 1.0 - (y / max(1, foot - 1))          # 底部=1,顶部=0
        gp[0, y] = int(255 * (GRAD_TOP + (GRAD_BOTTOM - GRAD_TOP) * t))
    grad = grad.resize((W, foot), Image.BILINEAR)
    dark = Image.new("RGB", (W, foot), SHADOW)
    out.paste(dark, (0, H - foot), grad)

    d = ImageDraw.Draw(out)

    # 标题(左下)
    m = int(W * 0.045)                            # 左右边距
    y_title = H - foot + int(foot * 0.14)
    d.text((m, y_title), TITLE, font=frame.f_title, fill=TITLE_FG)

    # 进度条
    bar_w = int(W * 0.5)
    bar_h = max(5, int(H * 0.012))
    bx = m
    by = y_title + int(frame.f_title.size * 1.55)
    d.rounded_rectangle([bx, by, bx + bar_w, by + bar_h],
                        radius=bar_h // 2, fill=BAR_BG)
    fill_w = max(0, int(bar_w * max(0.0, min(1.0, progress))))
    if fill_w > 2:
        d.rounded_rectangle([bx, by, bx + fill_w, by + bar_h],
                            radius=bar_h // 2, fill=BAR_FG)
        hi = max(2, fill_w // 3)
        d.rounded_rectangle([bx + fill_w - hi, by, bx + fill_w, by + bar_h],
                            radius=bar_h // 2, fill=BAR_FG2)

    # 副标题(进度条下方左) + 百分比(右下角)
    y_sub = by + bar_h + 8
    d.text((bx, y_sub), sub_text, font=frame.f_sub, fill=SUB_FG)
    pct = "%d%%" % int(round(progress * 100))
    pw = d.textlength(pct, font=frame.f_pct)
    d.text((W - m - pw, y_sub + 1), pct, font=frame.f_pct, fill=SUB_FG)

    return out


def _run(image_path, min_seconds, text0):
    """splash 主循环(在自己的线程里)"""
    root = None
    try:
        import tkinter as tk
        from PIL import ImageTk

        frame = _measure(image_path)
        W, H = frame.W, frame.H

        root = tk.Tk()
        root.withdraw()
        for attr, val in (("-topmost", True), ("-alpha", 1.0)):
            try:
                root.attributes(attr, val)
            except Exception:
                pass
        try:
            root.overrideredirect(True)
        except Exception:
            pass

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = max(0, (sw - W) // 2)
        y = max(0, (sh - H) // 2)
        root.geometry("%dx%d+%d+%d" % (W, H, x, y))
        root.configure(bg="#000000")

        lbl = tk.Label(root, bd=0, highlightthickness=0, bg="#000000")
        lbl.pack(fill="both", expand=True)

        state = {"progress": 0.0, "sub": text0, "photo": None, "target": 0.0}

        def repaint():
            img = _paint(frame, state["progress"], state["sub"])
            ph = ImageTk.PhotoImage(img)
            lbl.configure(image=ph)
            state["photo"] = ph       # 防 GC

        repaint()
        try:
            root.deiconify()
        except Exception:
            pass
        try:
            root.lift()
        except Exception:
            pass

        t0 = time.time()
        close_at = None
        done = {"v": False}

        def finish():
            """在自己线程里干净地拆掉 tk 对象(避免 Tcl_AsyncDelete 跨线程报错)"""
            nonlocal root, lbl
            done["v"] = True
            try:
                lbl.configure(image="")
            except Exception:
                pass
            state["photo"] = None
            try:
                root.quit()
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass
            root = None
            lbl = None

        def poll():
            nonlocal close_at
            if done["v"]:
                return
            try:
                while True:
                    cmd = _QUEUE.get_nowait()
                    if cmd[0] == "progress":
                        state["progress"] = cmd[1]
                        if len(cmd) > 2 and cmd[2]:
                            state["sub"] = cmd[2]
                    elif cmd[0] == "close_now":
                        finish()
                        return
                    elif cmd[0] == "close":
                        elapsed = time.time() - t0
                        if elapsed < min_seconds:
                            close_at = t0 + min_seconds
                        else:
                            close_at = time.time()
            except queue.Empty:
                pass

            # 进度条动画:向 target 平滑靠拢
            cur = state["progress"]
            tgt = state["target"]
            if cur < tgt:
                state["progress"] = min(tgt, cur + max(0.012, (tgt - cur) * 0.18))
                repaint()

            if close_at is not None and time.time() >= close_at:
                finish()
                return
            try:
                root.after(33, poll)
            except Exception:
                pass

        def driver():
            """人为把进度从 0 推到 100,持续到 min_seconds,然后**主动关自己**。

            真实加载其实很快;这里**故意拉长**成一段好看的启动动画:
            ease-out 曲线,起步快、收尾稳,总时长 = min_seconds。

            ⚠️ 推完必须自己 close():否则没有任何东西会触发关闭,
            splash 会一直挂着,只能等 pet 那边的 _SPLASH_HARD_TIMEOUT 兜底
            (表现为"固定显示 8 秒",min_seconds 形同虚设)。
            """
            steps = max(1, int(min_seconds * 1000 / 33))
            for i in range(steps + 1):
                if done["v"]:
                    return
                p = i / steps
                eased = 1.0 - (1.0 - p) ** 2    # ease-out
                state["target"] = min(0.99, eased)
                time.sleep(0.033)
            if done["v"]:
                return
            state["target"] = 1.0
            # 到点了:给自己发 close,由 poll() 在 tk 线程里干净收尾
            try:
                _QUEUE.put(("close", None))
            except Exception:
                pass

        root.after(33, poll)
        threading.Thread(target=driver, daemon=True,
                         name="dspet-splash-drv").start()
        root.mainloop()
    except Exception:
        # 任何异常都不能影响主程序
        pass
    finally:
        try:
            if root is not None:
                root.destroy()
                root = None
        except Exception:
            pass
        _CLOSED.set()


def start(image_path, min_seconds=3.0, text="正在启动…"):
    """非阻塞启动 splash。重复调用无副作用。返回是否成功启动。"""
    global _QUEUE, _THREAD, _STARTED
    with _LOCK:
        if _STARTED:
            return True
        if not image_path or not os.path.exists(image_path):
            return False
        _QUEUE = queue.Queue()
        _STARTED = True
        _CLOSED.clear()
        _THREAD = threading.Thread(
            target=_run, args=(image_path, min_seconds, text),
            name="dspet-splash", daemon=True)
        _THREAD.start()
        return True


def set_progress(p, text=None):
    """更新进度(p: 0..1)与可选文字;未启动时静默忽略。"""
    q = _QUEUE
    if q is None:
        return
    try:
        q.put(("progress", float(p), text))
    except Exception:
        pass


def set_text(t):
    """只更新文字(兼容旧接口)。"""
    set_progress(-1, t)


def close():
    """请求关闭 splash;幂等,未启动时静默忽略。

    会保证最短展示时间(由 min_seconds 控制),所以"桌宠即将出现"这类
    需要立刻腾出屏幕的场景请用 close_now()。
    """
    q = _QUEUE
    if q is None:
        return
    try:
        q.put(("close", None))
    except Exception:
        pass


def close_now(timeout=1.0):
    """立刻关闭 splash,不等最短展示时间;并阻塞等它真正消失。

    ⚠️ 用于"桌宠窗口即将显示"这一刻:必须保证 splash 已经不在屏幕上,
    否则两者会同屏重叠。等超时就放行,绝不拖死主程序。
    """
    q = _QUEUE
    if q is None:
        return True
    try:
        q.put(("close_now", None))
    except Exception:
        pass
    return _CLOSED.wait(timeout)


def wait_closed(timeout=2.0):
    """等 splash 真正消失(主要供测试用)。"""
    return _CLOSED.wait(timeout)


def is_active():
    return _STARTED and not _CLOSED.is_set()
