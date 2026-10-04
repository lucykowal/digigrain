---
name: digitakt-recorder
description: Digitakt mk1 OS 1.53 sampler/recorder internals - the 33 s record buffer (split s16 + low-byte planes), record state machine and addresses, source selector (IN/MAIN/USB/TRK1-8), sample-table setter 0x400763b4, reserved slot 0x82 preview, save/trim UI, and recipes for mods (play the record buffer from an SRC machine, sample editing, resampling a track). Use when a mod touches recording, the record buffer, or sample slots.
---

# Digitakt recorder and the record buffer (OS 1.53)

Source: static analysis (objdump `-m 5407`, Ghidra decompile of the non-EMAC UI/glue code). **Nothing here has been run in digiemu yet**;
the "Verify" list at the end is the first work to do. Companion skills: `digitakt-audio-input`, `digitakt-firmware-map`,
`digitakt-machines`, `digitakt-reverse-engineering`.

## The record buffer
- **Capacity 1,584,000 frames = 33.0 s at 48 kHz mono** (`0x182B80`; also the cap constant at 0x40076616/0x40076898).
- Two planes in SDRAM, written together per frame at frame index `n` (= `0x4199e104` when recording):
  - **s16 plane `0x4237DF90 + 2n`** = the top 16 bits of the 24-bit sample. This is a plain **s16 mono 48 kHz** buffer
    (3,168,000 B, ends at 0x42643B10).
  - low-byte plane `0x421FB410 + n` = bits 8-15 of the 24-bit sample (`0x4237DF90 - 0x421FB410 = 0x182B80`, i.e. directly below).
  - Per-block store (0x40076860-0x4007686a): `d4 = word >> 8` (24-bit), `moveb d4 -> bytes`, `d4 >>= 8`, `movew d4 -> words`.
- Reassembled 24-bit read (0x400769d6-0x400769dc): `(s16 << 8 | byte) << 8` = Q31.
- The planes are not cleared on record start (only frames 0..143 are zeroed by `0x40076a04`); stale data is overwritten as it records.
  After recording stops the data stays until the next record, so a mod can read it after the RECORDER view closes (verify).

## Capture block and source selector
- Per audio block, after the output stage, the render task calls `0x40076650(inRX, mainBus, usbBus, trackBlocks)` at **0x400782cc**
  (args: `rxhalf` shifted Q31, `0x80001f60 + 256*(0x4199e134&1)`, return of `0x40071c20`, `0x80001a18`).
- It switches on **`0x4197bf98`** (the SRC setting, jump table at 0x40076680) and fills the **mono capture block `0x800032c4`**
  (32 x Q31): sources `0 IN L, 1 IN R, 2 IN L+R` (arg1), `3 MAIN L, 4 MAIN R, 5 MAIN L+R` (arg2), `6 USB L, 7 USB R, 8 USB L+R` (arg3),
  **`9..16 TRK1..TRK8` = a straight 128-byte copy of voice block `0x80001a18 + 128*(sel-9)`** (memcpy `0x400e88c0`); `>16` -> zeros
  (`0x400e8908`). Names: table at 0x40202454 (`IN L`, `IN R`, `IN L+R`, `MAIN L`..., `USB L`..., `TRK1`..).
  Stereo selectors call `0x40076560(ptr, gL, gR)`: `mono = gL*L + gR*R` with `MACSR=0xa0` fractional; gains are `-1.0` (0x80000000)
  for a single channel, `0xA57DBF49` (about -0.707) for L+R.
- TRK1..8 copy the voice blocks as they are when this runs, i.e. after the synth and the in-place stages 0x40072478/0x4007266e, before the master mix
  (inferred from call order; verify). A machine that writes the voice block is therefore recordable for free (resample a track).

## State machine (`0x4199e114`), accessors and call sites
| state | meaning | notes |
|---|---|---|
| 0 | idle, no data | |
| 1 | armed, waiting for threshold | `0x400768a0` (YES: ARM) from state 0/4. Block loop at 0x400767b6 compares the block against the THR level (`(0x4197bf9c-128)<<24 * 0x11000000`) |
| 2 | recording | `0x400768ce` (Fn+YES: REC now) from 0/1/4; clears len `0x4199e104`, sets limit `0x4199e100 = 0x40076616()` |
| 3 | normalizing | `0x40076540` sets 3 and posts a message; task runs `0x40076a04` (called 0x4000b172): zeroes frames <144, scans min/max with `0x4007699e(start,end,&min,&max)`, scales with soft-float helpers `0x40124014/0x40123dac` and writes both planes back, then state 4 (or 0 if silent) |
| 4 | done, editing | UI draws waveform (0x400a8a6c), TRIM STRT/END, `Y: SAVE`, `Fn+Y: PREVIEW`, `Fn+N: DISCARD` |
- Stop `0x40076918` (state 2 -> finish), discard `0x4007693c` (states 1,2,4 -> state 0, len 0).
- Read-only getters: `0x400765d0` len, `0x400765d8` state, `0x40076b02(&state,&len)` atomic pair (what the UI uses), `0x40076996`/`0x4007698e`
  peak max/min (Q31), `0x40076898` capacity, `0x40076616` current limit (see below), `0x400765e0(steps_index)` sets `0x4199e0fc = 1<<idx` (length in steps, 0 = free).
- Length limit `0x40076616`: if `0x4199e0fc > 0` it is `5760000 * steps / (4 * tempo_unit(0x400770c8))` frames (sequencer-synced), else the 1,584,000 cap.
- Write position `0x4199e104`, limit `0x4199e100`, peak state `0x4199e108/e10c/e110` (updated per block with `macl` envelope followers).
- UI class `SamplerView` (vtable 0x401b32c8): consumeKey `0x400a955c`, draw `0x400a8a6c`, tick `0x400a7940` (also posts the "Sampler Waveform Cache" job,
  waveform pixel cache at SamplerView+0x194/+0x38c, 126 columns), preview `0x400a73fa`, stop preview `0x400a7382`. Max length constant in tick: `0x182b80`.
  Settings getters `0x4001f09e/f0ce/f06e/f0fe` -> SRC / THR / steps / MON.

## Sample table, slots, and the preview slot
- **`0x400763b4(slot, pcm_ptr, length_bytes, rate)`** sets `OS_SMP_TAB[slot]` (`0x403193A0 + 16*slot`): `+0 = ptr`, `+8 = length_bytes >> 1` (samples), `+12 = ratio`
  (`FUN_40123dac` soft-float of `rate / 48000`, 0 -> 48000; packed Q30 high half etc., 48 kHz gives `0x40000000`), and `+4` = u16 from `rate`'s low half.
  For `slot < 0x80` it also builds the **255-entry slice table** `0x402F9380 + 0x400*slot` (cut points snapped to the nearest zero crossing by `0x400762ee`,
  one entry per 1/256 of the sample). Slots `0x80..0x82` skip that table. Valid slots are `0..0x82` (<0x83).
- `0x40074fd0(slot)` resets an entry to the empty defaults (ptr `0x40319BD0`, length `0xF8`, ratio `0x40000000`) and zeroes its slice table.
- **Slot 0x82 (130) is the recorder's audition slot.** `0x400a73fa(view, track, loop)` does:
  `0x40074fd0(0x82); 0x400763b4(0x82, (0x4237DF90 + (trimStart+viewOffset)*2) & ~0xF, (trimEnd-trimStart)*2, 48000)`, inits a scratch sound block `0x4208c768`
  with `0x40084ef6(0x4208c768,-1,0)`, sets its **SAMP word (`+0x3c`, `0x4208c7a4`) = `0x8200`** (slot 130 << 8), PLAY word (`0x4208c7a0`) = `0x200` (FWD.L) if loop, LEV `0x4208c7c8..cc`, then posts a live
  note with a 0x30-byte message `{track, note 0x3c, vel 0x7f, 1, 0x30080, -1, ..., +0x28 sound ptr = 0x4208c768}` through the live-note builder `0x40076b3c`.
  So **the stock voice engine already plays the raw record buffer, via a sample-table entry, with no file or pool allocation.** Note the 16-byte pointer mask:
  the audition start is rounded down to a multiple of 8 samples.
- Normal save path: `Y: SAVE` -> "Save recording" job (lambdas 0x400a78a6 / 0x400a8526 / 0x400a81b8 / 0x400a77f6) writes `/recorded/REC%04d` (max 2000 files, "REC DIR FULL"),
  16-bit or 24-bit file content from the two planes (not decoded; the writer is in the lambda chain), then the sample is loaded into the pool and assigned
  (strings "ASSIGN SAMPLE TO TRACK?", "SAMPLE POOL FULL"; free pool alloc `0x400eb782`).

## Recipes for mods
1. **Granular (or any) SRC machine playing the live record buffer** (the original goal): do not save. In the machine's sample lookup, treat a
   reserved selector (e.g. a SAMP value above 127, or one extra "REC" entry) as "use slot 0x82", and keep that slot pointed at the *current* recording
   region: at recording end (state transition 3 -> 4, or lazily when the machine starts) call `0x40074fd0(0x82)` + `0x400763b4(0x82, 0x4237DF90 + 2*start,
   2*len, 48000)`. A machine that reads s16 mono from `{ptr, len}` in the sample table needs no other change (digigrain already reads that table). While
   state is 1/2 (recording) the buffer grows: read `0x4199e104` for the live length and treat `[0, len)` as valid -> that gives **live granulation of what is being recorded** with zero extra copying.
   Remember the SRC param page SAMP range is 0..127<<8; slot 130 is only reachable by the engine (the audition proves `0x8200` is accepted in the word).
2. **Sample editing (crop, reverse, fade, normalize, gain, loop-point snap) on the record buffer:** operate on the two planes in place while state == 4
   (there is no re-entrancy guard besides the state), preserving the 24-bit pair (`(s16<<8|byte)`), then refresh the waveform cache (it is rebuilt from the plane in `0x400a7940`
   when `SamplerView+0x190` is behind the length; clear that field to force a redraw). Editing *pool* samples instead needs the pool pointer from `OS_SMP_TAB[slot]` (s16, in DDR) and
   a rebuild of the slice table via `0x400763b4(slot, same ptr, bytes, rate)` (this is also how to re-slice after an edit).
3. **Resample a track (incl. a granular track):** set `0x4197bf98` to `9 + track` (writer of the setting to be found; poke is enough in the emulator); the capture block
   already holds the track's post-synth block. A mod machine that writes `0x80001a18 + 128*v` therefore gets recorded without any change.
4. **Record live input with your own trigger:** call `0x400768ce` (state -> 2, length limit set from `0x4199e0fc`) from a hook, `0x40076918` to stop. Avoid doing so while in state 3.
5. **Extra record sources or a longer buffer:** the planes are statically sized and adjacent to other SDRAM data, so do not move them; to add a source, hook the `jsr 0x40076650`
   at 0x400782cc and post-fill `0x800032c4` (the switch result is only consumed by the loop after it).

## Verify before relying (open work)
1. Run the emulator through RECORD: confirm `0x4237DF90` layout and the 24-bit split with a known sine (digiemu needs RX input injection; if absent, poke the RX half).
2. Confirm that slot 0x82 survives leaving the RECORDER view and that a SRC voice with `SAMP=0x8200` plays it (poke the word in the voice param copy `0x80001502 + 106*v`).
3. Identify who writes `0x4197bf98/9c/a0` (settings -> audio mirror) so a mod can set the source.
4. Measure the capture-block scale for each source (`0x800032c4` after `0x40076650`).
5. Check whether the planes are in the cached region, and the cost of a granular read from DDR vs SRAM (see `digitakt-dsp`).
