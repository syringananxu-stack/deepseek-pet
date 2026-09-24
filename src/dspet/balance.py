# -*- coding: utf-8 -*-
"""DeepSeek 官方余额接口 + 峰谷时段计算(峰谷是纯本地算的,不联网)"""
import datetime as dt
import json
import urllib.request

API = "https://api.deepseek.com/user/balance"
PEAK = [(9, 12), (14, 18)]          # 工作日高峰时段(北京时间)


class BalanceError(Exception):
    pass


def fetch_balance(key, timeout=15):
    """返回 (可用余额, 币种)。只读接口,不消耗 token。"""
    if not key:
        raise BalanceError("未设置 API Key")
    req = urllib.request.Request(API)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise BalanceError(_friendly(e))
    infos = data.get("balance_infos") or []
    if not infos:
        raise BalanceError("接口没返回余额信息")
    info = infos[0]
    try:
        return float(info.get("total_balance")), info.get("currency") or "CNY"
    except Exception:
        raise BalanceError("余额字段解析失败")


def _friendly(e):
    s = str(e)
    if "401" in s or "403" in s:
        return "API Key 无效或被拒(401/403)"
    if "timed out" in s.lower() or "timeout" in s.lower():
        return "网络超时,检查网络"
    if "URLError" in s or "getaddrinfo" in s:
        return "连不上 api.deepseek.com"
    return s[:48]


def peak_info(now=None):
    """返回 (是否高峰, 距离状态切换还有多少秒)"""
    now = now or dt.datetime.now()
    wd, mins = now.weekday(), now.hour * 60 + now.minute + now.second / 60.0
    if wd >= 5:                                     # 周末:全程低谷
        left = ((7 - wd) * 1440 + PEAK[0][0] * 60) - mins
        return False, int(left * 60)
    for a, b in PEAK:
        if a * 60 <= mins < b * 60:
            return True, int((b * 60 - mins) * 60)
    for a, b in PEAK:
        if mins < a * 60:
            return False, int((a * 60 - mins) * 60)
    left = ((3 if wd == 4 else 1) * 1440 + PEAK[0][0] * 60) - mins
    return False, int(left * 60)


def hms(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return "%d:%02d:%02d" % (h, m, s)
