$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $env:BACKEND_INTERNAL_URL) {
    $env:BACKEND_INTERNAL_URL = "http://127.0.0.1:8000"
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd run dev
}
finally {
    Pop-Location
}

