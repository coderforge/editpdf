# Builds everything editpdf deploys: the web interface (frontend/dist) and the
# Cloud Builder Function package (backend/dist/function), which carries it.
#
#   .\scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

npm ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build --workspace frontend
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python backend/scripts/build_function.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
