# DeepSeek 大肥鱼 · 桌面桌宠 (DeepSeekPet)

一只趴在 Windows 桌面上的小蓝鱼桌宠。会自己溜达、被拎起来会拉长成史莱姆、单击她能看到你
DeepSeek 账户余额和"高峰/低谷"时段、把文件拖到她身上可以"喂"掉。

* **纯本地运行** —— 断网也能用,所有动画和交互都在本机。
* **唯一的联网点**是查余额时调一次 DeepSeek 官方**只读**接口( `/user/balance` ),
  用你自己的 API Key,**不消耗 token、不产生费用**。
* **不填 Key 也能用**,只是不显示余额。

---

## 一、怎么用(免安装)

1. 解压 `DeepSeekPet-v0.2.0-win64.zip` 到任意目录(桌面、D 盘都行,别放需要管理员权限的地方)。
2. 双击 **`DeepSeekPet.exe`**。第一次启动会自动弹出**设置窗口**。
3. (可选)把 DeepSeek 的 API Key 粘进去 → 点「测试连接」确认 → 「保存并应用」。
   * 申请地址:<https://platform.deepseek.com> → API Keys → 创建。
   * Key 会加密后存在本机(Windows DPAPI,只有当前 Windows 用户能解开)。
4. 想开机自动出现 → 设置里勾上「登录 Windows 后自动启动」。

> 首次运行 Windows 可能弹 "SmartScreen 已阻止" —— 点「更多信息」→「仍要运行」即可
> (程序没做数字签名,自己人用没问题)。

### 操作一览

| 操作 | 效果 |
| --- | --- |
| 左键单击 | 显示余额 + 高峰/低谷倒计时(没填 Key 会直接弹设置) |
| 左键拖动 | 把她拎走,松手会自己弹回去 |
| 右键 | 菜单:设置 / 看余额 / 弹一下 / 换一句 / 溜达开关 / 置顶 / 大小 / 退出 |
| 把文件拖到她身上 | "喂"掉文件(有确认框;默认丢进回收站,可改成彻底删除) |
| 双击气泡 | 收起气泡 |

### 置顶 & 全屏游戏

默认**置顶**,会压在普通窗口、浏览器上面;但**玩全屏游戏时会自动躲起来**,退出游戏又自己回来。
在设置里可以关掉「全屏游戏自动让位」,那样她就会一直压在最上面。

## 二、配置文件在哪

优先放在**程序同目录**的 `config.json`(便携、可整个文件夹拷走);如果那个目录不可写
(例如塞进了 `C:\Program Files`),会自动改用 `%APPDATA%\DeepSeekPet\config.json`。

同一目录下还会有 `dspet.log`(出问题时的日志)。

## 三、卸载

1. 设置里取消勾选「开机自启」(或手动删掉
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DeepSeekPet.lnk`)。
2. 直接删掉整个程序文件夹(和 `%APPDATA%\DeepSeekPet`,如果有)。

## 四、系统要求

* Windows 10 / 11(x64)
* 免安装版无需 Python;源码运行需要 Python 3.10+ 和 `requirements.txt` 里的依赖

## 五、从源码运行 / 自己打包

```powershell
# 开发运行(控制台可见日志)
python run_dev.py --debug

# 打包(需要 pyinstaller;建议 Python 3.12)
powershell -ExecutionPolicy Bypass -File build\build.ps1
# 产物: dist\DeepSeekPet\  +  dist\DeepSeekPet-v0.2.0-win64.zip
```

依赖:`pywin32`、`pillow`、`numpy`(numpy 只用于把位图快速转成半透明位图,没有会自动降级)。

## 六、许可与致谢

* 本程序:**MIT License**(见 `LICENSE`)—— 可自由使用、修改、分发。
* 美术 / 音效素材来自 **「大肥鱼 - 余额挂件 v0.3.0」**(© @月匠 / MeteorNOX,MIT),
  参考了 **whale-purse**(© Suiwan,MIT)。详见 `THIRD_PARTY.md`。
