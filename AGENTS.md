# AGENTS.md

本文件是本仓库的开发规范与操作手册。**任何 Agent 动手前先读完本文件。**

> 本文件由东家(仓库所有者)的通用开发规范 + 本仓库实测事实合成。
> 最后更新:2026-09-26。

---

## 0. 三条硬约束(先读这个)

1. **每天晚上 23:00 断电**。长任务 22:30 前收尾;每步必须**可续跑、可断点续做**。
2. **一律放 D 盘**。仓库在 `D:\Projects\`,下载/临时/venv/打包产物全走 D 盘,C 盘敏感。
3. **不把本机私密信息发给任何外部服务**(路径、API Key、账号、截图)。涉及本机状态的活绝不外包。

---

## 1. 项目概述

**DeepSeek 大肥鱼桌宠(DeepSeekPet)** —— 趴在 Windows 桌面上的 PySide6/ctk 桌宠。

| 事实 | 值 |
| --- | --- |
| 语言 / 运行时 | Python 3.10+(实测 3.12.8 打包、3.14.7 可跑源码) |
| 当前版本 | `src/dspet/__init__.py` 里的 `VERSION`(当前 0.4.1) |
| 许可 | MIT(`LICENSE`);美术音效来自「大肥鱼-余额挂件 v0.3.0」(© 月匠/MeteorNOX, MIT) |
| 平台 | **仅 Windows 10 / 11 x64** |
| 联网点 | **唯一一个** —— 查余额 `https://api.deepseek.com/user/balance`(只读、用用户自己的 Key、不耗 token) |

**相关仓库**:

| 仓库 | 路径 | 说明 |
| --- | --- | --- |
| 桌宠本体 | `D:\Projects\deepseek-pet\` | 本仓库 |
| 一键部署器 | `D:\Projects\dspet-deploy\` | 自包含安装器(内嵌桌宠本体) |
| 开发环境专项 | `D:\Projects\devkit\` | 见其 `BRIEF.md` |

---

## 2. 目录结构

```
src/dspet/
  __init__.py     VERSION / APP_NAME / APP_TITLE 常量
  __main__.py     入口:单实例互斥体 / DPI / --mem-purge 分支
  pet.py          主逻辑:动画、拖拽、右键菜单、气泡、喂文件、全屏让位
  settings_ui.py  设置窗口(tkinter + customtkinter)
  uikit.py        自绘 UI 控件(PIL 超采样渲染)
  memopt.py       内存优化(清待机内存;非管理员走 UAC 提权 --mem-purge)
  balance.py      余额查询(唯一联网点)
  config.py       配置读写(JSON + Windows DPAPI 加密 Key)
  autostart.py    开机自启(启动文件夹 .lnk)
  paths.py        路径引导(frozen / 源码双形态)
  assets/         美术音效资源
main.py           完全版统一入口(打包入口)
main_lite.py      轻量版入口(设 DSPET_EDITION=lite)
run_dev.py        源码运行(开发调试)
build/            打包(见第 5 节)
tools/            自测脚本(t_*.py)
```

---

## 3. 常用命令

```powershell
# 源码运行(控制台有日志)
python run_dev.py --debug

# 打包完全版单文件 exe  → dist\DeepSeekPet-v<ver>-win64.exe
powershell -ExecutionPolicy Bypass -File build\build.ps1

# 打包完全版 + 目录版 zip
powershell -ExecutionPolicy Bypass -File build\build.ps1 -Full

# 打包轻量版单文件 exe  → dist\DeepSeekPet-Lite-v<ver>-win64.exe
powershell -ExecutionPolicy Bypass -File build\build_lite.ps1
```

**本机 Python 环境(实测)**:

| 路径 | 版本 | 已装 |
| --- | --- | --- |
| `D:\Python312\python.exe` | 3.12.8 | pyinstaller 6.22.3、pywin32 312、pillow、numpy、customtkinter 6.0.0 ← **打包用** |
| `C:\Python314\python.exe` | 3.14.7 | pywin32、pillow、customtkinter ← **源码调试用** |
| `D:\Projects\dspet-deploy\.venv\` | — | 部署器自用 venv |

**运行期依赖**(`requirements.txt`):`pywin32>=306` · `pillow>=10.0` · `numpy>=1.24`
**打包依赖**:`pyinstaller>=6.0`

---

## 4. 代码规范

- **PEP 8**;`ruff` 可做 lint(工具未强制安装,见第 9 节待办)。
- **所有源文件带 `# -*- coding: utf-8 -*-`** —— 这是一致约定,新文件照做。
- **`.ps1` 脚本一律纯 ASCII**。PowerShell 5.1 读不了无 BOM 的中文 `.ps1`,直接解析崩;
  中文内容交给 Python 写文件。
- **不做超出范围的改动**。不顺手重构、不顺手改别的文件;发现别处的 bug → **先报告,再动手**。
- **不做不可逆操作**:删除、覆盖、格式化前先确认或备份。
- **改动桌面软件(关进程/改自启/动安装目录)前先跟东家打招呼**,测完必须**恢复原样**。
- 外部命令用**参数数组**调用,不做 shell 字符串拼接。
- 测试脚本里的 `print` **不要放 `✓` / `✗` 等字符** —— 控制台是 GBK,会 `UnicodeEncodeError`。

---

## 5. 构建与产物

打包链在 `build/`:

| 文件 | 用途 |
| --- | --- |
| `build.ps1` | 完全版:单文件 exe(默认) + `-Full` 加目录版 zip |
| `build_lite.ps1` | 轻量版单文件 exe |
| `dspet_onefile.spec` | 完全版单文件 |
| `dspet.spec` | 完全版目录版(`COLLECT`) |
| `dspet_lite_onefile.spec` | 轻量版单文件 |
| `version_info.txt` | 完全版版本资源(部署器 `peinfo.py` 会读它核对) |
| `version_info_lite.txt` | 轻量版版本资源 |

**版本号单一来源**:`src/dspet/__init__.py` 的 `VERSION`;`build.ps1` 会 `Select-String` 读它来命名产物。**发版只改这一处。**

### 打包铁律(踩过的坑)

1. **`version=` 文件必须无 BOM** —— PyInstaller 读带 BOM 的版本资源会失败。
2. **spec 里不能写 `__file__`** —— PyInstaller 执行 spec 时没有这个变量,用 `SPECPATH`。
3. **excludes 不能误伤 PySide6 / PyQt** —— 曾误把 `PySide6` 写进 excludes 导致打包漏库。
4. **打包前先杀掉在跑的 exe**,否则 `Remove-Item dist` 会失败。
5. **onefile 会有两个同名进程**(引导进程 + 真身),**不是启动了两次**。判断数量要看窗口,不看进程。
6. 打包中间产物在 `build/_work*/`,已 gitignore;`build.ps1` 退出码末尾可能有旧毛病,**看输出里的 "单文件: ... (xx MB)" 判断成功**。
7. 完成后产物落 `dist/`(已 gitignore,不进版本库)。

---

## 6. 测试

**目前没有 pytest 套件**(见第 9 节待办)。现有自测全在 `tools/t_*.py` —— 都是**针对具体功能的一次性验证脚本**,按需运行:

```powershell
python tools\t_quit2.py menu      # 右键退出是否干净
python tools\t_nokey.py           # 没填 Key 时点桌宠不弹设置窗
python tools\t_toolbox.py         # 工具箱按钮链路(禁提权)
python tools\t_memhelper.py       # --mem-purge 自模式
python tools\t_menu2.py           # 右键时冻住 + 临时取消置顶
python tools\t_tick_logic.py      # 倒计时刷新
```

### 测试方法论(重要,别重踩)

- **测"程序秒退"前先看桌面/进程** —— 可能已有同程序占着**全局单实例互斥体**
  `Global\DeepSeekPetFishSingleton`,不是崩溃。
- **不要用 `FindWindow('DSPetWnd')` 抓测试窗口** —— 会抓到装机跑的那一只;用 `p.hwnd`。
- **tkinter 消息泵必须在主线程**:`Pet.start()` 放子线程 → `PostMessage` 永远不派发。
- **模态确认框用 `BM_CLICK(0xF5)`** 点按钮,比 `WM_COMMAND` 靠。
- 测"点按钮"要**按截图量出的像素坐标**点;点完窗口尺寸变了,下次坐标要重算。
- `os._exit(0)` 前必须判空 `sys.stdout`(windowed 打包下是 `None`)。
- 验证窗口状态用 Win32 API 比看截图可靠:`GetWindowLong(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST` 验置顶。
- **本机无法自测"提权"** —— 需要管理员的那一下,如实告诉东家让他点 UAC,别假装测过。

---

## 7. 配置与运行期状态(不在版本库)

- `config.json` —— 程序同目录优先(便携),不可写则退 `%APPDATA%\DeepSeekPet\`。含 **DPAPI 加密的 API Key**。
- `dspet.log` —— 日志,同目录。
- **这两个文件都不许进版本库**(已 gitignore)。测试时改配置要先备份、测完还原。

---

## 8. Git 规范

- 分支:`master` 为稳定线;改动开分支(如 `chore/baseline`)。
- **Conventional Commits**:`feat(scope):` / `fix(scope):` / `docs:` / `test:` / `chore:` / `refactor:`。
  参考历史:`feat(memopt):` `fix(pet):` `fix(uikit):` `chore(baseline):` `docs+test:`。
- **提交粒度**:一个逻辑改动一次提交;尽量**聚焦、原子**、可单独回退。
- **不提交**:`config.json`、`dspet.log`、`dist/`、`build/_work*/`、`__pycache__/`、`_*.png/txt` 等临时产物。
- **提交前自查**:`git status` 确认没有误加私密/临时文件。

---

## 9. 已知问题 / 待办

| 项 | 现状 | 说明 |
| --- | --- | --- |
| `build/build.ps1` 硬编码 | ⚠️ **待修** | `$py = "D:\Python312\python.exe"` 写死;换台机器路径不存在时 fallback 到 `python`。应改为可配置/自动探测。 |
| lint / 类型检查 | ❌ 无 | 未装 `ruff`。 |
| pytest 套件 | ❌ 无 | 只有 `tools/t_*.py` 一次性脚本。 |
| 覆盖率门禁 | ❌ 无 | 未装 `pytest-cov`。 |
| GitHub 远程 | ❌ 无 | 当前**仅本地仓库**;东家暂缓建远程的事。 |

---

## 10. 版本/许可

MIT。分发时保留 `LICENSE` 与 `THIRD_PARTY.md`(第三方素材署名)。
