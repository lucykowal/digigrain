#!/usr/bin/env bash
# Definition of done: build, lint, patch, unit tests.
set -euo pipefail
d="$(dirname "$0")"
"$d/build.sh"; "$d/lint.sh"; "$d/patch.sh"
python3 -m unittest discover -s "$d/../tests" -v
