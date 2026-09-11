# tools/make_shortcut.ps1 — создаёт ярлык "PC Action Imitator" на рабочем столе.
# Ярлык запускает run_app.pyw через pythonw.exe (без окна консоли).

$ErrorActionPreference = "Stop"

# --- путь к pythonw.exe рядом с текущим python.exe ---
$pyExe  = (Get-Command python).Source
$pyDir  = Split-Path $pyExe -Parent
$pywExe = Join-Path $pyDir "pythonw.exe"
if (-not (Test-Path $pywExe)) {
    # Windows Store Python: exe лежит в WindowsApps
    $alt = Join-Path (Split-Path $pyDir -Parent) "pythonw.exe"
    if (Test-Path $alt) { $pywExe = $alt } else { $pywExe = $pyExe }
}

# --- пути проекта ---
$project = Split-Path (Split-Path $PSCommandPath -Parent) -Parent   # <project>/tools -> <project>
$launcher = Join-Path $project "run_app.pyw"
$iconFile = Join-Path $project "assets\app_icon.ico"

if (-not (Test-Path $launcher)) { throw "Не найден $launcher" }

# --- рабочий стол пользователя ---
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "PC Action Imitator.lnk"

# --- создание ярлыка через COM ---
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath       = $pywExe
$lnk.Arguments        = '"' + $launcher + '"'
$lnk.WorkingDirectory = $project
if (Test-Path $iconFile) { $lnk.IconLocation = "$iconFile,0" }
$lnk.Description       = "PC Action Imitator - имитатор работы за ПК"
$lnk.Save()

Write-Host "OK: $lnkPath"
Write-Host "pythonw: $pywExe"