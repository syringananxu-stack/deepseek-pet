# -*- coding: utf-8 -*-
"""内存优化自测(非提权):快照 + 清待机内存(预期缺特权)+ 刷修改页(预期成功)"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet import memopt                                    # noqa: E402

print("管理员:", memopt.is_admin())
s0 = memopt.snapshot()
print("初始: 总 %.1f GB 可用 %.2f GB 系统缓存 %.2f GB 占用 %d%%" % (
    memopt.gb(s0["total"]), memopt.gb(s0["avail"]), memopt.gb(s0["cache"]), s0["load"]))
print("特权:", memopt.enable_privilege())
r = memopt.purge()
print("清待机内存 NTSTATUS=0x%08X %s" % (r["standby"], "(成功)" if r["standby"] == 0 else "(缺管理员)"))
print("刷修改页   NTSTATUS=0x%08X %s" % (r["flush"], "(成功)" if r["flush"] == 0 else "(失败)"))
s1 = memopt.snapshot()
print("之后: 可用 %.2f GB 系统缓存 %.2f GB" % (memopt.gb(s1["avail"]), memopt.gb(s1["cache"])))
ok = (r["flush"] == 0) and (r["standby"] in (0, 0xC0000061))
print("RESULT:", "PASS" if ok else "FAIL")
