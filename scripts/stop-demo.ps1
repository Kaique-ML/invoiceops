$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& docker compose stop
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not stop the services."
}
Write-Output "Stopped services; named database, Redis, and upload volumes were preserved."
