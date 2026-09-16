#!/usr/bin/env bash
#
# Run the WCP dashboard data collectors using the repo's own virtualenv.
#
# Why this wrapper exists
# -----------------------
# `python3` is NOT stable across contexts on this machine:
#   - interactive shells        -> /usr/bin/python3        (3.12, user-site has geopandas)
#   - background / cron shells  -> ~/miniconda3/bin/python3 (3.13, geopandas ABSENT)
# miniconda appears early in PATH for non-interactive shells, so a bare
# `python3 scripts/collect_x.py` silently fails in scheduled runs.
#
# Always invoke collectors through this script (or the .venv interpreter
# directly) rather than relying on `python3` from PATH.
#
# Usage:
#   scripts/run_collectors.sh              # run every collector
#   scripts/run_collectors.sh gtfs         # run one by keyword
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: venv interpreter not found at $PY" >&2
  echo "Create it with: /usr/bin/python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 3
fi

# Fail loudly if the venv is missing required packages, naming the interpreter
# so the source of the problem is unambiguous.
if ! "$PY" -c "import geopandas, shapely, pyproj, pandas" 2>/dev/null; then
  echo "ERROR: $PY is missing required packages." >&2
  echo "Fix: $REPO/.venv/bin/python -m pip install -r $REPO/requirements.txt" >&2
  exit 4
fi

COLLECTORS=(
  "collect_qcew_employment.py"
  "collect_gtfs_frequency.py"
  "collect_nyopendata_property.py"
)

FILTER="${1:-}"
status=0

for name in "${COLLECTORS[@]}"; do
  if [[ -n "$FILTER" && "$name" != *"$FILTER"* ]]; then
    continue
  fi
  echo "=== $name ==="
  cd "$REPO" || exit 1
  # NOTE: do NOT pipe this through tail/head. Piping makes $? report the exit
  # status of the pager, which previously masked total collector failure as
  # "exit code 0".
  if "$PY" "scripts/$name"; then
    echo "--- $name OK"
  else
    rc=$?
    echo "--- $name FAILED (exit $rc)" >&2
    status=$rc
  fi
  echo
done

exit "$status"
