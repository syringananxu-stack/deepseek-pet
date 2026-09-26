# 一键打包:轻量版单文件 exe(在 D 盘 venv 里用 Python 3.12 环境打)
#   用法: powershell -ExecutionPolicy Bypass -File build\build_lite.ps1
#   产物: dist\DeepSeekPet-Lite-v0.4.1-win64.exe
param()

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$py = "D:\Projects\dspet-deploy\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$ver = (Select-String -Path "$proj\src\dspet\__init__.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Set-Location $proj

Write-Host "==> clean" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$proj\build\_work_lite" -ErrorAction SilentlyContinue

Write-Host "==> build lite onefile (v$ver)" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work_lite" "$proj\build\dspet_lite_onefile.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (lite) failed" }

$built = "$proj\dist\DeepSeekPet-Lite.exe"
$single = "$proj\dist\DeepSeekPet-Lite-v$ver-win64.exe"
Copy-Item $built $single -Force
Write-Host ("==> done: {0}  ({1:N1} MB)" -f $single, ((Get-Item $single).Length / 1MB)) -ForegroundColor Green
