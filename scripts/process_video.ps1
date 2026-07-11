# process_video.ps1 - Process one match video end-to-end (detect -> track ->
# identify -> events -> stats -> reports). Thin wrapper around `playsight process`.
#
# Usage:
#   .\scripts\process_video.ps1 -Video data\demo\demo_match.mp4
#   .\scripts\process_video.ps1 -Video match.mp4 -MatchId <id> -Club my-club
#   .\scripts\process_video.ps1 -Video match.mp4 -NoEager   # use a Celery worker
#
# Requires the package installed in the active environment: pip install -e ".[dev]"

param(
    [Parameter(Mandatory = $true)]
    [string]$Video,
    [string]$MatchId,
    [string]$Club,
    [switch]$NoEager
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path $Video)) {
    Write-Error "Video not found: $Video"
    exit 1
}

$cliArgs = @("process", $Video)
if ($MatchId) { $cliArgs += @("--match-id", $MatchId) }
if ($Club) { $cliArgs += @("--club", $Club) }
if ($NoEager) { $cliArgs += "--no-eager" }

& playsight @cliArgs
exit $LASTEXITCODE
