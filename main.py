# -*- coding: utf-8 -*-
"""打包/源码统一入口:把 dspet.__main__ 的异常写进日志,避免 windowed 模式"静默死亡"。"""
import os
import sys
import traceback


def _bootstrap_path():
    if not getattr(sys, "frozen", False):
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
        if src not in sys.path:
            sys.path.insert(0, src)


def _log_exception(exc_text):
    try:
        from dspet.paths import log_path
        p = log_path()
    except Exception:
        p = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "dspet.log")
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(exc_text + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    _bootstrap_path()
    try:
        from dspet.__main__ import main
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        _log_exception(traceback.format_exc())
        raise
