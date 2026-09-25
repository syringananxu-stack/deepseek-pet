# -*- coding: utf-8 -*-
"""内存优化机制试验:提权 → 清待机内存 / 清工作集,看前后内存变化"""
import ctypes
import ctypes.wintypes as w

ntdll = ctypes.windll.ntdll
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

SystemMemoryListInformation = 0x50        # 80
MemoryEmptyWorkingSets = 2
MemoryFlushModifiedList = 3
MemoryPurgeStandbyList = 4
MemoryPurgeLowPriorityStandbyList = 5


class PERF(ctypes.Structure):
    _fields_ = [("cb", w.DWORD)] + [(n, ctypes.c_size_t) for n in
                ("CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal",
                 "PhysicalAvailable", "SystemCache", "KernelTotal", "KernelPaged",
                 "KernelNonpaged", "PageSize", "HandleCount", "ProcessCount",
                 "ThreadCount")]


def perf():
    p = PERF()
    p.cb = ctypes.sizeof(PERF)
    psapi.GetPerformanceInfo(ctypes.byref(p), p.cb)
    return p


def show(tag):
    p = perf()
    print("%-8s 可用 %6.2f GB | 系统缓存 %6.2f GB | 提交 %5.2f GB" % (
        tag, p.PhysicalAvailable * p.PageSize / 2**30,
        p.SystemCache * p.PageSize / 2**30, p.CommitTotal * p.PageSize / 2**30))
    return p


def enable_priv(name="SeProfileSingleProcessPrivilege"):
    TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY = 0x20, 0x8
    SE_PRIVILEGE_ENABLED = 0x2

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", w.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", w.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    tk = w.HANDLE()
    if not ctypes.windll.advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                                   TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                                   ctypes.byref(tk)):
        return "OpenProcessToken 失败"
    luid = LUID()
    if not ctypes.windll.advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        return "LookupPrivilegeValue 失败(没有这个特权)"
    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
    ok = ctypes.windll.advapi32.AdjustTokenPrivileges(tk, False, ctypes.byref(tp),
                                                      ctypes.sizeof(tp), None, None)
    err = ctypes.get_last_error()
    if not ok:
        return "AdjustTokenPrivileges 失败 err=%s" % err
    if err == 1300:                       # ERROR_NOT_ALL_ASSIGNED
        return "特权不在令牌里(需要管理员)"
    return "OK"


print("管理员:", bool(ctypes.windll.shell32.IsUserAnAdmin()))
p0 = show("初始")
print("提权:", enable_priv())
for cmd, nm in ((MemoryPurgeStandbyList, "清待机内存"),
                (MemoryEmptyWorkingSets, "清工作集"),
                (MemoryFlushModifiedList, "刷修改页")):
    c = ctypes.c_ulong(cmd)
    st = ntdll.NtSetSystemInformation(SystemMemoryListInformation, ctypes.byref(c), 4)
    print("  %-8s NTSTATUS=0x%08X %s" % (nm, st & 0xFFFFFFFF,
                                         "(成功)" if st == 0 else "(失败)"))
    show(nm)
show("结束")
