# -*- coding: utf-8 -*-
"""入口:python -m dspet"""
import os
import sys


def _single_instance():
    """同一台机器只允许一只大肥鱼(自启 + 手动启动不会变成两只)"""
    import ctypes
    h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DeepSeekPetFishSingleton")
    return h, ctypes.windll.kernel32.GetLastError() != 183


def main():
    _h, first = _single_instance()
    if not first:
        return 0
    from .pet import Pet
    from .paths import resource_path

    if not os.path.exists(resource_path("DSniang1.png")):
        sys.stderr.write("assets missing: %s\n" % resource_path("DSniang1.png"))
        return 2
    Pet().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
