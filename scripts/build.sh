#!/usr/bin/env bash
# Builds everything editpdf deploys: the web interface (frontend/dist) and the
# Cloud Builder Function package (backend/dist/function), which carries it.
#
#   ./scripts/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

npm ci
npm run build --workspace frontend
"$PYTHON" backend/scripts/build_function.py
