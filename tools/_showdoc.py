# -*- coding: utf-8 -*-
import io
p = u'D:\\Temp\\dspet_pkg\\使用说明.txt'
s = io.open(p, encoding='utf-8-sig').read()
io.open(r'D:\Temp\doc_now.txt', 'w', encoding='utf-8').write(s)
print('copied', len(s))
