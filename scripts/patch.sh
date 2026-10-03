#!/usr/bin/env bash
# Produce out/test.syx: stock + core + mod.
set -euo pipefail
. "$(dirname "$0")/env.sh"
CORE="$(ls "$OUT"/core/core-*.elemod | head -1)"
MOD="$(ls "$OUT"/mod/lucys-granular-*.elemod | head -1)"
"$PY" -m elekloader.patch --stock "$ELEKLOADER_STOCK" --mod "$CORE" --mod "$MOD" --out "$OUT/test.syx" --version 0.0t
