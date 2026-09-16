$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".tools\python"
if (-not $env:AVICOLA_DATABASE_URL) {
    $env:AVICOLA_DATABASE_URL = "postgresql+psycopg://avicola:local-test-password@127.0.0.1:55432/avicola_pro"
}

Push-Location (Join-Path $projectRoot "backend")
try {
    uv run uvicorn avicola_pro.bootstrap.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}

