# Verify the Desktop shortcut + Desktop copy (ASCII only, writes to file)
$ErrorActionPreference = 'Continue'
$log = Join-Path $env:TEMP 'verify_shortcut.txt'
Set-Content -Path $log -Value '' -Encoding UTF8
function W($m) { Add-Content -Path $log -Value ([string]$m) -Encoding UTF8 }

$desk = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desk 'PC Action Imitator.lnk'
$appPath = Join-Path $desk 'PC Action Imitator'

W ("Desktop = " + $desk)
W ("Shortcut exists = " + (Test-Path $lnkPath))
W ("App folder exists = " + (Test-Path $appPath))

if (Test-Path $lnkPath) {
    $w = New-Object -ComObject WScript.Shell
    $l = $w.CreateShortcut($lnkPath)
    W ("TargetPath   = " + $l.TargetPath)
    W ("TargetExists = " + (Test-Path $l.TargetPath))
    W ("Arguments    = " + $l.Arguments)
    W ("WorkingDir   = " + $l.WorkingDirectory)
    W ("IconLocation = " + $l.IconLocation)
    $iconOnly = ($l.IconLocation -split ',')[0]
    W ("IconExists   = " + (Test-Path $iconOnly))
    W ("Desc         = " + $l.Description)
    $runApp = Join-Path $appPath 'run_app.pyw'
    W ("RunApp exists = " + (Test-Path $runApp))
}

# Compare all .py file hashes between project and desktop copy
$proj = 'C:\Users\d.sergazin\PCActionImitator'
$diff = @()
foreach ($f in (Get-ChildItem $appPath -Filter *.py -Name)) {
    $pf = Join-Path $proj $f
    if (Test-Path $pf) {
        $h1 = (Get-FileHash (Join-Path $appPath $f) -Algorithm MD5).Hash
        $h2 = (Get-FileHash $pf -Algorithm MD5).Hash
        if ($h1 -ne $h2) { $diff += $f }
    } else { $diff += ($f + ' (not in project)') }
}
W ("Different py files = " + $(if ($diff.Count) { $diff -join ', ' } else { 'NONE - identical' }))
W ("Stands button in desktop main.py = " + ((Select-String -Path (Join-Path $appPath 'main.py') -Pattern 'Добавить стенд' -Encoding UTF8).Count -gt 0))

W "=== DONE ==="
Write-Output 'VERIFY_DONE'
