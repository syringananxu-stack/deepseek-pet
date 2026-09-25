# 一键打包(在 D 盘 Python 3.12 环境下)
#   单文件: powershell -ExecutionPolicy Bypass -File build\build.ps1
#   目录版: powershell -ExecutionPolicy Bypass -File build\build.ps1 -Full
param([switch]$Full)

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$py   = "D:\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$ver = (Select-String -Path "$proj\src\dspet\__init__.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Set-Location $proj

Write-Host "==> 清理" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$proj\dist", "$proj\build\_work" -ErrorAction SilentlyContinue

Write-Host "==> 打包单文件 exe (v$ver)" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work" "$proj\build\dspet_onefile.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

$single = "$proj\dist\DeepSeekPet-v$ver-win64.exe"
Copy-Item "$proj\dist\DeepSeekPet.exe" $single -Force
Write-Host ("    单文件: {0}  ({1:N1} MB)" -f $single, ((Get-Item $single).Length / 1MB)) -ForegroundColor Green

if ($Full) {
  Write-Host "==> 附带打包目录版(启动更快)" -ForegroundColor Cyan
  & $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work2" "$proj\build\dspet.spec"
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller(目录版)失败" }
  $out = "$proj\dist\DeepSeekPet"
  Copy-Item "$proj\dspet.ico" "$out\dspet.ico" -Force
  foreach ($f in @("README.md", "LICENSE", "THIRD_PARTY.md")) {
    if (Test-Path "$proj\$f") { Copy-Item "$proj\$f" "$out\$f" -Force }
  }
  $zip = "$proj\dist\DeepSeekPet-v$ver-win64-portable.zip"
  Remove-Item $zip -ErrorAction SilentlyContinue
  Compress-Archive -Path "$out\*" -DestinationPath $zip -CompressionLevel Optimal
  Write-Host ("    目录版: {0}  ({1:N1} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)) -ForegroundColor Green
}

Write-Host "==> 完成" -ForegroundColor Green
