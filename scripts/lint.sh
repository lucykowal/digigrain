#!/usr/bin/env bash
# Lint the mod alone and combined with core.
set -euo pipefail
. "$(dirname "$0")/env.sh"
CORE="$(ls "$OUT"/core/core-*.elemod | head -1)"
MOD="$(ls "$OUT"/mod/digigrain-*.elemod | head -1)"
"$PY" -m elekloader.lint "$MOD"
"$PY" -m elekloader.lint "$MOD" --stock "$ELEKLOADER_STOCK" --with "$CORE"
# digiresample conflicts with digigrain (same hooks and descriptors): lint it on its own
RS="$(ls "$OUT"/resample/digiresample-*.elemod | head -1)"
"$PY" -m elekloader.lint "$RS"
"$PY" -m elekloader.lint "$RS" --stock "$ELEKLOADER_STOCK" --with "$CORE"
