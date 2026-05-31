#!/usr/bin/env bash
# Fraud Hunter — one-command run (macOS / Linux).
# 1) venv + deps  2) seed Mongo from CSV (if configured)  3) FastAPI :8000  4) web :5173
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1. Python venv + deps ---
[ -d "$root/.venv" ] || python3 -m venv "$root/.venv"
# shellcheck disable=SC1091
source "$root/.venv/bin/activate"
pip install -q -r "$root/api/requirements.txt"

# --- 2. Seed MongoDB from the CSV (skipped gracefully if MONGO_URI unset/unreachable;
#        the API then falls back to CSV-backed in-memory mode). Configure secrets in .env. ---
python -m scripts.seed_mongo || echo "Mongo seed skipped — API will use CSV fallback."

# --- 3. API ---
( cd "$root" && uvicorn api.main:app --port 8000 ) &

# --- 4. Web ---
cd "$root/web"
[ -d node_modules ] || npm install
npm run dev
