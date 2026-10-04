#!/usr/bin/env bash
# Boundary check, then lint each selected mod alone and combined with core.
set -euo pipefail
. "$(dirname "$0")/env.sh"
"$PY" "$ROOT/tools/check_boundaries.py" $MODS
CORE="$(ls "$OUT"/core/core-*.elemod | head -1)"
for m in $MODS; do
  M="$(mod_elemod "$m")"
  "$PY" -m elekloader.lint "$M"
  "$PY" -m elekloader.lint "$M" --stock "$ELEKLOADER_STOCK" --with "$CORE"
done
