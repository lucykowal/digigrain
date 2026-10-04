#!/usr/bin/env bash
# Host unit tests: repo-level tests/, common/tests/, and tests/ of each selected mod (MOD=<name>, default all).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mods="${MOD:-$(cd "$ROOT/mods" && for d in */; do [ -f "$d/mod.json" ] && echo "${d%/}"; done)}"
dirs="$ROOT/tests $ROOT/common/tests"
for m in $mods; do dirs="$dirs $ROOT/mods/$m/tests"; done
for d in $dirs; do
  ls "$d"/test_*.py >/dev/null 2>&1 || continue
  echo "== $d"
  python3 -m unittest discover -s "$d" -v
done
