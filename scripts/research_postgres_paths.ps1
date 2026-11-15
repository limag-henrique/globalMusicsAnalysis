function Get-ResearchPostgresLayout {
    [CmdletBinding()]
    param(
        [string]$LocalDataRoot = $env:LOCALAPPDATA,
        [string]$OverrideBase = $env:CHART_OBSERVATORY_POSTGRES_BASE
    )

    # Packaged Windows apps can redirect LocalAppData. A later runtime can see
    # the physical package path instead, while the existing cluster stays there.
    $bases = @()
    if ($OverrideBase) {
        $bases = @($OverrideBase)
    } else {
        $nativeBase = Join-Path $LocalDataRoot 'ChartObservatory'
        $bases += $nativeBase
        $packages = Join-Path $LocalDataRoot 'Packages'
        if (Test-Path -LiteralPath $packages) {
            $bases += @(Get-ChildItem -LiteralPath $packages -Directory -Filter 'OpenAI.Codex*' |
                ForEach-Object { Join-Path $_.FullName 'LocalCache/Local/ChartObservatory' })
        }
    }
    $layouts = @($bases | Select-Object -Unique | ForEach-Object {
        $base = [IO.Path]::GetFullPath($_)
        $binaries = Join-Path $base 'postgresql16/bin'
        $cluster = Join-Path $base 'postgres16-destination'
        $versionFile = Join-Path $cluster 'PG_VERSION'
        if ((Test-Path -LiteralPath (Join-Path $binaries 'pg_ctl.exe')) -and
            (Test-Path -LiteralPath (Join-Path $binaries 'pg_isready.exe')) -and
            (Test-Path -LiteralPath $versionFile) -and
            ((Get-Content -LiteralPath $versionFile -Raw).Trim() -eq '16')) {
            [pscustomobject]@{ Base = $base; Binaries = $binaries; Cluster = $cluster }
        }
    })
    if ($layouts.Count -eq 0) {
        throw 'PostgreSQL 16 existente não encontrado; nenhum banco vazio foi criado.'
    }
    if ($layouts.Count -gt 1) {
        throw 'Mais de um cluster de destino encontrado; defina CHART_OBSERVATORY_POSTGRES_BASE explicitamente.'
    }
    return $layouts[0]
}
