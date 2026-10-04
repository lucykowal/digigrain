#!/usr/bin/env bash
# Scaffold mods/<name>/ from templates/mod/.  Usage: scripts/new-mod.sh <name>   (lowercase, digits, dashes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
name="${1:-}"
[[ "$name" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "usage: $0 <name>  (lowercase letters, digits, dashes)" >&2; exit 2; }
dest="$ROOT/mods/$name"
[ ! -e "$dest" ] || { echo "mods/$name already exists" >&2; exit 2; }
cname="${name//-/_}"
mkdir -p "$dest/src" "$dest/tests"
for f in mod.json CLAUDE.md "src/@NAME@.c"; do
  out="$dest/${f//@NAME@/$name}"
  sed -e "s/@NAME@/$name/g" -e "s/@CNAME@/$cname/g" "$ROOT/templates/mod/$f" > "$out"
done
echo "created mods/$name; next: make check MOD=$name"
