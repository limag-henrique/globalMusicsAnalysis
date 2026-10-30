param([string]$TaskPids, [double]$MinFreeGB = 3)

# Temporary companion for this extraction only. Never traverses or deletes recursively.
$taskRoot = [System.IO.Path]::GetFullPath('D:\PromiscuidadeMusical\.git\lfs\tmp')
if ($taskRoot -ne 'D:\PromiscuidadeMusical\.git\lfs\tmp') { throw 'Unexpected temporary root' }
$taskProcesses = @($TaskPids.Split(',') | ForEach-Object {
    $taskProcess = Get-Process -Id ([int]$_) -ErrorAction SilentlyContinue
    if ($taskProcess) { $null = $taskProcess.Handle; $taskProcess }
})
$taskStop = 'D:\PromiscuidadeMusical\tmp\lfs-space-guard.stop'
while (-not (Test-Path -LiteralPath $taskStop)) {
    $taskAlive = @($taskProcesses | Where-Object { -not $_.HasExited })
    if ($taskAlive.Count -eq 0) { break }
    if ((Get-PSDrive D).Free -lt ($MinFreeGB * 1GB)) {
        $taskFreed = 0
        foreach ($taskFile in @(Get-ChildItem -LiteralPath $taskRoot -File | Where-Object {
            $_.Name -match '^\d+$' -and $_.LastWriteTime -lt (Get-Date).AddSeconds(-10)
        })) {
            if ($taskFile.DirectoryName -ne $taskRoot) { throw 'Unexpected temporary path' }
            try {
                # Exclusive access proves this temporary file is not open in a filter.
                $taskHandle = [System.IO.File]::Open($taskFile.FullName,
                    [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite,
                    [System.IO.FileShare]::None)
                $taskHandle.Dispose()
                Remove-Item -LiteralPath $taskFile.FullName -Force -ErrorAction Stop
                $taskFreed += $taskFile.Length
            } catch { continue }
        }
        @{ freed_bytes = $taskFreed; free_bytes = (Get-PSDrive D).Free;
            updated_at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json -Compress
    }
    Start-Sleep -Seconds 5
}
