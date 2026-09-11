# Создание ярлыка "PC Action Imitator" на рабочем столе Windows.
# Запуск:  powershell -ExecutionPolicy Bypass -File tools\create_shortcut.ps1
$ErrorActionPreference = "Stop"

# Пути (проект лежит на уровень выше папки tools)
$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe  = (python -c "import sys; print(sys.executable)").Trim()
$PythonDir  = Split-Path -Parent $PythonExe
$Pythonw    = Join-Path $PythonDir "pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $PythonExe }  # fallback, если pythonw нет

$IconPath = Join-Path $ProjectDir "assets\app_icon.ico"
$Desktop  = [Environment]::GetFolderPath("Desktop")
$LnkPath  = Join-Path $Desktop "PC Action Imitator.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($LnkPath)
$Shortcut.TargetPath    = $Pythonw
$Shortcut.Arguments     = "`"$ProjectDir\run_app.pyw`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.IconLocation  = "$IconPath,0"
$Shortcut.Description   = "PC Action Imitator - zapisi i vosproizvedeniye deystviy myshi i klaviatury"
$Shortcut.WindowStyle   = 1
$Shortcut.Save()

Write-Host "OK: $LnkPath"
Write-Host "Target: $Pythonw"
Write-Host "Icon:   $IconPath"
