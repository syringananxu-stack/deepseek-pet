# 桌宠项目 · 交接提示词(给新 Agent)

> 用途:OpenClaw 即将格式化重建,新 Agent 接手「DeepSeek 大肥鱼桌宠」项目。
> **先读这份,再读 `D:\Projects\devkit\BRIEF.md`,然后才动手。**
> 最后更新:2026-09-26 08:4x(东家要格式化 OpenClaw 前)

---

## 0. 给新 Agent 的三条铁律(先读这个)

1. **每天晚上 23:00 断电**,东家会自己关机。长任务 22:30 前收尾,每步必须**可续跑、可断点续做**。
2. **一律放 D 盘**。东家 C 盘敏感,下载/安装/venv/临时文件全走 D。C 盘只放 workspace。
3. **涉及本机状态的活绝不外包**;跑量任务(示例代码/文案/脚本初稿)可以丢给网页版,但**产出必须自己复核 + 本机实测**,日志标注来源。**绝不把私人信息(路径/Key/账号/截图)发给网页版或任何外部服务。**

---

## 1. 项目是什么

**DeepSeek 大肥鱼桌宠(DeepSeekPet)** —— 一只趴在 Windows 桌面上的小蓝鱼。

- 会自己溜达、被拎起来会拉长成史莱姆
- 单击她 → 看 DeepSeek 账户余额 + 高峰/低谷时段
- 拖文件到她身上 → 「喂」掉(默认进回收站)
- 设置里有「工具箱 → 内存优化」:清系统待机内存/修改页(要 UAC 提权)
- 唯一联网点 = 查余额(DeepSeek 官方只读接口 `/user/balance`,用**用户自己的 Key**,不消耗 token);不填 Key 也能用
- Key 加密存本机(Windows DPAPI)

**版权**:MIT。美术/音效来自「大肥鱼 - 余额挂件 v0.3.0」(© @月匠 / MeteorNOX,MIT),参考 whale-purse(© Suiwan,MIT)。见 `THIRD_PARTY.md`。

---

## 2. 三个仓库(全在 D 盘)

| 仓库 | 路径 | 是什么 |
| --- | --- | --- |
| **桌宠本体** | `D:\Projects\deepseek-pet\` | 主程序(v0.4.1) |
| **一键部署器** | `D:\Projects\dspet-deploy\` | `dspet-deploy.exe`(v0.1.0,41.57MB,自带桌宠本体,自包含) |
| **开发环境专项** | `D:\Projects\devkit\` | devkit 简报 + 脚本(见 `BRIEF.md`) |

### 桌宠源码结构(`D:\Projects\deepseek-pet\src\dspet\`)

| 文件 | KB | 干什么 |
| --- | --- | --- |
| `pet.py` | 43.3 | 主逻辑:动画/拖拽/右键菜单/气泡/喂文件/全屏让位 |
| `settings_ui.py` | 31.5 | 设置窗口(圆角卡片:账号/行为/详情/工具箱) |
| `uikit.py` | 27.6 | 自绘 UI 组件(Card / Segmented / 旋钮…) |
| `memopt.py` | 9.9 | 内存优化(清待机内存/修改页,非管理员走 UAC 提权 `--mem-purge`) |
| `config.py` | 3.1 | 配置读写(优先程序同目录 `config.json`) |
| `autostart.py` | 2.5 | 开机自启(`%APPDATA%\...\Startup\DeepSeekPet.lnk`) |
| `balance.py` | 2.2 | 余额查询(唯一联网点) |
| `paths.py` | 1.7 | 路径引导(资源/日志/配置) |
| `__main__.py` | 2.5 | 入口(单实例互斥体 / DPI / 内存优化 helper 分支) |

**入口**:`main.py`(完全版)、`main_lite.py`(**轻量版**,只设 `DSPET_EDITION=lite`)

**双版本机制**:`DSPET_EDITION=lite` 环境变量驱动,`pet.py` / `settings_ui.py` 里靠 `LITE` 常量做守卫,隐藏「内存优化 / 开机自启 / 喂文件」。

### 打包链(`D:\Projects\deepseek-pet\build\`)

| 文件 | 干什么 |
| --- | --- |
| `build.ps1` | 完全版(一键出 exe + portable zip) |
| `build_lite.ps1` | 轻量版单文件 exe |
| `dspet_onefile.spec` / `dspet_lite_onefile.spec` / `dspet.spec` | PyInstaller 配置 |
| `version_info.txt` / `version_info_lite.txt` | 版本资源(**已写入,可被部署器读**) |

**打包含 `version=` 版本资源**,`dspet-deploy` 的 `peinfo.py` 能读出来核对。

---

## 3. 已完成(交出去的东西)

### 3.1 两个出货 ZIP —— 在 `D:\Downloads\`

| 包 | 大小 | 内含 |
| --- | --- | --- |
| `DeepSeekPet-Lite-v0.4.1-win64.zip` | 30.68MB | `DeepSeekPet-Lite.exe`(双击即用)+ LICENSE/README/THIRD_PARTY/使用说明 |
| `DeepSeekPet-Full-v0.4.1-win64.zip` | 70.94MB | **`一键部署.exe`(41.57MB,内嵌桌宠)** + `DeepSeekPet.exe` + 说明文档 |

临时暂存:`D:\Temp\pkg\lite` 与 `D:\Temp\pkg\full`。

### 3.2 版本资源(已核对通过)

- 完全版:`0.4.1.0` / `DeepSeek 大肥鱼 · 桌面桌宠(完全版)`
- 轻量版:`0.4.1.0` / `DeepSeek 大肥鱼 · 桌面桌宠(轻量版)`

### 3.3 devkit 原型(`D:\Temp\devkit-demo\`)—— **必须保留**

| 组件 | 状态 |
| --- | --- |
| `runtime\python` | ✅ Python 3.13.7(便携) |
| `runtime\uv` | ✅ 0.12.19 |
| `runtime\git` | ✅ MinGit 2.51.0 |
| `ide\VSCode` | ✅ 1.139.1 便携版(1.1GB;`data\user-data` 已重置为出厂,`data\extensions` **空**) |
| `projects\demo-app\.venv` | ✅ 已建,装了 pytest 9.1.1 + debugpy 1.8.22(cp313) |
| 离线 wheel 包 | ✅ `D:\Downloads\devkit\wheels`(7 个) |
| **跑测试** | ✅ **`4 passed in 0.01s`**(2026-09-26 复测确认) |
| 三个脚本 | ✅ `一键就绪.cmd` / `打开VS Code.cmd` / `跑测试.cmd` |

---

## 4. 未完成(当前主线任务)

### 任务目标(东家原话)

> 「让一个**傻子都能部署环境**。用户下载我们的桌宠,打开 UI,点一键部署,自动把 Python 开发环境部署完美,随后就能开始开发。」
> 「**离线版本**,做大点做个安装包都没事(1G 也行)。」
> 「**轻量版不用 Python 环境**,朋友新机装上也能跑。」

### 已定死的设计约束

- **离线自包含**:全部打包进安装包,**运行时不下载**任何东西
- **版本锁死**(不追更新):Python **3.13.7** · uv **0.12.19** · MinGit **2.51.0** · VS Code **1.139.1** · pytest **9.1.1** · debugpy **1.8.22** · 插件 `ms-python.python` / `ms-python.vscode-pylance` / `MS-CEINTL.vscode-language-pack-zh-hans`
- **零 UAC / 不写系统 PATH / 不改注册表**(用户级 + 自用目录,像 PCL)
- **零窗口**:安装过程绝不弹 GUI
  ⚠️ 装 VS Code 插件**必须「解压 VSIX 到 extensions 目录」**,**绝对不要**调 `code --install-extension`(会拉起 VS Code 窗口,已经坑过东家一次)
- **打包前必须清空 `user-data` / `extensions`,并校验 `state.vscdb` 不存在**(否则会把东家的登录令牌发给陌生人 —— 真实事故)

### 验收标准(装完 60 秒内)

1. 示例项目跑 `pytest` 看到 **`4 passed`**
2. 打开 VS Code:解释器已自动选中,按 F5 能调试
3. **全程零 UAC**;系统 PATH / 注册表**未被修改**

### 待办顺序(东家 2026-09-26 08:29 拍板「按顺序做吧」)

**① 补完 devkit 原型的 `4 passed`** —— ✅ **已完成**(复测 4 passed)
> 遗留:原型里 `一键就绪.cmd` 的 `WHEELS` 变量指向 `D:\Temp\devkit-demo\wheels`(不存在),回退到 `D:\Downloads\devkit\wheels`。**换台机器就断链** → 正是第 ② 步要修的。

**② 做自包含离线安装包**(最重的一块,未开始)
- 目标:**一个 ~1GB 安装包** = 桌宠 + 完整 Python 开发环境
- 全部自包含(wheels/VSIX/runtime 都进包,不依赖 `D:\Downloads`)
- 集成进**桌宠 UI** 的「一键就绪」按钮
- 脚本一律**纯 ASCII**
- 建议:用 **Inno Setup** 打安装包,默认装到 `D:\DeepSeekPetDev`,含桌面/开始菜单快捷方式 + 卸载
- ⚠️ **桌宠侧集成由主会话负责,不要乱改桌宠代码**

**③ 虚拟机验证**(依赖 ② 完成)
- 用 **Hyper-V**(东家 Win11 Pro 自带,不装第三方)
- **所有文件只放一个文件夹** `D:\VMs\devkit-test\`(VHDX/快照/配置全在 D;Hyper-V 默认塞 C 盘,要显式改)
- Win11 官方 ISO(~6GB)也放同一文件夹
- VM 规格:**4~8 vCPU / 8GB 内存 / 60GB 盘 / 开 TPM + 安全启动**
- 装完做**干净快照**,以后每轮测试 3~5 分钟回滚
- **一键清理脚本**:停 VM → `Remove-VM -Force` → 删文件夹 → 删专用交换机 → 校验(东家要求「做完项目必须能立刻连根拔掉」)
- **先确认 Hyper-V 已生效**(2026-09-25 已启用 + 当晚重启过 → 大概率已生效,待提权确认)
- 现状:ISO 未下、`D:\VMs` 未建、VM 未建、清理脚本未写
- ⚠️ 占 D 盘 ~66GB、跑起来吃 8GB 内存;**东家打游戏时不要启动 VM**

---

## 5. 踩过的坑(别重踩)

1. **PowerShell 5.1 读不了没有 BOM 的中文 `.ps1`** → 解析直接崩。脚本一律**纯 ASCII**;中文内容交给 python 写文件。
2. `Expand-Archive` **不认 `.whl`** → 用 `[IO.Compression.ZipFile]::ExtractToDirectory`;对截断 zip 报"找不到中央目录结尾记录" → 先用 `ZipFile::OpenRead().Entries.Count` 校验。
3. **VS Code zip 会下载截断**(258MB vs 实际 321MB / 3302 entries)→ 必须校验 + `curl -C -` 续传。
4. VS Code 市场 API **HEAD 返回 405** → 用 GET(curl)。
5. `debugpy` 轮子必须指定 `--python-version 3.13 --implementation cp --abi cp313 --platform win_amd64`,否则拉到 cp314。
6. `Get-WindowsOptionalFeature` **需要管理员**;非管理员下改用 `systeminfo` / 服务 / 模块存在性探测。
7. **测"程序秒退"前先看桌面/进程** —— 可能已有同程序占着**全局单实例互斥体** `Global\DeepSeekPetFishSingleton`,不是崩溃。
8. **桌宠两版共用同一个全局互斥体 → 不能同时装、同时跑**,装哪个跑哪个。
9. **改动桌面软件要先跟东家打招呼**(关进程/改自启都算),测完务必恢复原样。
10. **PyInstaller 的 `version=` 文件要无 BOM**。
11. 装插件弹窗事故:**装 VSIX 只解压,不调 `code`**。

---

## 6. 环境与工具

**本机**:Windows 11 Pro 25H2 · build 26200 · Intel Core Ultra 7 265K · 31.4GB 内存
**磁盘**:C 盘敏感(尽量不占)/ D 盘充裕
**Python**:
- 测试用 `C:\Python314\python.exe`
- 打包用 `D:\Python312\python.exe`
- 桌宠部署 venv:`D:\Projects\dspet-deploy\.venv\`

**外部工具:网页版 DeepSeek(已登录,浏览器 relay)**
```powershell
cd D:\Downloads
$env:RELAY_TOKEN='d901ed2a2258bf89a47d042309f4ce5021ae7a87a222cebd'
node _cdp.mjs list                              # 列标签页
node _cdp.mjs <targetId> "JS表达式"              # 执行
node _cdp.mjs <targetId> "@D:\Downloads\_js_x.js"  # 执行文件里的 JS
```
只喂**通用技术问题**;绝不喂私人信息。

**东家风格**:中文交流,说话简短直接,会质疑、会追问,**喜欢看到真东西**(让文件留在桌面上给他看)。**报时间前先 `session_status`**,不要自己估。

---

## 7. 参考文件

| 文件 | 内容 |
| --- | --- |
| `D:\Projects\devkit\BRIEF.md` | devkit 专项完整简报(最详细) |
| `D:\Projects\deepseek-pet\README.md` | 桌宠用户文档 |
| `D:\Projects\dspet-deploy\README.md` | 部署器文档 |
| `D:\Projects\deepseek-pet\THIRD_PARTY.md` | 第三方素材致谢 |
| `D:\Projects\deepseek-pet\LICENSE` | MIT |
| `memory/2026-09-25.md` / `memory/2026-09-26.md` | workspace 里的逐日详细日志 |
