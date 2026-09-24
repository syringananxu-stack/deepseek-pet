# 一键打包(在 D 盘 Python 3.12 环境下)
#   用法: powershell -ExecutionPolicy Bypass -File build\build.ps1
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
$py   = "D:\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Set-Location $proj
Write-Host "==> 清理" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$proj\build\DeepSeekPet", "$proj\dist" -ErrorAction SilentlyContinue

Write-Host "==> PyInstaller 打包(onedir, 无控制台)" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work" "$proj\build\dspet.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

Write-Host "==> 拷贝附带文件" -ForegroundColor Cyan
$out = "$proj\dist\DeepSeekPet"
Copy-Item "$proj\dspet.ico" "$out\dspet.ico" -Force
foreach ($f in @("README.md", "LICENSE", "THIRD_PARTY.md")) {
  if (Test-Path "$proj\$f") { Copy-Item "$proj\$f" "$out\$f" -Force }
}
New-Item -ItemType Directory -Force "$out\config" | Out-Null

Write-Host "==> 压缩为 zip" -ForegroundColor Cyan
$zip = "$proj\dist\DeepSeekPet-v$((Select-String -Path "$proj\src\dspet\__init__.py" -Pattern 'VERSION = \"(.*)\"').Matches[0].Groups[1].Value)-win64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path "$out\*" -DestinationPath $zip -CompressionLevel Optimal

$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "==> 完成: $zip  ($size MB)" -ForegroundColor Green
Write-Host "    目录: $out"
