# -*- coding: utf-8 -*-
import io
p = u'D:\\Temp\\dspet_pkg\\使用说明.txt'
s = io.open(p, encoding='utf-8-sig').read()
s = s.replace(u'v0.3.2', u'v0.3.3')
old = u'【右键菜单】只有两项:打开设置界面… / 退出桌宠。'
new = u'【右键菜单】只有两项:打开设置界面… / 退出桌宠。设置只能从这里进(点桌宠不会弹窗)。'
if old in s:
    s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8').write(s)
print(u'首行:', s.splitlines()[0])
print(u'有右键说明:', u'点桌宠不会弹窗' in s)
print(u'版本号全对:', u'0.3.2' not in s)
