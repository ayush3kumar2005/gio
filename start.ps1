# Green Inventory Optimizer - start on Windows. First run installs everything.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
}
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path "dist")) { npm run build }

Set-Location "$root\backend"
Write-Host "Open http://127.0.0.1:8000  (Ctrl+C to stop)"
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
