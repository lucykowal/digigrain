# Sourced by the other scripts. Resolves repo paths, stock OS and toolchain prefix.
# MOD=<name> selects one mod under mods/; unset means every mod. Sets MODS (space separated).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ELEKLOADER_DIR="${ELEKLOADER_DIR:-$ROOT/../elekloader}"
export PYTHONPATH="$ELEKLOADER_DIR${PYTHONPATH:+:$PYTHONPATH}"
export ELEKLOADER_STOCK="${ELEKLOADER_STOCK:-${DIGITAKT_OS:-$ROOT/../Digitakt_OS1.53.syx}}"
# SDK expects m68k-linux-gnu-*; Homebrew ships m68k-elf-*.
if ! command -v m68k-linux-gnu-gcc >/dev/null 2>&1 && command -v m68k-elf-gcc >/dev/null 2>&1; then
  export ELEKLOADER_CROSS="${ELEKLOADER_CROSS:-m68k-elf-}"
fi
OUT="$ROOT/out"
CORE_DIR="$ELEKLOADER_DIR/mods/core"
PY="${PYTHON:-python3}"
[ -f "$ELEKLOADER_STOCK" ] || { echo "stock OS not found: $ELEKLOADER_STOCK (set ELEKLOADER_STOCK)" >&2; exit 2; }
if [ -n "${MOD:-}" ]; then
  [ -f "$ROOT/mods/$MOD/mod.json" ] || { echo "no such mod: $MOD (see mods/)" >&2; exit 2; }
  MODS="$MOD"
else
  MODS="$(cd "$ROOT/mods" && for d in */; do [ -f "$d/mod.json" ] && echo "${d%/}"; done)"
fi
mkdir -p "$OUT"
# Path of mod $1's built elemod.
mod_elemod() { ls "$OUT/$1"/"$1"-*.elemod 2>/dev/null | head -1; }
