#!/usr/bin/env bash
# Produce out/test.syx: stock + core + mod.
set -euo pipefail
. "$(dirname "$0")/env.sh"
CORE="$(ls "$OUT"/core/core-*.elemod | head -1)"
MOD="$(ls "$OUT"/mod/digigrain-*.elemod | head -1)"
"$PY" -m elekloader.patch --stock "$ELEKLOADER_STOCK" --mod "$CORE" --mod "$MOD" --out "$OUT/test.syx" --version 0.0t
RS="$(ls "$OUT"/resample/digiresample-*.elemod | head -1)"
"$PY" -m elekloader.patch --stock "$ELEKLOADER_STOCK" --mod "$CORE" --mod "$RS" --out "$OUT/test-resample.syx" --version 0.0t
# both together must be refused (overlapping sites)
if "$PY" -m elekloader.patch --stock "$ELEKLOADER_STOCK" --mod "$CORE" --mod "$MOD" --mod "$RS" --out "$OUT/both.syx" --version 0.0t >/dev/null 2>&1; then
  echo "digigrain + digiresample unexpectedly patch together" >&2; exit 1
fi
