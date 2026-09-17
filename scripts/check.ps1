$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".tools\python"
if (-not $env:AVICOLA_DATABASE_URL) {
    $env:AVICOLA_DATABASE_URL = "postgresql+psycopg://avicola:local-test-password@127.0.0.1:55432/avicola_pro"
}
if (-not $env:AVICOLA_TEST_DATABASE_URL) {
    $env:AVICOLA_TEST_DATABASE_URL = "postgresql+psycopg://avicola:local-test-password@127.0.0.1:55432/avicola_pro_test"
}
if (-not $env:AVICOLA_SESSION_HMAC_KEY) {
    $env:AVICOLA_SESSION_HMAC_KEY = "local-test-session-hmac-key-that-is-long-enough-for-security"
}
if ($env:AVICOLA_TEST_DATABASE_URL -eq $env:AVICOLA_DATABASE_URL) {
    throw "AVICOLA_TEST_DATABASE_URL must use a dedicated database, separate from AVICOLA_DATABASE_URL"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Join-Path $projectRoot "backend")
try {
    Invoke-Checked { uv lock --check } "uv lock check"
    Invoke-Checked { uv run ruff format --check . } "backend format check"
    Invoke-Checked { uv run ruff check . } "backend lint"
    Invoke-Checked { uv run mypy src tests } "backend typecheck"
    Invoke-Checked { uv run pytest } "backend tests"
}
finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    Invoke-Checked { npm.cmd run lint } "frontend lint"
    Invoke-Checked { npm.cmd run typecheck } "frontend typecheck"
    Invoke-Checked { npm.cmd test } "frontend tests"
    Invoke-Checked { npm.cmd run build } "frontend build"
}
finally {
    Pop-Location
}
