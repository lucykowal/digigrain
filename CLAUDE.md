# digigrain

Granular SRC machine for the Elektron Digitakt mk1 (OS 1.53), an elekloader mod. Open work, what is verified and what is
not are tracked in GitHub issues (`gh issue list`; start with the "Tracking" issue), not in the repo. Domain
knowledge (firmware map, hooks, testing, reverse engineering) is in the skills in `.claude/skills/`.

## Commands

```sh
make build | lint | patch | test | check     # core + mod -> out/, test.syx; `make check` is the definition of done
python3 -m unittest tests.test_grain          # host tests of the engine (bit-exact vs a Python model)
uv run --project ../digiemumac python tests/emu/grain_bench.py   # ColdFire instruction counts for gr_block
SYX=$PWD/out/test.syx tests/emu/make_probe_home.sh                # emulator home for our build, then:
GRANULAR=1 FW_DIR=out/emu/home/firmware/<newest> uv run --project ../digiemumac python tests/emu/scale_probe.py
```
The elemods are `out/mod/digigrain-*.elemod` and `out/core/core-2.1.elemod` (load both in elekloader).

## Working agreements

- **Stay inside the directories you are told about.** Never search or list outside them (never `~`, Downloads, other
  repos); report something missing and ask. Subagent prompts must say the same ("read only under <paths>").
- **Never commit firmware** or anything derived from it (`*.syx`, `*.bin`, section binaries, `out/`). Check `git status`.
  `.envrc` and `.mcp.json` are machine-local and ignored.
- Feature branches, conventional commits, squash merge to main; merge only when asked.
- Verify claims: a build that lints is not a working mod. Prefer emulator measurements; mark anything unverified as such.
- Sibling checkouts used: `../elekloader` (core 2.1 = main/v0.4.0), `../Digitakt_OS1.53.syx`, `../digiemumac`.
