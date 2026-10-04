#!/usr/bin/env bash
# Build core (once) and the mod into out/.
set -euo pipefail
. "$(dirname "$0")/env.sh"
ls "$OUT"/core/core-*.elemod >/dev/null 2>&1 || "$PY" -m elekloader.sdk.build "$CORE_DIR" --out "$OUT/core"
"$PY" -m elekloader.sdk.build "$ROOT/mod" --out "$OUT/mod"
"$PY" -m elekloader.sdk.build "$ROOT/resample" --out "$OUT/resample"
