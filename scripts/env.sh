# Sourced by the other scripts. Resolves repo paths, stock OS and toolchain prefix.
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
mkdir -p "$OUT"
