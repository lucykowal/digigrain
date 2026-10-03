---
name: digitakt-testing
description: Testing Digitakt mods without hardware: raw Unicorn hook tests, digiemu full-firmware scenarios (external), bit-exact DSP models, and what is/isn't available locally. Use when writing tests or deciding how to verify a hook.
---

# Testing Digitakt mods

## Availability (checked)
- **digiemu is NOT in any local repo** (it is the separate "digikit" emulator; needs its own patched Unicorn venv). `elektron-firmware-tool` is only a container/SysEx/aPLib tool; it has no emulator. Ask the user where digiemu lives before relying on it; don't search the filesystem for it.
- Raw Unicorn tests need `pip install unicorn pillow` (`requirements-dev.txt`) plus m68k binutils; EMAC-using code needs digiemu's patched Unicorn.

## Layer 1: raw Unicorn hook tests (seconds)
Reference: `../digi1_mods/tests/emu_poly.py`, `emu_eq.py`, `emu_matrix.py`. Skeleton:
- `from elekloader import syx, devices, elemod, link`; `st=syx.Syx.load(stock)`; `L=link.link([elemod.load_any(p) for p in mods], st.section(dev.main_section))`; use `L.map` (symbol->address), `L.image`, `L.layout["ddr"|"bss"|"run_load"]`.
- `uc=Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)`; `uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)`; map 0x40000000, 0x41900000, 0x421f0000, 0x43900000, 0x47b00000, 0x80000000; write the image at 0x40000400, the run image at ddr, zeros for bss.
- Stub firmware calls by writing `rts` (0x4e75) at their addresses (invalidate 0x400c9812, fillrect 0x400c19a6, text 0x400c257c, blit 0x400c2960, MSG_ALLOC 0x400ee036, MSG_COPY 0x400ee0a0, 0x400d53dc, 0x400d575e, 0x40076b3c); allocators need a few assembled instructions (`as -mcpu=54455`). Record calls with `UC_HOOK_CODE` reading args at `sp+4...`.
- `call(fn,*args)`: push big-endian args below a sentinel return pointing at `nop nop`, `emu_start(MAP[fn], SENT, count=5_000_000)`, read d0.
- Build fake kits/patterns/engine state with `w32/r32`; assert outputs and recorded calls. Check all registers/EMAC are preserved; use a register-junking stub to catch missing saves; do mutation checks (inject bugs, confirm tests fail).
- Old stand-alone suite: `tests/run_tests.sh <official section_3.bin> <patched section_3.bin>`.

## Layer 2: bit-exact DSP
Python model of the fixed-point algorithm (`eq_model.py` style) compared sample-for-sample with on-target code run in Unicorn. Count instructions per block for ISR budget.

## Layer 3: digiemu full-firmware (if available)
Reference driver `../digi1_mods/tests/digiemu_scenario.py`:
```
python3 tests/digiemu_scenario.py --digiemu <checkout> --fw <firmware folder> --stock <official.syx> \
  --elekloader <elekloader checkout> --mods <core> <mod...> --png <outdir>
```
- Register a build first: `python -m emu.portable --add BUILD.syx --yes`. Env: `PLAN=tour|song|eq`, `INJECT=<Hz>` (sine into render out; the cold-boot card has no samples), `DT2_*`.
- A PLAN is `(step, action)`; actions `("press"|"release", keycode, 0)`, `("encoder", code, delta)`; ~1 ms/step; chords press(FUNC), press(key), release(key), release(FUNC) with ~20-step gaps. Framebuffer `E.fb[y*128+x]` -> PNG. `UC_HOOK_CODE` at e.g. VOICE_START 0x40077a76 to observe playback. Boot ~30 s from a snapshot. Encoder deltas ±4/±8 used.
- Key codes (inferred): see `digitakt-hook-bus`; knob k = `ENC_A + k`.
- Caveat: no cold-boot samples, so verifying sample playback needs injected data or a prepared snapshot/+Drive image.

## Hardware
Only after emulator passes. Distinct 4-char `--version` per build, flash one at a time, know recovery (`digitakt-workflow`). Unverified-on-hardware items are listed in `../digi1_mods/RISKS.md`.
