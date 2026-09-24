# -*- coding: utf-8 -*-
"""开机自启:在用户"启动"文件夹里放/删一个 .lnk(用 PowerShell 建,不依赖 COM 库)"""
import os
import subprocess
import sys

from . import APP_TITLE
from .paths import app_dir, is_frozen

LNK_NAME = "DeepSeekPet.lnk"
_CREATE_NO_WINDOW = 0x08000000


def _startup_dir():
    return os.path.join(os.environ.get("APPDATA", ""),
                        r"Microsoft\Windows\Start Menu\Programs\Startup")


def lnk_path():
    return os.path.join(_startup_dir(), LNK_NAME)


def is_enabled():
    return os.path.exists(lnk_path())


def _run_ps(script):
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=30,
                           creationflags=_CREATE_NO_WINDOW)
        return p.returncode == 0, (p.stderr or "").strip()
    except Exception as e:
        return False, str(e)


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def enable():
    """创建自启快捷方式;返回 (ok, msg)"""
    if is_frozen():
        target = sys.executable
        args = ""
        workdir = os.path.dirname(target)
    else:
        # 源码运行:用 pythonw.exe 跑 -m dspet(工作目录指向 src,保证能 import dspet)
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        target = exe if os.path.exists(exe) else sys.executable
        args = "-m dspet"
        workdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = os.path.join(app_dir(), "dspet.ico")
    if not os.path.exists(icon):
        icon = target
    ps = (
        "$ws = New-Object -ComObject WScript.Shell;"
        "$l = $ws.CreateShortcut(%s);"
        "$l.TargetPath = %s;"
        "$l.Arguments = %s;"
        "$l.WorkingDirectory = %s;"
        "$l.IconLocation = %s;"
        "$l.Description = %s;"
        "$l.Save()"
    ) % (_ps_quote(lnk_path()), _ps_quote(target), _ps_quote(args),
         _ps_quote(workdir), _ps_quote(icon + ",0"),
         _ps_quote(APP_TITLE))
    ok, err = _run_ps(ps)
    if ok and is_enabled():
        return True, "已开启开机自启"
    return False, err or "创建快捷方式失败"


def disable():
    try:
        if os.path.exists(lnk_path()):
            os.remove(lnk_path())
        return True, "已关闭开机自启"
    except Exception as e:
        return False, str(e)


def apply(want):
    if want and not is_enabled():
        return enable()
    if not want and is_enabled():
        return disable()
    return True, ""
