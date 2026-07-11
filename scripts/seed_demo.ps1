# seed_demo.ps1 - Initialize the database and seed the demo club/team/players
# plus a deterministic synthetic match video (data\demo\demo_match.mp4).
# Thin wrapper around `playsight init-db` + `playsight seed-demo`.
#
# Usage:
#   .\scripts\seed_demo.ps1
#   .\scripts\seed_demo.ps1 -Force     # regenerate the demo video
#
# Requires the package installed in the active environment: pip install -e ".[dev]"

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& playsight init-db
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$cliArgs = @("seed-demo")
if ($Force) { $cliArgs += "--force" }

& playsight @cliArgs
exit $LASTEXITCODE
