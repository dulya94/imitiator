# tools/verify_push.ps1 — закоммитить (опционально) и проверить синхронизацию с GitHub.
# Использование:
#   powershell -File tools\verify_push.ps1                       # только проверка
#   powershell -File tools\verify_push.ps1 -Message "текст"       # add -A + commit + push + проверка
param([string]$Message = '')

$ErrorActionPreference = 'Continue'
$out = Join-Path $env:TEMP 'pushverify.txt'
Set-Content -Path $out -Value '' -Encoding UTF8
function W($m) { Add-Content -Path $out -Value $m -Encoding UTF8 }

Set-Location 'c:\Users\d.sergazin\PCActionImitator'
$env:GIT_TERMINAL_PROMPT = '0'

if ($Message) {
    W "--- add ---"
    (git add -A 2>&1) | ForEach-Object { W $_ }
    W "--- commit ---"
    (git commit -m $Message 2>&1) | ForEach-Object { W $_ }
    W ("commit exit=" + $LASTEXITCODE)
}

W "--- push ---"
(git push 2>&1) | ForEach-Object { W $_ }
W ("push exit=" + $LASTEXITCODE)
W "--- local ---"
(git log --oneline -1 2>&1) | ForEach-Object { W $_ }
W "--- remote ---"
(git ls-remote origin refs/heads/main 2>&1) | ForEach-Object { W $_ }
W "--- status ---"
(git status --short 2>&1) | ForEach-Object { W $_ }
W "--- end ---"
