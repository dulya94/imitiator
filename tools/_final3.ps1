# Временный финальный скрипт: уборка, синхронизация, сверка хешей, коммит и push.
param([string]$Message = 'final sync')

$out = Join-Path $env:TEMP 'final3.txt'
Set-Content -Path $out -Value '' -Encoding UTF8
function W($m) { Add-Content -Path $out -Value $m -Encoding UTF8 }

$proj = 'c:\Users\d.sergazin\PCActionImitator'
$desk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PC Action Imitator'
Set-Location $proj
$env:GIT_TERMINAL_PROMPT = '0'

W "=== 1. remove temp/stale files ==="
Remove-Item 'tools\_final2.ps1' -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $desk 'tools\_final2.ps1') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $desk 'tools\make_shortcut.ps1') -Force -ErrorAction SilentlyContinue
W ("proj _final2 gone: " + (-not (Test-Path 'tools\_final2.ps1')))
W ("desk _final2 gone: " + (-not (Test-Path (Join-Path $desk 'tools\_final2.ps1'))))
W ("desk make_shortcut gone: " + (-not (Test-Path (Join-Path $desk 'tools\make_shortcut.ps1'))))

W "=== 2. sync code to desktop ==="
robocopy $proj $desk /E /XD .git __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
W ("robocopy exit=" + $LASTEXITCODE)

W "=== 3. compare python files (project vs desktop) ==="
$diff = @()
foreach ($f in (Get-ChildItem $proj -Recurse -Filter '*.py' -File |
               Where-Object { $_.FullName -notmatch '__pycache__' })) {
    $rel = $f.FullName.Substring($proj.Length + 1)
    $d = Join-Path $desk $rel
    if (-not (Test-Path $d)) { $diff += ("MISSING: " + $rel); continue }
    $h1 = (Get-FileHash $f.FullName -Algorithm MD5).Hash
    $h2 = (Get-FileHash $d -Algorithm MD5).Hash
    if ($h1 -ne $h2) { $diff += ("DIFFER: " + $rel) }
}
if ($diff.Count -eq 0) { W "ALL PY IDENTICAL" } else { $diff | ForEach-Object { W $_ } }

W "=== 4. desktop tools ==="
(Get-ChildItem (Join-Path $desk 'tools') -File | Select-Object -ExpandProperty Name) |
    ForEach-Object { W $_ }

W "=== 5. git add/commit/push ==="
(git add -A 2>&1) | ForEach-Object { W $_ }
(git commit -m $Message 2>&1) | ForEach-Object { W $_ }
W ("commit exit=" + $LASTEXITCODE)
(git push 2>&1) | ForEach-Object { W $_ }
W ("push exit=" + $LASTEXITCODE)

W "=== 6. verify ==="
(git log --oneline -1 2>&1) | ForEach-Object { W $_ }
W "--- remote ---"
(git ls-remote origin refs/heads/main 2>&1) | ForEach-Object { W $_ }
W "--- status ---"
(git status --short 2>&1) | ForEach-Object { W $_ }
W "=== end ==="
