# lucy's mod

Custom firmware mods for the Elektron Digitakt (mk1, OS 1.53), built with
[elekloader](../elekloader).

A granular playback SRC machine (id 6, GRANULAR). The engine runs in the
emulator on the real firmware; the SRC page labels and ranges, polyphonic cost
and hardware testing are still open (see `.claude/skills/digitakt-machines`).

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

- Custom value readouts (Hz, offset from noon) for DENS / SHAPE / RAND
- Optimise the grain loop (about 65 instructions per grain-sample today)
- Hardware testing; Poisson random intervals

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

### Implementation notes

- TUNE sets the playback speed through the stock voice; grains read a fixed
  50 ms of source (at 1x), so speed changes pitch and grain length together.
- The position knob (C) is the stock STRT parameter, so it is labelled STRT
  (0 to 120) rather than BR; PLAY picks the grain direction (the `.L` modes
  also keep the voice sustaining).
- DENS: periodic grains at 0.25 to 120 Hz counter-clockwise of noon, random
  intervals (same mean rates) clockwise. RAND randomizes pitch (up to +-12
  semitones), shape and position per grain.
- The SRC page reads `TUNE PLAY STRT SAMP / DENS SHAPE RAND LEV` (page layout
  hook plus three new parameter descriptors); DENS, SHAPE and RAND show raw
  0 to 127 values with noon at 64. A new GRANULAR track starts with FWD.L,
  DENS 36 and a sine SHAPE.
