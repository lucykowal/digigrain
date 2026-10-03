---
name: digitakt-testing
description: Testing Digitakt mods without hardware: raw Unicorn hook tests, digiemu full-firmware scenarios (external), bit-exact DSP models, and what is/isn't available locally. Use when writing tests or deciding how to verify a hook.
---

# Testing Digitakt mods

## Availability
- **digiemu** = `../digiemumac` (github.com/orwell68/digiemumac, a fork of irpina/digiemu). Runs the real 1.53 OS in a patched Unicorn on macOS. Set up (done): `uv sync --python-preference only-managed --python 3.12` (managed Python has Tk; Homebrew's python lacks `_tkinter`), then `tools/install-patched-unicorn.sh` (rerun after every `uv sync`/venv rebuild), then `uv run python -m emu.portable --add ../Digitakt_OS1.53.syx --yes` (~25 s; data in `portable/firmware/dt1-1.53-9bdd44bb/`, derived from firmware: never commit). GUI: `uv run python -m emu.portable` (needs a display).
- **Build check** for our patched firmware: `uv run python -m emu.fwcheck out/test.syx (from this repo, via ../digiemumac) --baseline ../Digitakt_OS1.53.syx --out <dir>` (~8-12 min; `--no-timing` ~3x faster, skips the render-margin measurement). Reports prepare/bootloader/boot/run, audio render margin, screen diffs and audio identity vs stock. The stock build itself "fails" boot on a FlexBus read at 0x0 in this copy (emulator quirk, ignore).
- **Probe harness (this repo):** `tests/emu/make_probe_home.sh` builds a throwaway digiemu home (`out/emu/home`) with a known sine in `/incoming`; `FW_DIR=out/emu/home/firmware/<name> uv run --project ../digiemumac python tests/emu/scale_probe.py` drives the real firmware headless (key plan: SRC, knob D = slot list, YES = browser, DOWN, YES into incoming, DOWN, YES to load, trig key 24), hooks `UC_HOOK_CODE` after the voice-synth calls and prints voice blocks. Pattern for new scenarios: patch `G.spin`, count steps (~5 ms emulated each), push `('press'|'release'|'encoder', code, delta)` onto `E.inbox`, save PNGs with `SHOTS=dir`. The factory snapshot has NO sample data in RAM (slot 37's table entry is the empty default); load samples via `emu.samples` + `--rebuild`.
- **Testing our own build:** `SYX=out/test.syx tests/emu/make_probe_home.sh` registers it as a firmware in `out/emu/home` (it gets its own `devices/digitakt.toml`; `scale_probe.py` uses it, so the emulator accepts the unknown version 0.0t) and puts the sine on its card; then `GRANULAR=1 FW_DIR=out/emu/home/firmware/dt1-0.0t-<sha8> uv run --project ../digiemumac python tests/emu/scale_probe.py` switches track 1 to GRANULAR (FUNC+SRC, DOWN x4 with >=80 steps between taps, YES), trigs it, and prints block levels and audio. Key taps closer than ~40 steps are dropped. Symbol addresses of the build come from elekloader's linker (`link.link([core, mod], stock.section(3)).map`). Rebuild the home after every new build (new hash = new folder).
- **Probe env knobs** (`tests/emu/scale_probe.py`; set before the run, steps are ~5 ms):
  - `POKE="slot:value,..."` writes track 1's param words into the voice's engine copy AND the kit sound block; value = 0..127 knob value (written <<8) or `0xHHHH` for a raw word. GRANULAR slots: 17 TUNE (centre 16384), 18 ENV, 19 RATE, 21 POS (0..120), 22 RTIO (raw 8.8, e.g. `22:0x0800` = 8:1), 23 SPRD, 24 LEV (ENV/RATE/SPRD: noon 64). `POKE_FROM=n` first step to poke (default 1000; use ~2200 to start after the machine switch and its defaults). `SWEEP="slot:value@step,..."` one-shot writes at given steps (same value forms).
  - `TURNS="knob:delta:count,..."` (knob 1-8 = A-H) turns encoders after the machine is selected (single events with delta 16 are ignored; use delta +-4 repeated). `MACHINE_DOWNS=n` DOWN presses in the machine list (default 4 = GRANULAR, 3 = SLICE, 0 = stay on ONESHOT). `SHOTS=dir SHOT_STEPS=a,b` saves screenshots.
  - Output: `DUMP=n` per-block (step, V+4, peak); `GAPS=1` (`GAPS_FROM`) longest silent stretch of voice 0; `LIFE=1` blocks with signal, `on` flag, V+4 loop wraps and the grain-rate histogram; `ZCSTAT=1` rising zero crossings per 50 ms of the audio (440 Hz = 22); `TRACE_GR=1` the `gr_block` params of the first calls; `MEASURE=1` instructions per `digigrain_granular_render` call (steps 2400-2440); `MEMDUMP="addr:len"` (`MEMDUMP_STEP`) hex dump.
  - Firmware spelunking: `SITE_COUNTS="addr,addr"` (hex, no 0x) counts executions of those addresses in the phases of a preset plan (page view, knob E turns, knob C turns); `ARG_TRACE="addr,..."` logs (entry, arg1 high half, arg1's vtable, arg2) at function entries; `REGS="addr:A3,..."` prints a register at an address; `MEMAT="addr:A6:54:2"` prints memory at reg+offset (`MEMAT_FROM`); `WATCH="addr,..."` logs the pcs that read those bytes.
  - The stock ONESHOT and SLICE pages are unchanged by the mod (STRT/BR/LEN/LOOP, SLICE/LEN/GRID and their titles); check them with `MACHINE_DOWNS=0` / `3`.
- **Performance:** `uv run --project ../digiemumac python tests/emu/grain_bench.py` compiles `mod/grain.c` for the ColdFire and counts instructions per `gr_block` in the patched Unicorn (seconds; no firmware needed). `tests/emu/bench.sh [folder]` measures `digigrain_granular_render` inside the real firmware for eight settings (~2 min each). Instruction counts, not cycles: the ColdFire V4e issues roughly 1 per cycle but multiplies and memory ops cost more.
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

## Gotchas (all hit during development)
- A digiemu "step" is ~5 ms of emulated time (about 7 render blocks); the emulator runs ~2x real time headless.
- The factory snapshot opens on track A01 "SUBAQUATIC" with sample slot 37 EMPTY in RAM (the table entry is the 248-frame
  default): load a WAV via `emu.samples` + `--rebuild`, then pick it in the sample browser (`make_probe_home.sh` does the first part).
- Key taps closer than ~40 steps are dropped; knob events need small deltas (+-4) spaced >= 6 steps; a single delta of 16 is ignored.
  Codes: 1 FUNC, 12 YES, 13 NO, 15 DOWN, 20 SRC, 24 trig 1; encoders 1..8 = A..H. Machine list: FUNC+SRC, DOWN x4 (GRANULAR is the 5th row).
- Every new build is a new firmware folder (hash in the name); rebuild the probe home after each build. Custom builds
  need their own `devices/digitakt.toml` (copied automatically); the emulator cannot identify an unknown `.syx` otherwise.
- `uv sync` (or deleting `.venv`) restores the stock Unicorn wheel: rerun `tools/install-patched-unicorn.sh`.
  Homebrew's Python lacks `_tkinter`: use `uv sync --python-preference only-managed --python 3.12` for the GUI.
- On a trig the voice reloads its params from the kit for the first blocks: poke both the engine copy (`0x80001502 + 106*v`) and
  the kit sound (`kit + 0x20 + 0x14 + 2*slot`, kit ptr at `0x800019ac`).
- `emu.fwcheck`: ~8-12 min with timing (`--no-timing` ~3x faster, no render margin); its stock "reference" run reports a boot FAIL
  (FlexBus read at 0x0) in this copy: an emulator quirk, ignore it; it never switches a track to GRANULAR.
- Run long emulator jobs in the background and poll; never search outside the repos you were told about.
