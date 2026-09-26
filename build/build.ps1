# One-click build (single-file exe).
#   Single-file: powershell -ExecutionPolicy Bypass -File build\build.ps1
#   With onedir: powershell -ExecutionPolicy Bypass -File build\build.ps1 -Full
#   Custom interpreter: set $env:DSPET_PYTHON = "D:\path\python.exe" before running.
#
# NOTE: this file MUST stay pure ASCII. PowerShell 5.1 reads BOM-less .ps1 files
# using the system ANSI code page, so non-ASCII text here would corrupt parsing.
param([switch]$Full)

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot

# ---- Resolve a Python interpreter (no hardcoded machine path) ----
# Order: env var > local 3.12 > project venv > deploy venv > py launcher > PATH python
function Resolve-Python {
    $cands = @()
    if ($env:DSPET_PYTHON) { $cands += @{ kind = "path"; value = $env:DSPET_PYTHON } }
    $cands += @{ kind = "path"; value = "D:\Python312\python.exe" }
    $cands += @{ kind = "path"; value = "$proj\.venv\Scripts\python.exe" }
    $cands += @{ kind = "path"; value = "$proj\..\dspet-deploy\.venv\Scripts\python.exe" }
    $cands += @{ kind = "launcher"; value = "py" }
    $cands += @{ kind = "cmd"; value = "python" }

    foreach ($c in $cands) {
        if ($c.kind -eq "path") {
            if (Test-Path $c.value) { return $c.value }
        } elseif ($c.kind -eq "launcher") {
            $v = & $c.value -3.12 -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) { return $v.Trim() }
        } else {
            $v = & $c.value -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) { return $v.Trim() }
        }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    throw "No usable Python interpreter found. Set DSPET_PYTHON to a python.exe path."
}
# Fail fast if PyInstaller is missing (clearer than failing mid-build).
& $py -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Interpreter [$py] has no PyInstaller. Run: & '$py' -m pip install pyinstaller"
}
Write-Host "==> interpreter: $py" -ForegroundColor Cyan

$ver = (Select-String -Path "$proj\src\dspet\__init__.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Set-Location $proj

Write-Host "==> clean" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$proj\dist", "$proj\build\_work" -ErrorAction SilentlyContinue

Write-Host "==> build single-file exe (v$ver)" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work" "$proj\build\dspet_onefile.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$single = "$proj\dist\DeepSeekPet-v$ver-win64.exe"
Copy-Item "$proj\dist\DeepSeekPet.exe" $single -Force
Write-Host ("    single-file: {0}  ({1:N1} MB)" -f $single, ((Get-Item $single).Length / 1MB)) -ForegroundColor Green

if ($Full) {
  Write-Host "==> also building onedir package (faster startup)" -ForegroundColor Cyan
  & $py -m PyInstaller --noconfirm --clean --distpath "$proj\dist" --workpath "$proj\build\_work2" "$proj\build\dspet.spec"
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller (onedir) failed" }
  $out = "$proj\dist\DeepSeekPet"
  Copy-Item "$proj\dspet.ico" "$out\dspet.ico" -Force
  foreach ($f in @("README.md", "LICENSE", "THIRD_PARTY.md")) {
    if (Test-Path "$proj\$f") { Copy-Item "$proj\$f" "$out\$f" -Force }
  }
  $zip = "$proj\dist\DeepSeekPet-v$ver-win64-portable.zip"
  Remove-Item $zip -ErrorAction SilentlyContinue
  Compress-Archive -Path "$out\*" -DestinationPath $zip -CompressionLevel Optimal
  Write-Host ("    onedir: {0}  ({1:N1} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)) -ForegroundColor Green
}

Write-Host "==> done" -ForegroundColor Green
