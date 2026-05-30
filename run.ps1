# Fraud Hunter — one-command run (Windows / PowerShell).
# 1) venv + deps  2) score CSV  3) FastAPI :8000  4) web :5173
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 1. Python venv + deps ---
if (-not (Test-Path "$root\.venv")) { python -m venv "$root\.venv" }
& "$root\.venv\Scripts\python.exe" -m pip install -q -r "$root\api\requirements.txt"

# --- 2. Score the CSV once (writes transactions_flagged.csv) ---
# NOTE: no-op until detector step 1 is implemented; the API serves stub data meanwhile.
try { & "$root\.venv\Scripts\python.exe" -m detector.score "$root\data\transactions.csv" }
catch { Write-Host "detector not implemented yet - API will serve stub data." }

# --- 3. API ---
Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","api.main:app","--port","8000" -WorkingDirectory $root

# --- 4. Web ---
Push-Location "$root\web"
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
Pop-Location
