# -*- coding: utf-8 -*-
"""功能自测:改开关 → 保存并应用 → 配置落盘 → 窗口收场(测完一定还原)"""
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet import config                                    # noqa: E402
from dspet.paths import config_path                         # noqa: E402
from dspet.settings_ui import SettingsWindow                # noqa: E402


def say(*a):
    s = " ".join(str(x) for x in a)
    sys.stdout.write(s.encode("gbk", "replace").decode("gbk") + "\n")


path = config_path()
say("config:", path)
backup = path + ".bak"
if not os.path.exists(backup):
    shutil.copyfile(path, backup)
else:
    shutil.copyfile(backup, path)      # 先把上次崩掉的现场还原
    say("(上次没还原干净,已先还原)")

try:
    cfg = config.load()
    before_snd = bool(cfg.get("sounds", True))
    say("before sounds =", before_snd)

    w = SettingsWindow(cfg)
    w.root.update()
    w.var_snd.set(not before_snd)
    w.var_chat.set(False)
    w.root.update()
    w._save()
    say("保存后按钮:", w.btn_save.itemcget(w.btn_save._tid, "text").encode("gbk", "replace").decode("gbk"))

    t = time.time()
    while not w._closing and time.time() - t < 3:
        w.root.update()
        time.sleep(0.02)
    t = time.time()
    while time.time() - t < 1.5:
        try:
            w.root.update()
        except Exception:
            break
        time.sleep(0.02)

    saved = json.load(io.open(path, encoding="utf-8-sig"))
    ok1 = saved.get("sounds") == (not before_snd)
    ok2 = saved.get("chat") is False
    say("saved sounds =", saved.get("sounds"), "| chat =", saved.get("chat"))
    keys = ("size_level", "wander", "calm", "topmost", "auto_hide_fullscreen", "sounds",
            "chat", "hard_delete", "refresh_sec", "autostart", "first_run_done")
    say("keys ok:", all(k in saved for k in keys), "| 有 api_key_enc:", "api_key_enc" in saved)
    say("RESULT:", "PASS" if (ok1 and ok2) else "FAIL")
finally:
    shutil.copyfile(backup, path)
    os.remove(backup)
    restored = json.load(io.open(path, encoding="utf-8-sig"))
    say("restored sounds =", restored.get("sounds"), "| chat =", restored.get("chat"))
