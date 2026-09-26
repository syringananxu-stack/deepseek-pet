# -*- coding: utf-8 -*-
"""路径工具:兼容"源码运行"与"PyInstaller 打包后运行"两种形态"""
import os
import sys

from . import APP_NAME


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    """程序所在目录(frozen=exe 所在目录;源码=项目根目录)"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    # src/dspet/paths.py -> 上三级 = 项目根
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(*parts):
    """只读资源(素材)路径:打包后在 _MEIPASS/assets,源码在 dspet/assets"""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", *parts)


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".dspet_write_test")
        with open(t, "w") as f:
            f.write("1")
        os.remove(t)
        return True
    except Exception:
        return False


def _portable_dir():
    """跟 exe 放一起的那种"绿色免安装"配置目录"""
    return app_dir()


def _roaming_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


CONFIG_DIR = None


def config_dir():
    """配置存放目录:优先程序同目录(便携),不可写则退回 %APPDATA%"""
    global CONFIG_DIR
    if CONFIG_DIR:
        return CONFIG_DIR
    d = _portable_dir()
    if not _writable(d):
        d = _roaming_dir()
        os.makedirs(d, exist_ok=True)
    CONFIG_DIR = d
    return d


def config_path():
    return os.path.join(config_dir(), "config.json")


def log_path():
    return os.path.join(config_dir(), "dspet.log")
