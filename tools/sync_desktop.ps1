# tools/sync_desktop.ps1 — обновить настольную копию кодом из проекта.
#
# ВАЖНО: скрипт НЕ трогает пользовательские данные:
#   - config.json (настройки: стенды, расписание, задержка)
#   - scenarios/  (записанные сценарии)
# Поэтому ваши настройки и записи на рабочем столе сохраняются.
#
# Запуск:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\sync_desktop.ps1

$ErrorActionPreference = 'Stop'

$project = Split-Path (Split-Path $PSCommandPath -Parent) -Parent   # <project>/tools -> <project>
$desk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PC Action Imitator'

if (-not (Test-Path $desk)) { throw "Настольная копия не найдена: $desk" }

Write-Host "Проект : $project"
Write-Host "Копия  : $desk"
Write-Host "Копирую код (config.json и scenarios/ не затрагиваются)..."

# /E — рекурсивно; /XO — не перезаписывать более новые файлы в приёмнике;
# исключаем .git, __pycache__, пользовательские config.json и scenarios/
robocopy $project $desk /E /XO `
    /XD '.git' '__pycache__' 'scenarios' `
    /XF '*.pyc' 'config.json' `
    /NFL /NDL /NJH /NJS /NP | Out-Null

$code = $LASTEXITCODE
Write-Host "robocopy код: $code (0-7 = успех)"

# Сверка питоновских файлов
$diff = @()
foreach ($f in (Get-ChildItem $project -Recurse -Filter '*.py' -File |
                Where-Object { $_.FullName -notmatch '__pycache__' })) {
    $rel = $f.FullName.Substring($project.Length + 1)
    $d = Join-Path $desk $rel
    if (-not (Test-Path $d)) { $diff += "MISSING: $rel"; continue }
    if ((Get-FileHash $f.FullName -Algorithm MD5).Hash -ne
        (Get-FileHash $d -Algorithm MD5).Hash) { $diff += "DIFFER: $rel" }
}
if ($diff.Count -eq 0) {
    Write-Host "OK: все .py совпадают с проектом" -ForegroundColor Green
} else {
    $diff | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
}
