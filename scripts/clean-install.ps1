$ErrorActionPreference = "Stop"

$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$targets = @(
    [IO.Path]::GetFullPath((Join-Path $projectRoot "backend\.venv")),
    [IO.Path]::GetFullPath((Join-Path $projectRoot "frontend\node_modules")),
    [IO.Path]::GetFullPath((Join-Path $projectRoot "frontend\.next"))
)

foreach ($target in $targets) {
    if (-not $target.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to remove path outside project: $target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

& (Join-Path $PSScriptRoot "bootstrap.ps1")
