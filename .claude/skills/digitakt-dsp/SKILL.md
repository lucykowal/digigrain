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

Proposed engine:
- Source: s16 PCM from `OS_SMP_TAB[slot]` (`digitakt-firmware-map`).
- Q32 phase accumulators (wrap free); read position Q16.16; linear interpolation (2 reads + 1 MAC).
- Window: Q15 half-sine/Hann table (256-512 entries) generated at build time, optional linear interp.
- Pitch: semitone x fine-cents ratio tables, resolved once per block; reciprocal tables instead of division.
- Grain pool: per grain `{pos Q16.16, inc, age, len, gain, pan}` ~16-24 B; 16-32 grains ~0.5-1 KB.
- Scheduler: density counter/phasor per block, jitter from xorshift32/LCG (no libc); start position, size, pitch, pan per grain; free-grain search; mix into the 32-frame stereo block.
- Estimated 8-16 grains x 32 frames ~512 grain-samples/block; feasibility is **unmeasured**: profile in the emulator (instruction counts via `UC_HOOK_CODE`) before committing to a grain count.
- Map the 8 SRC knobs: position, size, density, pitch, jitter, spread, shape, level (design TBD).

## Process
Write C reference (host-compiled) + Python fixed-point model first, assert bit-exactness against the on-target code in Unicorn (`digitakt-testing`), then integrate.
