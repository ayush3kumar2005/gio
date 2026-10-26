#!/usr/bin/env sh
# Green Inventory Optimizer - start on Mac/Linux. First run installs everything.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
if [ ! -d .venv ]; then python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt; fi
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
[ -d dist ] || npm run build
cd "$ROOT/backend"
echo "Open http://127.0.0.1:8000  (Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
