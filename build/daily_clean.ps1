# Daily Temp residue cleaner (OpenClaw plugin builds + PyInstaller _MEI + Intel IIFC).
# ASCII-only on purpose: PowerShell 5.1 reads BOM-less .ps1 as ANSI.
# Safe rules:
#   - only directories directly under the system TEMP
#   - only name prefixes: openclaw-plugin-build- , _MEI , IIFC
#   - skip anything modified in the last 60 minutes (may be a live process)
#   - failures are ignored; exit 0 always
param([int]$MinAgeMinutes = 60)

$ErrorActionPreference = "SilentlyContinue"
$temp = $env:TEMP
if (-not $temp) { $temp = [System.IO.Path]::GetTempPath() }
$cutoff = (Get-Date).AddMinutes(-1 * $MinAgeMinutes)
$prefixes = @("openclaw-plugin-build-", "_MEI", "IIFC")

$removed = 0
$freed = 0

Get-ChildItem -LiteralPath $temp -Directory -Force | ForEach-Object {
    $name = $_.Name
    $hit = $false
    foreach ($p in $prefixes) { if ($name.StartsWith($p)) { $hit = $true; break } }
    if (-not $hit) { return }
    if ($_.LastWriteTime -gt $cutoff) { return }   # too new -> likely alive
    $size = 0
    Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force |
        ForEach-Object { $size += $_.Length }
    try {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
        $removed++
        $freed += $size
    } catch {
        # locked / permission -> skip, try again tomorrow
    }
}

$log = Join-Path $temp "dspet_daily_clean.log"
$line = "{0}  removed={1}  freed={2:N1} MB" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $removed, ($freed / 1MB)
Add-Content -LiteralPath $log -Value $line -Encoding UTF8
Write-Output $line
exit 0
