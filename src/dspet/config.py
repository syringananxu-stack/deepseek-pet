# -*- coding: utf-8 -*-
"""配置读写:JSON + Windows DPAPI 加密 API Key(拿不到 DPAPI 就退化为明文并标注)"""
import base64
import json
import os
import threading

from .paths import config_path, log_path

_LOCK = threading.RLock()

DEFAULTS = {
    "api_key": "",              # 明文(仅在 DPAPI 不可用时使用)
    "api_key_enc": "",          # DPAPI 加密后的 base64
    "size_level": 1,            # 0..4
    "wander": True,             # 自主溜达
    "topmost": True,            # 窗口置顶
    "auto_hide_fullscreen": True,   # 全屏游戏自动让位
    "sounds": True,             # 音效
    "hard_delete": False,       # 喂文件:True=直接删,False=进回收站
    "refresh_sec": 30,          # 余额刷新间隔
    "chat": True,               # 碎嘴台词
    "pos": None,                # [x, y] 上次位置
    "first_run_done": False,
    "autostart": False,         # 仅记录状态,真实状态看启动文件夹
}


def _log(msg):
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _dpapi_crypt(data, unprotect=False):
    try:
        import win32crypt
        if unprotect:
            return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
        return win32crypt.CryptProtectData(data, "dspet", None, None, None, 0)
    except Exception:
        return None


def set_api_key(cfg, key):
    """把 key 写进 cfg(dict),尽量用 DPAPI 加密"""
    key = (key or "").strip()
    cfg["api_key"] = ""
    cfg["api_key_enc"] = ""
    if not key:
        return cfg
    enc = _dpapi_crypt(key.encode("utf-8"))
    if enc:
        cfg["api_key_enc"] = base64.b64encode(enc).decode("ascii")
    else:
        cfg["api_key"] = key
    return cfg


def get_api_key(cfg):
    enc = (cfg or {}).get("api_key_enc") or ""
    if enc:
        try:
            raw = _dpapi_crypt(base64.b64decode(enc), unprotect=True)
            if raw:
                return raw.decode("utf-8")
        except Exception as e:
            _log("decrypt api key failed: %r" % (e,))
    return (cfg or {}).get("api_key") or ""


def load():
    with _LOCK:
        cfg = dict(DEFAULTS)
        p = config_path()
        try:
            # utf-8-sig:兼容用户用记事本编辑后带 BOM 的情况
            with open(p, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    cfg[k] = v
        except FileNotFoundError:
            pass
        except Exception as e:
            _log("load config failed: %r" % (e,))
        return cfg


def save(cfg):
    with _LOCK:
        p = config_path()
        tmp = p + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
            return True
        except Exception as e:
            _log("save config failed: %r" % (e,))
            return False
