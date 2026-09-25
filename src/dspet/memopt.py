# -*- coding: utf-8 -*-
"""内存优化(对标 PCL2「Plain Craft Launcher 2」的内存优化)

做了什么:
  1. 清空**系统待机内存**(Standby List)——
     `NtSetSystemInformation(SystemMemoryListInformation, MemoryPurgeStandbyList)`
     这是 PCL2/纯净启动器那类"内存优化"的真正主体,能把系统缓存里 3~10 GB 的
     待机页还回空闲内存池。**需要管理员**(SeProfileSingleProcessPrivilege)。
  2. 刷**修改页**(MemoryFlushModifiedList)—— 把脏页落盘,不需要管理员。
  3. (可选)清**工作集**(MemoryEmptyWorkingSets)—— 更狠,所有进程的工作集被清空,
     程序下次访问要重新缺页,可能会卡一下;PCL2 的"极度"档就是它。默认不开。

非管理员时的做法:用 UAC 把自己以 `--mem-purge` 再启动一次(那个实例只干活、不建窗口、
不抢互斥体),干完就退出,这边等它结束再读内存数字。
"""
import ctypes
import ctypes.wintypes as w
import os
import sys
import time

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
psapi = ctypes.windll.psapi
advapi32 = ctypes.windll.advapi32
shell32 = ctypes.windll.shell32

SYSTEM_MEMORY_LIST_INFORMATION = 0x50          # 80
CMD_EMPTY_WORKING_SETS = 2
CMD_FLUSH_MODIFIED_LIST = 3
CMD_PURGE_STANDBY_LIST = 4

STATUS_SUCCESS = 0
STATUS_PRIVILEGE_NOT_HELD = 0xC0000061

# ---------- 取内存数字 ----------


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", w.DWORD), ("dwMemoryLoad", w.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [("cb", w.DWORD)] + [
        (n, ctypes.c_size_t) for n in
        ("CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable",
         "SystemCache", "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize",
         "HandleCount", "ProcessCount", "ThreadCount")]


def snapshot():
    """当前内存快照(字节):total/avail 物理内存 + 系统缓存(待机)+ 占用率"""
    ms = MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    pi = PERFORMANCE_INFORMATION()
    pi.cb = ctypes.sizeof(PERFORMANCE_INFORMATION)
    psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
    return {"total": int(ms.ullTotalPhys), "avail": int(ms.ullAvailPhys),
            "cache": int(pi.SystemCache) * int(pi.PageSize),
            "load": int(ms.dwMemoryLoad)}


def gb(n):
    return n / float(1 << 30)


def is_admin():
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------- 提权 ----------


def enable_privilege(name="SeProfileSingleProcessPrivilege"):
    """把特权塞进本进程令牌。返回 (ok, 说明)"""
    TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY, SE_PRIVILEGE_ENABLED = 0x20, 0x8, 0x2

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", w.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", w.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    advapi32.OpenProcessToken.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.HANDLE)]
    advapi32.LookupPrivilegeValueW.argtypes = [w.LPCWSTR, w.LPCWSTR, ctypes.POINTER(LUID)]
    advapi32.AdjustTokenPrivileges.argtypes = [w.HANDLE, w.BOOL, ctypes.c_void_p, w.DWORD,
                                               ctypes.c_void_p, ctypes.c_void_p]
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p

    tk = w.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                     TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(tk)):
        return False, "打不开进程令牌"
    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        return False, "本机没有这个特权"
    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
    ctypes.set_last_error(0)
    ok = advapi32.AdjustTokenPrivileges(tk, False, ctypes.byref(tp),
                                        ctypes.sizeof(tp), None, None)
    err = ctypes.get_last_error()
    kernel32.CloseHandle(tk)
    if not ok:
        return False, "设置特权失败(err=%s)" % err
    if err == 1300:                            # ERROR_NOT_ALL_ASSIGNED
        return False, "特权不在当前令牌里(要管理员)"
    return True, "OK"


# ---------- 真正干活 ----------


def _call(cmd):
    ntdll.NtSetSystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long
    c = ctypes.c_ulong(cmd)
    return ntdll.NtSetSystemInformation(SYSTEM_MEMORY_LIST_INFORMATION,
                                        ctypes.byref(c), 4) & 0xFFFFFFFF


def purge(empty_working_sets=False):
    """执行清理,返回各步的 NTSTATUS(0=成功)"""
    enable_privilege()
    out = {"standby": _call(CMD_PURGE_STANDBY_LIST),
           "flush": _call(CMD_FLUSH_MODIFIED_LIST),
           "ws": None}
    if empty_working_sets:
        out["ws"] = _call(CMD_EMPTY_WORKING_SETS)
    return out


def self_command(flag="--mem-purge"):
    """再启动一个自己(提权用)"""
    if getattr(sys, "frozen", False):
        return [sys.executable, flag]
    return [sys.executable, os.path.abspath(sys.argv[0]), flag]


def run_elevated(flag="--mem-purge", timeout=60):
    """UAC 提权跑一次自己。返回 (ok, 说明)"""
    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", w.DWORD), ("fMask", ctypes.c_ulong),
                    ("hwnd", ctypes.c_void_p), ("lpVerb", w.LPCWSTR),
                    ("lpFile", w.LPCWSTR), ("lpParameters", w.LPCWSTR),
                    ("lpDirectory", w.LPCWSTR), ("nShow", ctypes.c_int),
                    ("hInstApp", ctypes.c_void_p), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", w.LPCWSTR), ("hkeyClass", ctypes.c_void_p),
                    ("dwHotKey", w.DWORD), ("hIcon", ctypes.c_void_p),
                    ("hProcess", ctypes.c_void_p)]

    cmd = self_command(flag)
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    sei.fMask = 0x00000040                      # SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = cmd[0]
    sei.lpParameters = " ".join('"%s"' % a for a in cmd[1:]) if len(cmd) > 1 else None
    sei.lpDirectory = os.path.dirname(cmd[0]) or None
    sei.nShow = 0                               # SW_HIDE:只弹 UAC,不闪窗口
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = w.BOOL
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        e = ctypes.get_last_error()
        if e == 1223:                           # ERROR_CANCELLED
            return False, "已取消(没点同意管理员)"
        return False, "启动失败(err=%s)" % e
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, w.DWORD]
    if sei.hProcess:
        kernel32.WaitForSingleObject(sei.hProcess, int(timeout * 1000))
        kernel32.CloseHandle(sei.hProcess)
    return True, "OK"


def optimize(empty_working_sets=False, do_elevate=True):
    """一键内存优化:非管理员时自动弹一次 UAC。返回 (ok, 结果dict)"""
    if os.environ.get("DSPET_MEMOPT_NOELEVATE"):     # 测试用:不提权
        do_elevate = False
    before = snapshot()
    st = {"standby": None, "flush": None, "ws": None, "elevated": False, "msg": ""}
    st.update(purge(empty_working_sets))             # 先就地试一把(管理员的话这步就成了)
    if st["standby"] != STATUS_SUCCESS and do_elevate and not is_admin():
        ok, msg = run_elevated("--mem-purge" + (" --mem-ws" if empty_working_sets else ""))
        st["msg"] = msg
        if ok:
            st["elevated"] = True
            st["standby"] = STATUS_SUCCESS
            if empty_working_sets:
                st["ws"] = STATUS_SUCCESS
    time.sleep(0.7)
    after = snapshot()
    freed = before["cache"] - after["cache"]
    st["freed"] = freed
    return True, {"before": before, "after": after, "status": st}


def helper_main():
    """`--mem-purge` 模式:提权后的自己只干这一件事,然后退出"""
    try:
        r = purge("--mem-ws" in sys.argv)
    except Exception:
        r = {"error": True}
    try:
        import json
        import tempfile
        p = os.path.join(tempfile.gettempdir(), "dspet_mempurge.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(r))
    except Exception:
        pass
    return 0


def state_line(s):
    """当前状态一行:总内存 / 已占用 / 可用"""
    used = s["total"] - s["avail"]
    return "总内存 %.1f GB · 已占用 %.2f GB · 可用 %.2f GB" % (
        gb(s["total"]), gb(used), gb(s["avail"]))


def lines_now():
    return state_line(snapshot())


def report(res):
    """结果两行:①总内存/已占用/可用 ②本次释放(含系统缓存前后)"""
    b, a, st = res["before"], res["after"], res["status"]
    freed = max(0, b["cache"] - a["cache"])
    l1 = state_line(a)
    if st.get("standby") == STATUS_SUCCESS:
        l2 = "本次释放 %.2f GB(系统缓存 %.2f → %.2f GB)" % (
            gb(freed), gb(b["cache"]), gb(a["cache"]))
    elif st.get("msg"):
        l2 = "本次释放 0.00 GB · %s" % st["msg"]
    else:
        l2 = "本次释放 0.00 GB(清系统缓存需要管理员权限)"
    return l1, l2


def text_of(res):
    """一行版(给测试/日志用)"""
    return " · ".join(report(res))
