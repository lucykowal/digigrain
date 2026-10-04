#!/usr/bin/env bash
# Produce out/<mod>/test.syx (stock + core + that mod) for each selected mod.
set -euo pipefail
. "$(dirname "$0")/env.sh"
CORE="$(ls "$OUT"/core/core-*.elemod | head -1)"
for m in $MODS; do
  "$PY" -m elekloader.patch --stock "$ELEKLOADER_STOCK" --mod "$CORE" --mod "$(mod_elemod "$m")" --out "$OUT/$m/test.syx" --version 0.0t
done
