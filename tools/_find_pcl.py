# -*- coding: utf-8 -*-
import os
import subprocess

import win32com.client

lnk = r"C:\Users\admin\Desktop\Plain Craft Launcher 2.lnk"
sh = win32com.client.Dispatch("WScript.Shell")
s = sh.CreateShortCut(lnk)
print("target:", s.TargetPath)
print("workdir:", s.WorkingDirectory)
print("args:", s.Arguments)
d = s.WorkingDirectory or os.path.dirname(s.TargetPath)
print("--- dir listing ---")
for n in sorted(os.listdir(d))[:40]:
    p = os.path.join(d, n)
    print("   ", n, "(dir)" if os.path.isdir(p) else "%.1f MB" % (os.path.getsize(p) / 1048576))
