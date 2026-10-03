# lucy's mod

Custom firmware mods for the Elektron Digitakt (mk1, OS 1.53), built with
[elekloader](../elekloader).

Planned: a granular playback SRC machine. `mod/` is currently a scaffold that
draws a marker.

## Prerequisites

- Python 3.9+ (`.python-version` pins 3.12.0)
- m68k binutils + gcc: `brew install m68k-elf-gcc m68k-elf-binutils` (scripts
  set `ELEKLOADER_CROSS=m68k-elf-` automatically)
- Sibling checkouts: `../elekloader` and the stock `../Digitakt_OS1.53.syx`
  (override with `ELEKLOADER_DIR`, `ELEKLOADER_STOCK`)
- Optional, for emulator tests: `pip install -r requirements-dev.txt`

## Quickstart

```sh
make build   # core + mod -> out/
make lint    # mod alone and combined with core
make patch   # out/test.syx = stock + core + mod
make test    # unit tests (stdlib only)
make check   # all of the above
```

## Layout

- `mod/` — the elekloader mod: `grain.c` (engine), `granular.c` (firmware glue), `synth.s` (render hook), `machine.s` (machine descriptor)
- `scripts/` — build/lint/patch/check wrappers
- `tests/` — host tests (`test_grain.py` vs a Python model, `test_build.py`); `tests/emu/` digiemu probes (see the digitakt-testing skill)
- `tools/` — table generators (`gen_window.py` -> `mod/window.h`)
- `.claude/skills/` — agent notes for mod development

## Flashing and recovery

Back up first. If a build misbehaves: hold FUNC while powering on for the
startup menu, then send the stock `.syx`. Never commit firmware (`*.syx`,
`*.bin`, `*.elemod` are ignored).

## Future work

- Machine registration and SRC page hooks for the granular engine
- Grain buffer within the shared RAM budget (128 KB) and `.fast` SRAM (2304 B)
- Unicorn tests for the DSP hooks

## Granular Parameters

- TUNE: Pitch of each grain
- PLAY: Granular playhead's playback direction
- BR: Bit reduction
- SAMP: Sample selection
- DENS: Grain spawn rate. 0 Hz at noon, counter-clockwise for periodic rates,
  clockwise for random.
- SHAPE: Grain shape. Sinusoidal window at noon, counter-clockwise for gate,
  clockwise for a quick decay.
- RAND: Level of tune, shape, and position randomization between grains
- LEV: Source level
