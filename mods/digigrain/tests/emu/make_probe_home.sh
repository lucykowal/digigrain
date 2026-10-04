#!/usr/bin/env bash
# Build a throwaway digiemu home (HOME_DIR, default out/digigrain/emu/home) with a 440 Hz s16 sine in /incoming,
# for mods/digigrain/tests/emu/scale_probe.py. Needs ../digiemumac set up (see the digitakt-testing skill).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
EMU="$ROOT/../digiemumac"; HOME_DIR="${HOME_DIR:-$ROOT/out/digigrain/emu/home}"; WAV="$ROOT/out/digigrain/emu/sine440.wav"
SYX="${SYX:-$ROOT/../Digitakt_OS1.53.syx}"   # stock by default; SYX=out/digigrain/test.syx for our build
mkdir -p "$ROOT/out/digigrain/emu"
python3 - "$WAV" <<'PY'
import math, struct, sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
w.writeframes(b"".join(struct.pack("<h", int(16384 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(48000)))
w.close()
PY
cd "$EMU"
uv run python -m emu.portable --home "$HOME_DIR" --add "$SYX" --yes
FWD="$(ls -dt "$HOME_DIR"/firmware/*/ | head -1)"; FWD="${FWD%/}"
uv run python - "$WAV" "$FWD/plusdrive.img" <<'PY'
import sys
from emu import samples
p = samples.plan([sys.argv[1]], sys.argv[2])
assert p.samples and not p.rejected, p.rejected
samples.write(p)
PY
uv run python -m emu.portable --home "$HOME_DIR" --rebuild "$(basename "$FWD")"
echo "ready: FW_DIR=$FWD"
