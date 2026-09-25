param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [Parameter(Mandatory = $true)][ValidateSet("rc", "pilot")][string]$Mode,
    [Parameter(Mandatory = $true)][string]$ExpectedCommit,
    [Parameter(Mandatory = $true)][string]$ExpectedSourceRef,
    [Parameter(Mandatory = $true)][string]$ExpectedTag,
    [Parameter(Mandatory = $true)][string]$ExpectedMigrationHead,
    [Parameter(Mandatory = $true)][int]$MaxEvidenceAgeHours,
    [Parameter(Mandatory = $true)][string]$Report
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
$arguments = @((Join-Path $root "deploy\release_gate.py"), "--bundle", $Bundle, "--mode", $Mode, "--expected-commit", $ExpectedCommit, "--expected-source-ref", $ExpectedSourceRef, "--expected-tag", $ExpectedTag, "--expected-migration-head", $ExpectedMigrationHead, "--max-evidence-age-hours", $MaxEvidenceAgeHours)
$arguments += @("--report", $Report)
& $python @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
