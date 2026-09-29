$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$cacheRoot = Join-Path $projectRoot ".cache"
$dataDir = Join-Path $cacheRoot "postgres-data"
$passwordFile = Join-Path $cacheRoot "postgres-test-password.txt"
$logFile = Join-Path $cacheRoot "postgres.log"
$port = 55432

$env:UV_CACHE_DIR = Join-Path $cacheRoot "uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".tools\python"

Push-Location $backendRoot
try {
    $pgBin = (& $pythonExe -c "import postgresql_binaries; print(postgresql_binaries.bin())").Trim()
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION"))) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    [IO.File]::WriteAllText($passwordFile, "local-test-password`n")
    & (Join-Path $pgBin "initdb.exe") -D $dataDir -U avicola --encoding=UTF8 --locale=C --auth-host=scram-sha-256 --auth-local=trust --pwfile=$passwordFile
    if ($LASTEXITCODE -ne 0) { throw "initdb failed with exit code $LASTEXITCODE" }
}

& (Join-Path $pgBin "pg_isready.exe") -h 127.0.0.1 -p $port -U avicola 2>$null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l $logFile -o "-h 127.0.0.1 -p $port" start
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl failed with exit code $LASTEXITCODE" }
}

$env:PGPASSWORD = "local-test-password"
foreach ($databaseName in @("avicola_pro", "avicola_pro_test")) {
    $databaseExists = $false
    & (Join-Path $pgBin "psql.exe") -h 127.0.0.1 -p $port -U avicola -d postgres -tAc "select 1 from pg_database where datname='$databaseName'" | ForEach-Object { $databaseExists = $_.Trim() -eq "1" }
    if (-not $databaseExists) {
        & (Join-Path $pgBin "createdb.exe") -h 127.0.0.1 -p $port -U avicola $databaseName
        if ($LASTEXITCODE -ne 0) { throw "createdb $databaseName failed with exit code $LASTEXITCODE" }
    }
}

Write-Host "PostgreSQL 16 application and test databases are ready on 127.0.0.1:$port."


