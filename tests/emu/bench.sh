#!/usr/bin/env bash
# Instructions per digigrain_granular_render call (one GRANULAR voice playing) for a few settings, in digiemu.
# Usage: tests/emu/bench.sh [firmware folder name]   (default: the newest folder in out/emu/home/firmware)
# POKE words (value is written <<8): 17 TUNE (centre 64 = 0 st, 256 units per semitone: 40 = -24 st, 52 = -12 st),
# 18 ENV, 19 RATE (noon 64 = no grains), 21 POS (0..120), 22 RTIO (8.8: 1 = 1:1, 8 = 8:1), 23 SPRD (noon 64), 24 LEV.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FWD="${1:+$ROOT/out/emu/home/firmware/$1}"
FWD="${FWD:-$(ls -dt "$ROOT"/out/emu/home/firmware/*/ | head -1)}"; FWD="${FWD%/}"
run() {
  printf '%-34s ' "$1"
  MEASURE=1 POKE="$2" GRANULAR=1 FW_DIR="$FWD" uv run --project "$ROOT/../digiemumac" \
    python "$ROOT/tests/emu/scale_probe.py" 2>&1 | grep "instructions per" | sed 's/instructions per digigrain_granular_render call: //'
}
BASE="21:32,24:100,18:64"
run "idle (RATE noon)"               "$BASE,19:64,22:1,23:64"
run "24 Hz, RTIO 1"                  "$BASE,19:36,22:1,23:64"
run "120 Hz, RTIO 1"                 "$BASE,19:1,22:1,23:64"
run "RTIO 8 periodic"                "$BASE,19:1,22:8,23:64"
run "RTIO 8, TUNE -12"               "$BASE,19:1,22:8,23:64,17:52"
run "RTIO 8, TUNE -24"               "$BASE,19:1,22:8,23:64,17:40"
run "RTIO 8 random intervals"        "$BASE,19:127,22:8,23:64"
run "RTIO 8 + SPRD tune + decay"     "21:32,24:100,18:100,19:1,22:8,23:127"
