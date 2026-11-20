# Startet scripts/setup.sh unter Windows mit Git Bash im aktuellen Terminal.
# Alle Argumente werden durchgereicht, z. B.:
#   .\scripts\setup.ps1 --no-node
$ErrorActionPreference = 'Stop'

# bash.exe von Git for Windows finden: zuerst neben git.exe im PATH, dann Standardpfade.
$candidates = @()
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    # git.exe liegt in <Git>\cmd oder <Git>\bin – bash.exe in <Git>\bin
    $gitRoot = Split-Path (Split-Path $git.Source -Parent) -Parent
    $candidates += Join-Path $gitRoot 'bin\bash.exe'
}
$candidates += "$env:ProgramFiles\Git\bin\bash.exe"
$candidates += "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"

$bash = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bash) {
    Write-Error 'Git Bash nicht gefunden. Bitte Git for Windows installieren: https://git-scm.com/download/win'
    exit 1
}

$setup = Join-Path $PSScriptRoot 'setup.sh'
& $bash $setup @args
exit $LASTEXITCODE
