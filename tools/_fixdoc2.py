# -*- coding: utf-8 -*-
import io
import os

p = os.path.join(r'D:\Temp\dspet_pkg', u'使用说明.txt')
s = io.open(p, encoding='utf-8-sig').read()
bad = u'· 效果看结果那两行(总内存 / 已占用 / 可用 + 本次释放)。原文:效果看结果那行:"已释放 x GB 缓存 · 可用 x GB · 已缓存 x GB"。'
good = u'· 效果看结果那两行:第一行是「总内存 / 已占用 / 可用」,第二行是「本次释放 xx GB(系统缓存 a → b)」。'
if bad in s:
    s = s.replace(bad, good)
    print('patched')
else:
    print('WARN: 没找到目标文本')
s = s.replace(u'v0.4.0', u'v0.4.1')
io.open(p, 'w', encoding='utf-8').write(s)
i = s.find(u'【工具箱')
io.open(r'D:\Temp\doc_part.txt', 'w', encoding='utf-8').write(s[i:i + 330])
print('v0.4.0 left:', u'v0.4.0' in s)
