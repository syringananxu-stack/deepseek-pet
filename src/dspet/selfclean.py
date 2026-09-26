# -*- coding: utf-8 -*-
"""启动自清洁:清掉本程序(以及同类单文件程序)在 %TEMP% 留下的解包残渣。

为什么需要它
------------
PyInstaller 单文件版每次运行都要把整个包解到 %TEMP%\\_MEIxxxxxx,
正常退出时由 bootloader 自己删。但**异常退出 / 被强杀 / 多开 / 断电**时
这个目录会留下 —— 每份约 80MB。东家反复启动 → Temp 越堆越大(实测一天堆 1.4GB)。

策略(安全第一)
--------------
1. 只在**启动早期**跑一次,失败绝不抛异常、绝不影响主程序。
2. 只删名字匹配 `_MEI*` 且**位于系统 Temp** 的目录。
3. **跳过本进程自己的解包目录**(sys._MEIPASS)——那是正在用的。
4. **跳过最近 N 分钟内的**(默认 30 分钟)——避免误删别的正在启动的同款程序。
5. 删不掉就跳过(被占用 / 权限),不留后患。
"""
import os
import shutil
import sys
import tempfile
import time

# 只认这种前缀的目录(PyInstaller onefile 解包目录)
_PREFIX = "_MEI"
# 另外清掉这些程序留下的解包/构建残渣(前缀匹配,位于系统 Temp)
_OTHER_PREFIXES = (
    "openclaw-plugin-build-",   # OpenClaw 插件构建临时目录(每次约 45~68MB,不自清)
    "IIFC",                     # Intel 驱动安装器临时解包目录
)
# 跳过最近这么多秒内动过的(可能是别的进程正在解包)
# 60 分钟:插件构建/驱动安装可能跑很久,放宽窗口防误删活进程
_MIN_AGE_SEC = 60 * 60


def _temp_roots():
    """系统 Temp 候选目录(去重,只保留存在的)"""
    cands = []
    for key in ("TEMP", "TMP"):
        v = os.environ.get(key)
        if v:
            cands.append(v)
    try:
        cands.append(tempfile.gettempdir())
    except Exception:
        pass
    cands.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"))

    out, seen = [], set()
    for c in cands:
        if not c:
            continue
        c = os.path.abspath(c)
        k = c.lower()
        if k not in seen and os.path.isdir(c):
            seen.add(k)
            out.append(c)
    return out


def _own_dir():
    """本进程自己的解包目录(存在则要跳过)"""
    d = getattr(sys, "_MEIPASS", None)
    return os.path.abspath(d).lower() if d else None


def _matches(name):
    """该目录名是否属于要清理的残渣类型"""
    return name.startswith(_PREFIX) or name.startswith(_OTHER_PREFIXES)


def clean_mei_residue(min_age_sec=_MIN_AGE_SEC, dry=False):
    """清掉 Temp 里的 _MEI* 残渣。返回 (删除数量, 释放字节数)。

    dry=True 时只统计不删(给测试/预览用)。
    """
    own = _own_dir()
    now = time.time()
    freed = 0
    removed = 0

    for root in _temp_roots():
        try:
            names = os.listdir(root)
        except Exception:
            continue
        for name in names:
            if not _matches(name):
                continue
            path = os.path.join(root, name)
            ap = os.path.abspath(path)
            try:
                if not os.path.isdir(ap):
                    continue
            except Exception:
                continue
            if own and ap.lower() == own:          # 自己正在用 → 跳过
                continue
            try:
                if now - os.path.getmtime(ap) < min_age_sec:   # 太新 → 可能是活的
                    continue
            except Exception:
                continue
            # 累计大小
            size = 0
            try:
                for dirpath, _dirs, files in os.walk(ap):
                    for fn in files:
                        try:
                            size += os.path.getsize(os.path.join(dirpath, fn))
                        except Exception:
                            pass
            except Exception:
                pass
            if dry:
                removed += 1
                freed += size
                continue
            try:
                shutil.rmtree(ap, ignore_errors=False)
                removed += 1
                freed += size
            except Exception:
                # 删不动(占用/权限)→ 跳过,不影响启动
                continue
    return removed, freed


def clean_on_startup():
    """启动时调用:静默清理,绝不抛异常。"""
    try:
        n, freed = clean_mei_residue()
        if n:
            try:
                from .paths import log_path
                with open(log_path(), "a", encoding="utf-8") as f:
                    f.write("[selfclean] 清理 %d 个 _MEI 残渣,释放 %.1f MB\n"
                            % (n, freed / 1024.0 / 1024.0))
            except Exception:
                pass
        return n, freed
    except Exception:
        return 0, 0
