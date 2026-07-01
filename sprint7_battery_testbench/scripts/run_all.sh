#!/usr/bin/env bash
# Build the C++ core, run the pytest suite, generate benchmark + cycling data,
# and open the dashboard. Mirrors what a CI job would do.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/4] Building libpolaris_bms..."
(cd cpp && make)

echo "[2/4] Running pytest..."
python3 -m pytest

echo "[3/4] Running estimator benchmark..."
python3 scripts/benchmark_estimators.py

echo "[4/4] Running cycling campaign..."
python3 scripts/run_cycling_campaign.py

echo
echo "Done. Launch the dashboard with:"
echo "  streamlit run dashboard/app.py"
