# Clean decisive test of the desktop shortcut (ASCII only)
$ErrorActionPreference = 'Continue'
$log = Join-Path $env:TEMP 'clean_test.txt'
Set-Content -Path $log -Value '' -Encoding UTF8
function W($m) { Add-Content -Path $log -Value $m -Encoding UTF8 }

$desk = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desk 'PC Action Imitator.lnk'
$dst = Join-Path $desk 'PC Action Imitator'
$cfg = Join-Path $dst 'config.json'

W ("=== CLEAN TEST " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ===")

# 1. Kill ALL python GUI instances (clean slate)
W "--- kill all pythonw/pythonw3.12 ---"
Get-Process -Name 'pythonw3.12','pythonw' -ErrorAction SilentlyContinue | ForEach-Object {
    W ("  kill pid=" + $_.Id)
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

$before = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^python' } | Select-Object -ExpandProperty Id)
W ("before ids: " + ($before -join ','))
$cfgBefore = if (Test-Path $cfg) { (Get-Item $cfg).LastWriteTime.ToString('HH:mm:ss') } else { 'NONE' }
W ("config before=" + $cfgBefore)

# 2. Launch via shortcut and poll for the window
W "--- launch via shortcut + poll ---"
Start-Process -FilePath $lnk
$found = $null
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 1
    $cand = @(Get-Process -Name 'pythonw3.12','pythonw' -ErrorAction SilentlyContinue |
              Where-Object { $before -notcontains $_.Id })
    $withWin = @($cand | Where-Object { try { $_.Refresh(); ($_.MainWindowHandle -ne 0) } catch { $false } })
    if ($withWin.Count -gt 0) { $found = $withWin[0]; W ("  window appeared after " + $i + "s"); break }
}
if ($found) {
    W ("FOUND pid=" + $found.Id + " name=" + $found.ProcessName + " hwnd=" + $found.MainWindowHandle + " title=[" + $found.MainWindowTitle + "]")
    W "SHORTCUT_LAUNCH_OK=True"
} else {
    W "SHORTCUT_LAUNCH_OK=False"
}

# 3. Graceful close -> app on_close saves config
if ($found) {
    W "--- graceful close ---"
    try { $found.CloseMainWindow() | Out-Null } catch { W ("  CloseMainWindow err: " + $_) }
    Start-Sleep -Seconds 4
    if (-not $found.HasExited) { W "  still alive -> force kill"; Stop-Process -Id $found.Id -Force -ErrorAction SilentlyContinue }
    else { W "  exited gracefully" }
}

$cfgAfter = if (Test-Path $cfg) { (Get-Item $cfg).LastWriteTime.ToString('HH:mm:ss') } else { 'NONE' }
W ("config after=" + $cfgAfter)
W ("CONFIG_SAVED=" + ($cfgBefore -ne $cfgAfter))
W "=== END ==="
Write-Output "CLEAN_DONE"
