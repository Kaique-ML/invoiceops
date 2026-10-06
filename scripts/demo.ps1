$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function New-LocalSecret {
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $bytes = [byte[]]::new(48)
        $random.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    } finally {
        $random.Dispose()
    }
}

if (-not (Test-Path -LiteralPath ".env")) {
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $secretBytes = [byte[]]::new(48)
    $random.GetBytes($secretBytes)
    $sessionSecret = [Convert]::ToBase64String($secretBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $random.GetBytes($secretBytes)
    $databasePassword = [Convert]::ToBase64String($secretBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $random.GetBytes($secretBytes)
    $webhookSecret = [Convert]::ToBase64String($secretBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $random.GetBytes($secretBytes)
    $n8nEncryptionKey = [Convert]::ToBase64String($secretBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $random.Dispose()
    @(
        "APP_ENV=development"
        "INVOICEOPS_MODE=demo"
        "SESSION_SECRET=$sessionSecret"
        "DB_PASSWORD=$databasePassword"
        "UPLOAD_DIR=/var/lib/invoiceops/uploads"
        "MAX_UPLOAD_BYTES=10485760"
        "MAX_PAGES=50"
        "MAX_IMAGE_PIXELS=20000000"
        "OLLAMA_HOST=http://host.docker.internal:11434"
        "OLLAMA_MODEL="
        "WEBHOOK_URL=http://api:8000/integration/test/receive"
        "WEBHOOK_SECRET=$webhookSecret"
        "N8N_ENCRYPTION_KEY=$n8nEncryptionKey"
    ) | Set-Content -Encoding ascii -LiteralPath ".env"
    Write-Output "Created a local .env with random secrets. It is ignored by Git."
} elseif (-not (Select-String -Quiet -Path ".env" -Pattern '^N8N_ENCRYPTION_KEY=')) {
    Add-Content -Encoding ascii -LiteralPath ".env" -Value "N8N_ENCRYPTION_KEY=$(New-LocalSecret)"
    Write-Output "Added a local n8n encryption key to the ignored .env file."
}

& docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to build or start the services."
}
Write-Output "Waiting for the API health endpoint..."
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 3
        if ($health.status -eq "ready") {
            Write-Output "InvoiceOps is ready at http://127.0.0.1:8000"
            Write-Output "Create the explicit local demo account with:"
            Write-Output "  docker compose exec api uv run --no-sync python -m invoiceops.cli seed-demo"
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
& docker compose ps
throw "Services did not become ready. Inspect logs with: docker compose logs --tail 100 api worker db redis"
