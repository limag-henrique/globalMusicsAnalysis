param([switch]$Stop, [switch]$StatusOnly)

$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path -Parent $PSScriptRoot
$pgBase = Join-Path $env:LOCALAPPDATA 'ChartObservatory'
$pgCtl = Join-Path $pgBase 'postgresql16\bin\pg_ctl.exe'
$pgData = Join-Path $pgBase 'postgres16-destination'
if (-not (Test-Path -LiteralPath $pgCtl)) { throw 'PostgreSQL local não preparado.' }
if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    throw 'Cluster de destino não encontrado; este comando não cria banco vazio.'
}
if ($Stop) {
    & $pgCtl -D $pgData -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao parar PostgreSQL.' }
    return
}
& $pgCtl -D $pgData status
if ($LASTEXITCODE -ne 0 -and -not $StatusOnly) {
    $pgLogs = Join-Path $pgBase 'logs'
    New-Item -ItemType Directory -Path $pgLogs -Force | Out-Null
    & $pgCtl -D $pgData -l (Join-Path $pgLogs 'postgres16-destination.log') `
        -o '-p 55433 -h 127.0.0.1' -w start
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar PostgreSQL.' }
}
if ($StatusOnly) { return }
$env:PATH = "$env:USERPROFILE\.local\bin;$pgBase\postgresql16\bin;$env:PATH"
$env:PYTHONIOENCODING = 'utf-8'
$env:POLARS_MAX_THREADS = '2'
$temporary = Join-Path $researchRoot 'data\runtime\tmp'
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
$env:TEMP = $temporary
$env:TMP = $temporary
Write-Output 'PostgreSQL disponível em 127.0.0.1:55433; ambiente preparado nesta sessão.'
