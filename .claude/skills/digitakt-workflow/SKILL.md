---
name: digitakt-workflow
description: Build, lint, patch and flash a Digitakt mk1 (OS 1.53) mod with elekloader; toolchain, repo scripts, recovery. Use when setting up, building or shipping a mod.
---

# Digitakt mod workflow (elekloader, mk1 OS 1.53)

Only Digitakt mk1 OS 1.53 supports linkable (format 2) mods. Sibling checkouts used here: `../elekloader`, `../Digitakt_OS1.53.syx` (never commit it).

## Repo commands (this repo)
```
make build   # core (once, out/core) + every mod -> out/<mod>/
make lint    # boundary check (mods -> common only), then each mod alone and with core and the stock OS
make patch   # out/<mod>/test.syx = stock + core + that mod (--version 0.0t)
make test    # stdlib unit tests: tests/, common/tests/, mods/<mod>/tests/
make check   # all of the above
make check MOD=digigrain          # any target for one mod only
make new-mod NAME=my-mod          # scaffold mods/my-mod from templates/mod
```
Layout: one mod per `mods/<name>/` (`mod.json`, `src/`, `tests/`, optional `tools/`); shared code in `common/` (`include/`, `src/`). `scripts/build.sh` stages `out/<mod>/stage` = the mod's `mod.json` + `src/` + a `common` symlink, because the SDK builds one directory: list shared sources in `sources` as `common/src/x.c` and include headers as `"common/include/x.h"`. Never depend on another mod (`tools/check_boundaries.py`, run by lint, fails on it). `.o` names come from basenames, so keep source file names unique across a mod and the common files it uses. Scripts live in `scripts/`; `scripts/env.sh` sets `PYTHONPATH`, `ELEKLOADER_STOCK`, and `ELEKLOADER_CROSS=m68k-elf-` when only Homebrew's `m68k-elf-*` tools exist.

## Raw loop (what the scripts run)
```
python -m elekloader.sdk.build <moddir> --stock <stock.syx> [--out DIR]   # prints BUILT <path>
python -m elekloader.lint <mod.elemod> --stock <stock.syx> --with <core.elemod> [--json]
python -m elekloader.patch --stock <stock.syx> --mod <core.elemod> --mod <mod.elemod> --out test.syx --version XXXX [--check]
```
- Core builds from `../elekloader/mods/core` (now 2.1, `core-2.1.elemod`; 2.1 adds SRC machine slots). If `out/core` holds an older core, delete it and rebuild. Every format-2 set needs exactly one core.
- `--version` is exactly 4 ASCII chars; use a distinct tag per flash so you can confirm which build is on the unit.
- Lint with `--stock` but without `--with core` fails "X requires core".
- Bump the mod `version` on every change.

## Toolchain
- `brew install m68k-elf-gcc m68k-elf-binutils`. SDK default prefix is `m68k-linux-gnu-`; override with `ELEKLOADER_CROSS`. Flags: `-mcpu=54455 -O2 -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-pie -fomit-frame-pointer -Wall`.
- Disassemble stock with `m68k-*-objdump -D -b binary -m 5407 --adjust-vma=0x40000400 section_3_MAIN_OS.bin`. **`-m 5407` is essential**; `-m 68000` silently emits wrong `.short` garbage for ColdFire insns.
- No libc, no libgcc, no FPU: 64-bit math and division must be hand-written.
- `.envrc` is user-local and untracked (see project memory).

## Rules (loader enforces; see `digitakt-mod-json` for fields)
1. Only the main OS changes; bootloader stays stock.
2. Ship no firmware bytes: call firmware by address; 8+ byte runs equal to stock become references.
3. Code sites cover whole instructions (ColdFire insns are at most 6 bytes).
4. Don't patch core's shared sites; subscribe to events (`digitakt-hook-bus`).
5. One owner per byte. 6. Let the linker place code/data. 7. Only 32-bit abs / 32/16-bit PC-relative relocs.
8. One global namespace: prefix globals with the mod id, make internals `static`.
9. Claim resources in `resources.names`/`regions`. 10. Inside another mod's copied block use absolute addressing.
11. `requires: ["core"]`, `conflicts` as needed. 12. One mod file targets one OS release.

## Refusals -> fix
| message | fix |
|---|---|
| `stock bytes are X, not Y` | wrong address/OS; re-read bytes at the address |
| `ends mid-instruction` / `sweeps land on the start` | align site to instruction boundaries |
| `... overlap (0x..)` | another mod/core owns those bytes; subscribe instead |
| `X requires Y` | add `--with Y.elemod` |
| `imports N, which no given mod exports` | add exporter, fix typo, or list under `weak` |
| `both export S` / `both claim N` | prefix globals / pick another resource name |
| `relocation type N` | use 32-bit addressing for own symbols |
| `section X is not one elekloader places` | only `.run/.fast/.bss` (asm: `.section .run,"ax"`) |
| `the mods need RAM to ...` / `.fast code needs SRAM` | shrink buffers; `.fast` needs the fast-audio mod |
| `PC-relative, inside ...'s copied block` | use absolute `jmp`/`jsr` |
| `region ... is outside every free area` | regions must lie in ddr / sram-tail / sram-block |

## Definition of done
`BUILT`, lint exits 0 (with `--with` for every mod users may combine), patch prints `WROTE`, `mod.json` has description/category/license/requires and every resource name, no firmware committed, and you tested in an emulator or on a device you can recover. A verified build only proves a well-formed file, not working code.

## Flash and recovery
- Flash: Elektron Transfer > select unit > drop `.syx` > YES on the unit; don't power off mid-upgrade. Back up projects/sounds/samples first; flash one build at a time.
- Recovery: bootloader is never touched. Hold FUNC at power-on for the startup menu, TRIG 4 = OS UPGRADE, send the stock `.syx`. digi1_mods' INSTALL.md says USB doesn't work in that menu, so keep a physical MIDI interface and send the official OS over MIDI (safest route; digislicer's README says Transfer legacy upgrade, so sources disagree).
- A kit saved with an unknown machine loads that track as ONESHOT on stock firmware.
