#!/usr/bin/env bash
# Definition of done: build, lint, patch, unit tests. MOD=<name> limits it to one mod; default is every mod.
set -euo pipefail
d="$(dirname "$0")"
"$d/build.sh"; "$d/lint.sh"; "$d/patch.sh"; "$d/test.sh"
