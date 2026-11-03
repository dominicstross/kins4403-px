[CmdletBinding()]
param (
    [string]$SourceRepo = "kins2203-ik",
    [string[]]$Files = @("viewer.html"),
    [string[]]$Targets = @()
)

$baseDir = $PSScriptRoot

# Auto-detect target course directories if none are explicitly passed
if ($Targets.Count -eq 0) {
    $Targets = Get-ChildItem -Directory -Path $baseDir | 
        Where-Object { 
            $_.Name -ne $SourceRepo -and 
            (Test-Path (Join-Path $_.FullName "content\manifest.json"))
        } | 
        Select-Object -ExpandProperty Name
}

Write-Host "Source Engine: $SourceRepo" -ForegroundColor Cyan
Write-Host "Syncing Files: $($Files -join ', ')" -ForegroundColor Cyan
Write-Host "Target Repos : $($Targets -join ', ')" -ForegroundColor DarkGray
Write-Host "----------------------------------------"

foreach ($target in $Targets) {
    $targetPath = Join-Path $baseDir $target
    Write-Host "`n[$target]" -ForegroundColor Yellow

    foreach ($file in $Files) {
        $srcFile = Join-Path $baseDir "$SourceRepo\$file"
        $destFile = Join-Path $targetPath $file

        if (Test-Path $srcFile) {
            Copy-Item -Path $srcFile -Destination $destFile -Force
            Write-Host "  -> Synced $file" -ForegroundColor Green
        } else {
            Write-Host "  -> Source file not found: $file" -ForegroundColor Red
        }
    }

    # Inspect Git modifications in destination repo
    Push-Location $targetPath
    $changes = git status --short $Files
    if ($changes) {
        Write-Host "  Git Status:" -ForegroundColor Magenta
        $changes | ForEach-Object { Write-Host "    $_" -ForegroundColor White }
    } else {
        Write-Host "  (Files already identical; no changes detected)" -ForegroundColor DarkGray
    }
    Pop-Location
}
Write-Host "`nSync complete." -ForegroundColor Cyan
