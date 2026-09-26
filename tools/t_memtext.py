# -*- coding: utf-8 -*-
"""report() 文案自测(含"成功释放"和"没权限"两种情况)"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

from dspet import memopt                                   # noqa: E402

GB = 1 << 30
mk = lambda t, a, c: {"total": int(t * GB), "avail": int(a * GB),
                      "cache": int(c * GB), "load": int(100 * (1 - a / t))}

# 情况1:成功清掉(缓存 11.79 -> 1.20)
res = {"before": mk(31.4, 20.56, 11.79), "after": mk(31.4, 31.10, 1.20),
       "status": {"standby": 0, "flush": 0, "ws": None, "elevated": True, "msg": "OK"}}
print("== 成功 ==")
print("\n".join(memopt.report(res)).encode("gbk", "replace").decode("gbk"))
# 情况2:取消 UAC
res2 = {"before": mk(31.4, 20.56, 11.79), "after": mk(31.4, 20.60, 11.78),
        "status": {"standby": 0xC0000061, "flush": 0, "ws": None,
                   "elevated": False, "msg": "已取消(没点同意管理员)"}}
print("== 取消 UAC ==")
print("\n".join(memopt.report(res2)).encode("gbk", "replace").decode("gbk"))
print("当前:", memopt.lines_now().encode("gbk", "replace").decode("gbk"))
r1 = memopt.report(res)[1]
r2 = memopt.report(res2)[1]
# 成功档:应含“本次释放”+“安全档”(默认非深度) 且算出的释放量 = 可用增量 10.54 GB
ok = ("本次释放 10.54 GB" in r1) and ("安全档" in r1) and ("已取消" in r2)
print("RESULT:", "PASS" if ok else "FAIL")
