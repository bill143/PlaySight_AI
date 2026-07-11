# dev_up.ps1 - Start the full PlaySight docker-compose stack and initialize the DB.
#
# Usage:
#   .\scripts\dev_up.ps1              # build + start + wait for API + init-db
#   .\scripts\dev_up.ps1 -NoBuild     # skip image rebuild
#
# Services: api (:8000), worker, dashboard (:3000), postgres (:5432),
# redis (:6379), minio (:9000 / console :9001).

param(
    [switch]$NoBuild,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("compose", "up", "-d")
if (-not $NoBuild) { $composeArgs += "--build" }

Write-Host "Starting docker-compose stack..." -ForegroundColor Cyan
& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

$healthUrl = "http://localhost:8000/api/v1/health/live"
Write-Host "Waiting for the API at $healthUrl ..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        # API not up yet; keep polling.
    }
    Start-Sleep -Seconds 3
}
if (-not $ready) {
    Write-Error "API did not become healthy within $TimeoutSeconds seconds. Check: docker compose logs api"
    exit 1
}

# The API creates tables on startup; run init-db explicitly anyway (idempotent).
Write-Host "Initializing the database (idempotent)..." -ForegroundColor Cyan
& docker compose exec -T api playsight init-db
if ($LASTEXITCODE -ne 0) {
    Write-Error "playsight init-db failed inside the api container (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "PlaySight stack is up:" -ForegroundColor Green
Write-Host "  API        http://localhost:8000  (docs at /docs)"
Write-Host "  Dashboard  http://localhost:3000"
Write-Host "  MinIO      http://localhost:9001  (minioadmin / minioadmin)"
Write-Host ""
Write-Host "Stop with: docker compose down"
