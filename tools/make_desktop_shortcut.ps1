# Recreate the Desktop shortcut for PC Action Imitator (ASCII only!)
# Note: WshShortcut uses .TargetPath (NOT .Target)
$ErrorActionPreference = 'Stop'
$desk = [Environment]::GetFolderPath('Desktop')
$appPath = Join-Path $desk 'PC Action Imitator'
$lnkPath = Join-Path $desk 'PC Action Imitator.lnk'
$runApp = Join-Path $appPath 'run_app.pyw'
$iconPath = Join-Path $appPath 'assets\app_icon.ico'

$pwa = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\pythonw.exe'
if (-not (Test-Path $pwa)) { $pwa = 'pythonw.exe' }

Write-Output ('pythonw.exe=' + $pwa + ' exists=' + (Test-Path $pwa))
Write-Output ('run_app.pyw=' + $runApp + ' exists=' + (Test-Path $runApp))
Write-Output ('icon=' + $iconPath + ' exists=' + (Test-Path $iconPath))

if (-not (Test-Path $runApp)) { throw ('run_app.pyw missing: ' + $runApp) }
if (-not (Test-Path $iconPath)) { throw ('icon missing: ' + $iconPath) }

# Create shortcut
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut($lnkPath)
$lnk.TargetPath = $pwa
$lnk.Arguments = '"' + $runApp + '"'
$lnk.WorkingDirectory = $appPath
$lnk.IconLocation = $iconPath + ',0'
$lnk.Description = 'PC Action Imitator'
$lnk.Save()

# Read back
$lnk2 = $w.CreateShortcut($lnkPath)
Write-Output '--- Shortcut created ---'
Write-Output ('TargetPath=' + $lnk2.TargetPath)
Write-Output ('Arguments=' + $lnk2.Arguments)
Write-Output ('WorkingDir=' + $lnk2.WorkingDirectory)
Write-Output ('Icon=' + $lnk2.IconLocation)
Write-Output ('TargetPathExists=' + (Test-Path $lnk2.TargetPath))
Get-Item $lnkPath | Select-Object Name, Length, LastWriteTime | Format-List

