# -*- coding: utf-8 -*-
"""源码方式启动(开发/调试用):python run_dev.py [--debug]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

if "--debug" in sys.argv:
    os.environ["DSPET_DEBUG"] = "1"

from dspet.__main__ import main   # noqa: E402

sys.exit(main())
