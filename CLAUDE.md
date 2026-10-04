# lucys-mod

Elekloader mods for the Elektron Digitakt mk1 (OS 1.53). One repo, one directory per mod under `mods/`, shared code in
`common/`, shared platform knowledge in the skills in `.claude/skills/`. Open work, what is verified and what is not are
tracked in GitHub issues (`gh issue list`; start with the "Tracking" issue, one per mod, label `mod:<name>`), not in the repo.

## Mods

| mod | what | notes |
|---|---|---|
| `mods/digigrain` | GRANULAR SRC machine (id 6) | `mods/digigrain/CLAUDE.md` |

## Layout and dependency rule

```
mods/<name>/   mod.json, src/, tests/, optional tools/, CLAUDE.md    one self-contained mod
common/        include/, src/, tests/                                shared code, used only by opt-in
scripts/ tools/ tests/ templates/                                    mod-agnostic build + checks
out/core/  out/<name>/                                               build output (ignored)
```

- **Dependencies point one way: `mods/* -> common/`.** Never mod -> mod; a mod's `requires` is only `core`.
  `tools/check_boundaries.py` (part of `make lint`) fails on it. Do not `#include` or list sources from another mod.
- **Extract to `common/` on the second use**, in its own commit; do not pre-extract. A mod opts in by listing
  `common/src/x.c` in `sources` and writing `#include "common/include/x.h"` (the build stages `common/` beside the mod).
  A change under `common/` needs `make check` green for **every** mod.
- Prefix every global symbol with the mod id (`digigrain_...`); all mods share one address space.
- Platform knowledge (firmware, hooks, DSP, testing) belongs in the skills; a mod's own design and measurements belong in
  `mods/<name>/CLAUDE.md`. A new mod starts with `make new-mod NAME=<name>`.

## Commands

```sh
make build | lint | patch | test | check     # every mod; `make check` is the definition of done
make check MOD=digigrain                     # one mod only (also build/lint/patch/test)
make new-mod NAME=<name>                     # scaffold mods/<name> from templates/mod
```
Elemods: `out/<mod>/<mod>-*.elemod` and `out/core/core-2.1.elemod` (load both in elekloader); `out/<mod>/test.syx` is the
patched firmware. Mod-specific commands (benchmarks, emulator probes) are in `mods/<name>/CLAUDE.md`.

## Working agreements

- **Stay inside the directories you are told about.** Never search or list outside them (never `~`, Downloads, other
  repos); report something missing and ask. Subagent prompts must say the same ("read only under <paths>").
- **Never commit firmware** or anything derived from it (`*.syx`, `*.bin`, section binaries, `out/`). Check `git status`.
  `.envrc` and `.mcp.json` are machine-local and ignored.
- Feature branches, conventional commits with the mod as scope (`feat(digigrain): ...`, `refactor(common): ...`), squash
  merge to main; merge only when asked.
- Verify claims: a build that lints is not a working mod. Prefer emulator measurements; mark anything unverified as such.
- Sibling checkouts used: `../elekloader` (core 2.1 = main/v0.4.0), `../Digitakt_OS1.53.syx`, `../digiemumac`.
