# Fraud Hunter — one-command run (Windows / PowerShell).
# 1) venv + deps  2) seed Mongo from CSV (if configured)  3) FastAPI :8000  4) web :5173
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 1. Python venv + deps ---
if (-not (Test-Path "$root\.venv")) { python -m venv "$root\.venv" }
& "$root\.venv\Scripts\python.exe" -m pip install -q -r "$root\api\requirements.txt"

# --- 2. Seed MongoDB from the CSV (skipped gracefully if MONGO_URI unset/unreachable;
#        the API then falls back to CSV-backed in-memory mode). Configure secrets in .env. ---
& "$root\.venv\Scripts\python.exe" -m scripts.seed_mongo

# --- 3. API ---
Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","api.main:app","--port","8000" -WorkingDirectory $root

# --- 4. Web ---
Push-Location "$root\web"
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
Pop-Location
