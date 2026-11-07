$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot 'data/runtime/quota-supervisor-20261031'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
trap {
    [IO.File]::AppendAllText((Join-Path $runtime 'launcher-errors.log'),
        ([DateTimeOffset]::UtcNow.ToString('o') + ' ' + $_.Exception.Message +
         ' ' + $_.ScriptStackTrace + [Environment]::NewLine))
    exit 1
}
$campaignPath = Join-Path $runtime 'campaign.json'
if (Test-Path -LiteralPath $campaignPath) {
    $campaign = Get-Content -LiteralPath $campaignPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($campaign.ends_at)) { exit 0 }
    # Task Scheduler can inherit a different profile environment than the desktop app.
    if ($campaign.local_app_data) { $env:LOCALAPPDATA = $campaign.local_app_data }
    if ($campaign.user_profile) { $env:USERPROFILE = $campaign.user_profile }
    if ($campaign.mode -eq 'targeted_revision') {
        $targetedRuntime = Join-Path $projectRoot 'data/runtime/targeted-revision-20261103'
        if ((Test-Path -LiteralPath (Join-Path $targetedRuntime 'finished.json')) -or
            (Test-Path -LiteralPath (Join-Path $targetedRuntime 'safety-hold.json'))) { exit 0 }
    }
}
Remove-Item Env:PYTHONHOME,Env:PYTHONPATH,Env:__PYVENV_LAUNCHER__ -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath (Join-Path $runtime 'safety-hold.json')) { exit 0 }
Set-Location -LiteralPath $projectRoot
. (Join-Path $PSScriptRoot 'research_environment.ps1') -Quiet
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$scriptPath = Join-Path $PSScriptRoot 'supervise_quota_recovery.py'
if ($campaign.mode -eq 'targeted_revision') {
    $scriptPath = Join-Path $PSScriptRoot 'run_targeted_revision.py'
}
& $pythonPath -u $scriptPath `
    1>> (Join-Path $runtime ('launcher-' + $PID + '.stdout.log')) `
    2>> (Join-Path $runtime ('launcher-' + $PID + '.stderr.log'))
exit $LASTEXITCODE
