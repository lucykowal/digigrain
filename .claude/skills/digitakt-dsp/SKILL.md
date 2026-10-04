---
name: digitakt-dsp
description: Writing audio DSP for Digitakt mods: freestanding fixed-point C, ColdFire EMAC, ISR budget, and a granular engine design (DaisySP findings). Use when implementing grains, filters or anything in the render path.
---

# DSP on the Digitakt mk1

## Constraints
- ColdFire V4e, **no FPU use, no libc/libm/libgcc**: no `sinf`/`powf`/`malloc`/`printf`; 64-bit math and division are hand-written (`../digi1_mods/mods/digieq/eq.c` `udivq16`).
- Block = 32 stereo frames, 48 kHz, 0.67 ms, 1500 blocks/s. Master block `0x8000ea70` is int32 `{L,R}`, 8 bits above the 24-bit codec words (output stage shifts by 8; `asr 6` folds the x4 working range).
- RAM 128 KB shared, `.fast` 2304 B (see `digitakt-mod-json`).
- Cost references: master EQ ~2,800 instr/active band/block (4 bands ~8,800); digimatrix idle ~350; digipoly router ~180 per note.

## EMAC
`mac.l`, `movclr.l`, MACSR 0x20 = signed fractional, truncating, no saturation. Save/restore MACSR/ACC0/ACCEXT01 and clear ACC0 first. Python models must mirror it exactly (each product `floor(x*y/2^23)` keeping 8 bits below LSB, sum truncated) to get bit-exact tests (`../digi1_mods/tests/eq_model.py`, `emu_eq.py`).

## Table generation
Generate tables at build time with Python (`../digi1_mods/tools/gen_eq_tables.py`, `gen_spec_tables.py`); never compute `sin`/`exp` on device.

## Granular design (DaisySP findings)
DaisySP (`../DaisySP`, MIT) has only `GranularPlayer`: a 2-grain, 50%-overlap time-stretch player, float, libm, nearest-neighbour reads, with an OOB index-wrap bug and double phasor advance. **Do not port; write fresh.** Reuse only the ideas (half-sine window, sawtooth phasor grain restart). MIT notices must be kept if any code is copied; algorithm ideas need none; our mod is GPL-2.0-or-later.

Implemented engine (`mods/digigrain/src/grain.c`, API in `mods/digigrain/src/grain.h`):
- Source: s16 PCM from `OS_SMP_TAB[slot]` (`digitakt-firmware-map`); per grain a Q16 fraction + integer frame index, linear interpolation, forward only.
- Window: 256-entry tables generated at build time (`mods/digigrain/tools/gen_tables.py`): half-sine blended with gate or quick decay by ENV, built once per voice into a live Q16 table whenever the shape changes (`build_win`); Q24 window phase.
- Pitch: shadow-voice speed times an integer-semitone ratio table (`gr_ratio`, +-12) for SPRD-tune.
- Scheduler: periodic or uniform-random intervals, xorshift32 (no libc); #19-safe: `next_in` is capped to one interval (two in random mode) each block.
- **Cost model:** grain length in output frames = clamp(interval x RTIO >> 8, 16, 65535), *independent of pitch*; periodic overlap = ceil(RTIO) <= 8, the pool is 8 grains per voice, and a full pool skips the new grain. A longer grain from low pitch no longer exists (the old fixed-2400-source-frame grains grew to 4-10x at TUNE -12..-24 and froze the UI on hardware, issue #18). Worst case per voice: 8 grains x 32 frames x ~26 instructions (interpolating loop) ~ 8k per block; the integer-step loop (unity speed) is half that.

## Process
Write C reference (host-compiled) + Python fixed-point model first, assert bit-exactness against the on-target code in Unicorn (`digitakt-testing`), then integrate.

## ColdFire C optimisation notes (from tuning the grain loops, measured)
- Workflow: write the C reference and a Python model first (bit-exact), then optimise only with the model's tests green
  (`mods/digigrain/tests/test_grain.py`, including the random edge fuzz). Count instructions with `mods/digigrain/tests/emu/grain_bench.py`
  (compiles `mods/digigrain/src/grain.c` with the cross gcc and runs `gr_block` in the patched Unicorn: seconds) and confirm in the
  firmware with `mods/digigrain/tests/emu/bench.sh`. Look at the generated code: `m68k-elf-gcc -mcpu=54455 -O2 -ffreestanding
  -fno-builtin -nostdlib -fno-pic -fno-pie -fomit-frame-pointer -I mods/digigrain/src -S mods/digigrain/src/grain.c -o x.s`.
- `asr/lsr #imm` only goes up to 8 on ColdFire: a shift by 14 or 15 costs `moveq` + register shift (2 insns). A shift by 16 is
  `swap` (+ `ext.l`). Make products land on a 16-bit boundary: store tables as `2 x Q15` unsigned Q16 so
  `(s * w16) >> 16 == (s * w15) >> 15` exactly (no overflow: 32768 x 65534 < 2^31).
- 32-bit `muls.l` and hardware divide (`remu.l`) are available with `-mcpu=54455`; no libgcc is linked, so avoid 64-bit math.
- Prove bounds once per block and run a check-free loop with state in locals; keep the exact checked loop as the fallback
  near ends. Mark hot loops `noinline` so each gets its own registers (an inlined merged loop kept a branch inside and spilled
  to the stack, ~45 instr/sample). `do { } while (--n)` (n >= 1) saves the `moveq/cmp` count test.
- Specialise on loop-invariant cases: unity-speed grains (integer step, fraction 0) skip interpolation (13 vs ~26 instr/sample);
  a per-voice cached window table replaces per-sample shape blending.
- Costs measured: grain-sample 13 (integer step) to ~26 (interpolated) instructions; per-block overhead ~300 (clear/clamp loops).
- Instructions are not cycles: confirm margins with `emu.fwcheck` (timing mode) under load.
