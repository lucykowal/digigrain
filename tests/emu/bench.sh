#!/usr/bin/env bash
# Instructions per lucys_granular_render call (one GRANULAR voice playing) for a few settings, in digiemu.
# Usage: tests/emu/bench.sh [firmware folder name]   (default: the newest folder in out/emu/home/firmware)
# Words: 18 PLAY, 19 DENS, 21 STRT, 22 SHAPE, 23 RAND, 24 LEV (values 0..127).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FWD="${1:+$ROOT/out/emu/home/firmware/$1}"
FWD="${FWD:-$(ls -dt "$ROOT"/out/emu/home/firmware/*/ | head -1)}"; FWD="${FWD%/}"
run() {
  printf '%-34s ' "$1"
  MEASURE=1 POKE="$2" GRANULAR=1 FW_DIR="$FWD" uv run --project "$ROOT/../digiemumac" \
    python "$ROOT/tests/emu/scale_probe.py" 2>&1 | grep "instructions per" | sed 's/instructions per lucys_granular_render call: //'
}
run "idle (DENS noon)"               "19:64,21:32,22:64,23:0,24:100,18:3"
run "default-ish (24 Hz, sine)"      "19:36,21:32,22:64,23:0,24:100,18:3"
run "dense (120 Hz, sine)"           "19:1,21:32,22:64,23:0,24:100,18:3"
run "dense + RAND 127 + decay"       "19:1,21:32,22:100,23:127,24:100,18:3"
run "dense reverse"                  "19:1,21:60,22:64,23:0,24:100,18:0"
