# -*- coding: utf-8 -*-
"""看 PCL2 的"内存优化"到底调了哪些 API(在 exe 里找字符串)"""
import re

p = r"D:\PCL2\Plain Craft Launcher 2.exe"
data = open(p, "rb").read()
try:
    txt = data.decode("utf-16-le", "ignore")
except Exception:
    txt = ""
txt2 = data.decode("utf-8", "ignore")
blob = txt + "\n" + txt2

keys = ["NtSetSystemInformation", "SystemMemoryListInformation", "MemoryPurgeStandbyList",
        "EmptyWorkingSet", "SetProcessWorkingSetSize", "SetSystemFileCacheSize",
        "SeProfileSingleProcessPrivilege", "AdjustTokenPrivileges", "psapi",
        "内存优化", "优化内存", "释放内存", "待机", "StandbyList", "MemoryEmptyWorkingSets",
        "SystemFileCacheInformation", "SystemCombinePhysicalMemoryInformation"]
for k in keys:
    n = blob.count(k)
    print("%-34s %d" % (k, n))
# 抓一些上下文
for k in ["NtSetSystemInformation", "EmptyWorkingSet", "SetSystemFileCacheSize", "SeProfileSingleProcessPrivilege"]:
    for m in list(re.finditer(re.escape(k), blob))[:2]:
        s = blob[max(0, m.start() - 90):m.start() + 90].replace("\n", " ")
        print("---", k, "::", s.encode("gbk", "replace").decode("gbk"))
