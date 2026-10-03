# lucy's mod

Custom firmware mods for the Elektron Digitakt (mk1, OS 1.53), built with [elekloader](../elekloader).

Planned: a granular playback SRC machine. `mod/` is currently a scaffold that draws a marker.

## Prerequisites

- Python 3.9+ (`.python-version` pins 3.12.0)
- m68k binutils + gcc: `brew install m68k-elf-gcc m68k-elf-binutils` (scripts set `ELEKLOADER_CROSS=m68k-elf-` automatically)
- Sibling checkouts: `../elekloader` and the stock `../Digitakt_OS1.53.syx` (override with `ELEKLOADER_DIR`, `ELEKLOADER_STOCK`)
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

- `mod/` — the elekloader mod (`mod.json`, sources)
- `scripts/` — build/lint/patch/check wrappers
- `tests/` — smoke tests; `tests/emu/` reserved for Unicorn hook tests
- `.claude/skills/` — agent notes for mod development

## Flashing and recovery

Back up first. If a build misbehaves: hold FUNC while powering on for the startup menu, then send the stock `.syx`. Never commit firmware (`*.syx`, `*.bin`, `*.elemod` are ignored).

## Future work

- Machine registration and SRC page hooks for the granular engine
- Grain buffer within the shared RAM budget (128 KB) and `.fast` SRAM (2304 B)
- Unicorn tests for the DSP hooks
