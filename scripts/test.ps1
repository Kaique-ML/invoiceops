$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path -LiteralPath ".env")) {
    Write-Output "Generating local secrets and starting the demo dependencies first."
    & .\scripts\demo.ps1
    if ($LASTEXITCODE -ne 0) {
        throw "Could not prepare the local test environment."
    }
}

& docker compose --profile checks run --build --rm checks
if ($LASTEXITCODE -ne 0) {
    throw "Lint, type checking, or tests failed. Review the command output."
}
