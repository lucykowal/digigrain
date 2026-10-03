---
name: digitakt-testing
description: Testing Digitakt mods without hardware: raw Unicorn hook tests, digiemu full-firmware scenarios (external), bit-exact DSP models, and what is/isn't available locally. Use when writing tests or deciding how to verify a hook.
---

# Testing Digitakt mods

## Availability
- **digiemu** = `../digiemumac` (github.com/orwell68/digiemumac, a fork of irpina/digiemu). Runs the real 1.53 OS in a patched Unicorn on macOS. Set up (done): `uv sync --python-preference only-managed --python 3.12` (managed Python has Tk; Homebrew's python lacks `_tkinter`), then `tools/install-patched-unicorn.sh` (rerun after every `uv sync`/venv rebuild), then `uv run python -m emu.portable --add ../Digitakt_OS1.53.syx --yes` (~25 s; data in `portable/firmware/dt1-1.53-9bdd44bb/`, derived from firmware: never commit). GUI: `uv run python -m emu.portable` (needs a display).
- **Build check** for our patched firmware: `uv run python -m emu.fwcheck ../lucys-mod/out/test.syx --baseline ../Digitakt_OS1.53.syx --out <dir>` (~8-12 min; `--no-timing` ~3x faster, skips the render-margin measurement). Reports prepare/bootloader/boot/run, audio render margin, screen diffs and audio identity vs stock. The stock build itself "fails" boot on a FlexBus read at 0x0 in this copy (emulator quirk, ignore).
- **Probe harness (this repo):** `tests/emu/make_probe_home.sh` builds a throwaway digiemu home (`out/emu/home`) with a known sine in `/incoming`; `FW_DIR=out/emu/home/firmware/<name> uv run --project ../digiemumac python tests/emu/scale_probe.py` drives the real firmware headless (key plan: SRC, knob D = slot list, YES = browser, DOWN, YES into incoming, DOWN, YES to load, trig key 24), hooks `UC_HOOK_CODE` after the voice-synth calls and prints voice blocks. Pattern for new scenarios: patch `G.spin`, count steps (~5 ms emulated each), push `('press'|'release'|'encoder', code, delta)` onto `E.inbox`, save PNGs with `SHOTS=dir`. The factory snapshot has NO sample data in RAM (slot 37's table entry is the empty default); load samples via `emu.samples` + `--rebuild`.
- **Testing our own build:** `SYX=out/test.syx tests/emu/make_probe_home.sh` registers it as a firmware in `out/emu/home` (it gets its own `devices/digitakt.toml`; `scale_probe.py` uses it, so the emulator accepts the unknown version 0.0t) and puts the sine on its card; then `GRANULAR=1 FW_DIR=out/emu/home/firmware/dt1-0.0t-<sha8> uv run --project ../digiemumac python tests/emu/scale_probe.py` switches track 1 to GRANULAR (FUNC+SRC, DOWN x4 with >=80 steps between taps, YES), trigs it, and prints block levels and audio. Key taps closer than ~40 steps are dropped. Symbol addresses of the build come from elekloader's linker (`link.link([core, mod], stock.section(3)).map`). Rebuild the home after every new build (new hash = new folder).
- **Probe env knobs** (`tests/emu/scale_probe.py`): `POKE="slot:value,..."` writes SRC/page param words (value<<8) of track 1 into the voice's engine copy AND the kit sound block (slots: 17 TUNE, 18 PLAY, 19 BR/C, 20 SAMP, 21 E, 22 F, 23 G, 24 LEV); `DUMP=n` prints per-block (step, V+4, peak); `TRACE_GR=1` prints the `gr_block` params of the first calls; `MEASURE=1` counts instructions per `lucys_granular_render` call (steps 2400-2440); `SHOTS=dir SHOT_STEPS=a,b` saves screenshots; `TURNS="knob:delta:count,..."` (knob 1-8 = A-H) turns encoders after the machine is selected (single events with delta 16 are ignored; use delta +-4 repeated); `MEMDUMP="addr:len"` (`MEMDUMP_STEP`) dumps memory.
- Headless tools in digiemumac: `tools/dtdrive.py` (press keys, capture), `tools/livecheck.py` (live audio via stub card), `tools/ekfsadd.py` (WAVs onto the +Drive), `emu.checkpoint`; see `DIGITAKT-MK1.md`.
- Ghidra: use language `68000:BE:32:ColdfireEMAC` (decodes EMAC/`movclr`; the stock ColdFire language stops there and the decompiler fails).
- `elektron-firmware-tool` is only a container/SysEx/aPLib tool; no emulator.
- Raw Unicorn tests need `pip install unicorn pillow` (`requirements-dev.txt`); EMAC code needs the patched Unicorn.

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
