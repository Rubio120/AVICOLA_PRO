$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".tools\python"

Push-Location (Join-Path $projectRoot "backend")
try {
    uv python install 3.13
    uv sync --frozen --all-groups
}
finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd ci
}
finally {
    Pop-Location
}

Write-Host "AVÍCOLA PRO dependencies installed from lockfiles."
