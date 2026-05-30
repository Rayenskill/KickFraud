#!/usr/bin/env bash
# Fraud Hunter — one-command run (macOS / Linux).
# 1) venv + deps  2) score CSV  3) FastAPI :8000  4) web :5173
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1. Python venv + deps ---
[ -d "$root/.venv" ] || python3 -m venv "$root/.venv"
# shellcheck disable=SC1091
source "$root/.venv/bin/activate"
pip install -q -r "$root/api/requirements.txt"

# --- 2. Score the CSV once (writes transactions_flagged.csv) ---
# NOTE: no-op until detector step 1 is implemented; the API serves stub data meanwhile.
python -m detector.score "$root/data/transactions.csv" || \
  echo "detector not implemented yet — API will serve stub data."

# --- 3. API ---
( cd "$root" && uvicorn api.main:app --port 8000 ) &

# --- 4. Web ---
cd "$root/web"
[ -d node_modules ] || npm install
npm run dev
