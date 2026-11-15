$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot 'data/runtime/postgres-recovery-20261111'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$log = Join-Path $runtime 'watchdog.log'

try {
    Set-Location -LiteralPath $projectRoot
    & (Join-Path $PSScriptRoot 'research_environment.ps1') -Quiet
    . (Join-Path $PSScriptRoot 'research_postgres_paths.ps1')
    $pgLayout = Get-ResearchPostgresLayout
    $pgReady = Join-Path $pgLayout.Binaries 'pg_isready.exe'
    if (-not (Test-Path -LiteralPath $pgReady)) {
        throw 'PostgreSQL readiness probe is missing.'
    }
    & $pgReady -h 127.0.0.1 -p 55433 -t 5 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'PostgreSQL did not accept a local readiness probe.'
    }
    [IO.File]::AppendAllText(
        $log,
        ([DateTimeOffset]::UtcNow.ToString('o') + ' ensure and readiness probe passed' + [Environment]::NewLine),
        (New-Object System.Text.UTF8Encoding($false))
    )
} catch {
    # Keep startup diagnostics operational and credential-free.
    $line = [DateTimeOffset]::UtcNow.ToString('o') + ' ensure failed: ' +
        $_.Exception.GetType().Name + [Environment]::NewLine
    [IO.File]::AppendAllText($log, $line, (New-Object System.Text.UTF8Encoding($false)))
    exit 1
}
