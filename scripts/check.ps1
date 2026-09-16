$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".tools\python"

Push-Location (Join-Path $projectRoot "backend")
try {
    uv lock --check
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy src tests
    uv run pytest
}
finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd run lint
    npm.cmd run typecheck
    npm.cmd test
    npm.cmd run build
}
finally {
    Pop-Location
}

