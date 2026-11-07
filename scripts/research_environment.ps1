param([switch]$Stop, [switch]$StatusOnly, [switch]$Quiet)

$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path -Parent $PSScriptRoot
$pgBase = Join-Path $env:LOCALAPPDATA 'ChartObservatory'
$pgCtl = Join-Path $pgBase 'postgresql16\bin\pg_ctl.exe'
$pgData = Join-Path $pgBase 'postgres16-destination'
if (-not (Test-Path -LiteralPath $pgCtl)) { throw 'PostgreSQL local não preparado.' }
if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    throw 'Cluster de destino não encontrado; este comando não cria banco vazio.'
}
$bootstrapLogs = Join-Path $researchRoot 'data/runtime/quota-supervisor-20261031'
New-Item -ItemType Directory -Force -Path $bootstrapLogs | Out-Null

function Invoke-ResearchPgCtl([string]$ControlArguments) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $pgCtl
    $info.Arguments = $ControlArguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.Encoding]::Default
    $info.StandardErrorEncoding = [Text.Encoding]::Default
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(65000)) { throw 'pg_ctl excedeu o tempo de resposta.' }
        # Wait for pg_ctl itself, never for the lifetime of its background server.
        $output = ''
        $errorOutput = ''
        if ($stdoutTask.Wait(1000)) { $output = $stdoutTask.Result }
        if ($stderrTask.Wait(1000)) { $errorOutput = $stderrTask.Result }
        $result = @{ ExitCode = $process.ExitCode; Output = $output; ErrorOutput = $errorOutput }
        $line = [DateTimeOffset]::UtcNow.ToString('o') + ' pg_ctl exit=' + $process.ExitCode +
            ' ' + ($output + $errorOutput).Trim() + [Environment]::NewLine
        [IO.File]::AppendAllText((Join-Path $bootstrapLogs 'postgres-bootstrap.log'),
            $line, (New-Object System.Text.UTF8Encoding($false)))
        return $result
    } finally {
        $process.Dispose()
    }
}

# Startup and the scheduled watchdog may reach this code at the same instant.
# Serialize status/start, while PostgreSQL itself retains ownership of its PID file.
$bootstrapMutex = New-Object System.Threading.Mutex($false,
    'Local\PromiscuidadeMusical-Postgres16-55433-Bootstrap')
$ownsBootstrap = $false
try {
    try { $ownsBootstrap = $bootstrapMutex.WaitOne(60000) }
    catch [System.Threading.AbandonedMutexException] { $ownsBootstrap = $true }
    if (-not $ownsBootstrap) { throw 'Tempo esgotado aguardando a inicialização do PostgreSQL.' }
    if ($Stop) {
        $result = Invoke-ResearchPgCtl ('-D "' + $pgData + '" -m fast -t 60 -w stop')
        if ($result.ExitCode -ne 0) { throw 'Falha ao parar PostgreSQL; consulte postgres-bootstrap.log.' }
    } else {
        $result = Invoke-ResearchPgCtl ('-D "' + $pgData + '" status')
        if ($StatusOnly -and -not $Quiet) {
            Write-Output ($result.Output + $result.ErrorOutput).Trim()
        }
        if ($result.ExitCode -ne 0 -and -not $StatusOnly) {
            $pgLogs = Join-Path $pgBase 'logs'
            New-Item -ItemType Directory -Path $pgLogs -Force | Out-Null
            $result = Invoke-ResearchPgCtl ('-D "' + $pgData + '" -l "' +
                (Join-Path $pgLogs 'postgres16-destination.log') +
                '" -o "-p 55433 -h 127.0.0.1" -t 60 -w start')
            if ($result.ExitCode -ne 0) {
                throw 'Falha ao iniciar PostgreSQL; consulte postgres-bootstrap.log.'
            }
        }
    }
} finally {
    if ($ownsBootstrap) { $bootstrapMutex.ReleaseMutex() }
    $bootstrapMutex.Dispose()
}
if ($Stop) { return }
if ($StatusOnly) { return }
$env:PATH = "$env:USERPROFILE\.local\bin;$pgBase\postgresql16\bin;$env:PATH"
$env:PYTHONIOENCODING = 'utf-8'
$env:POLARS_MAX_THREADS = '2'
$temporary = Join-Path $researchRoot 'data\runtime\tmp'
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
$env:TEMP = $temporary
$env:TMP = $temporary
if (-not $Quiet) {
    Write-Output 'PostgreSQL disponível em 127.0.0.1:55433; ambiente preparado nesta sessão.'
}
