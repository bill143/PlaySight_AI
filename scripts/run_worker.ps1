# run_worker.ps1 - Run a Celery worker consuming PlaySight jobs (requires redis).
# Thin wrapper around `playsight serve worker`.
#
# Usage:
#   .\scripts\run_worker.ps1
#   .\scripts\run_worker.ps1 -LogLevel DEBUG -Concurrency 2 -Pool solo
#
# On Windows the pool defaults to 'solo' (prefork is unsupported there).
# Requires the package installed in the active environment: pip install -e ".[dev]"

param(
    [string]$LogLevel = "INFO",
    [int]$Concurrency = 0,
    [string]$Pool = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$cliArgs = @("serve", "worker", "--loglevel", $LogLevel)
if ($Concurrency -gt 0) { $cliArgs += @("--concurrency", $Concurrency) }
if ($Pool) { $cliArgs += @("--pool", $Pool) }

& playsight @cliArgs
exit $LASTEXITCODE
