# digigrain collection

Custom firmware mods for the Elektron Digitakt (mk1, OS 1.53), built with
[elekloader](../elekloader). One directory per mod under `mods/`; shared code in `common/`.
Open work and test status are in the GitHub issue tracker. Design notes for
contributors and agents are in `.claude/skills/` and each mod's `CLAUDE.md`.

| mod | what |
|---|---|
| [`digigrain`](mods/digigrain) | a granular playback SRC machine (id 6, GRANULAR), verified in the emulator on the real firmware |

## Prerequisites

- Python 3.9+ (`.python-version` pins 3.12.0)
- m68k binutils + gcc: `brew install m68k-elf-gcc m68k-elf-binutils` (scripts
  set `ELEKLOADER_CROSS=m68k-elf-` automatically)
- Sibling checkouts: `../elekloader` and the stock `../Digitakt_OS1.53.syx`
  (override with `ELEKLOADER_DIR`, `ELEKLOADER_STOCK`)
- Optional, for emulator tests: `pip install -r requirements-dev.txt`

## Quickstart

```sh
make build   # core + every mod -> out/core, out/<mod>/
make lint    # dependency-rule check, then each mod alone and combined with core
make patch   # out/<mod>/test.syx = stock + core + that mod
make test    # unit tests (stdlib only)
make check   # all of the above
make check MOD=digigrain    # one mod only
make new-mod NAME=my-mod    # scaffold a new mod from templates/mod
```

## Layout

- `mods/<name>/` — one self-contained mod: `mod.json`, `src/`, `tests/` (host tests; `tests/emu/` digiemu probes), optional `tools/` generators, `CLAUDE.md`
- `common/` — code shared by mods (`include/`, `src/`, `tests/`); mods opt in per file. Mods depend on `common/`, never on each other (enforced by `tools/check_boundaries.py` in `make lint`)
- `scripts/` — mod-agnostic build/lint/patch/test/check wrappers (`MOD=<name>` selects one mod)
- `tests/` — checks that apply to every mod (`test_build.py`)
- `tools/` — `stage_mod.py` (stages a mod with `common/` for the SDK), `check_boundaries.py`
- `templates/mod/` — scaffold used by `make new-mod`
- `.claude/skills/` — agent notes for mod development (platform knowledge shared by all mods)

## Flashing and recovery

Back up first. If a build misbehaves: hold FUNC while powering on for the
startup menu, then send the stock `.syx`. Never commit firmware (`*.syx`,
`*.bin`, `*.elemod` are ignored).

## Granular Parameters

- A. TUNE: Pitch of each grain. Independent of grain length.
- B. RATE: Grain spawn rate. Nothing at noon, counter-clockwise for periodic
  rates, clockwise for random.
- C. SPRD: Random grain variation. None at noon, counter-clockwise randomizes
  POS, clockwise randomizes TUNE.
- D. SAMP: Sample selection.
- E. POS: Grain playhead, the position where grains start when spawned.
- F. RTIO: Grain length as a ratio of the spawn period, 0.25 to 8.00 (1:4 to
  8:1). At the maximum RTIO with a periodic RATE, 8 grains play at once.
- G. ENV: Grain envelope. Sine at noon, counter-clockwise for gate, clockwise
  for a quick decay.
- H. LEV: Source level.

### Implementation notes

- Grains play forward only. There is no PLAY parameter: the stock voice the
  machine borrows is forced to loop, so a held note sustains.
- Grain length is RTIO times the spawn period, independent of pitch, so a
  voice never has more than 8 grains (the per-voice pool size). Length is
  capped at 65535 frames (1.37 s).
- A new GRANULAR track starts with RATE 36 (periodic, about 24 Hz), SPRD 64
  (none), POS 0, RTIO 1.00 and ENV 64 (sine).
- The RATE and POS labels come from hooks on the page's label lookups (the
  firmware has too few spare parameter descriptors for unique names).
- RATE, SPRD and ENV print readable values (Hz / OFF, POS or PIT percent, SINE / GATE / DCAY percent)
  through hooks on the page's two value-to-text routines.
- Open work (further optimisation, hardware tests) is in the issue tracker.
