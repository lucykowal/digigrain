---
name: digitakt-audio-input
description: Digitakt mk1 OS 1.53 external audio input path - codec RX ping-pong buffer, the two input channels in the 10-source mixer, input param blocks (volume/pan/delay/reverb/stereo link), the output stage, recorder monitoring, and where to hook to process live input (e.g. a live granulator). Use when a mod must read, replace or route IN L/IN R or the master/USB buses.
---

# Digitakt audio input, monitoring and mixing (OS 1.53)

Static analysis only (objdump `-m 5407` + Ghidra decompile), **not yet confirmed in digiemu** unless a line says "measured".
Companion skills: `digitakt-firmware-map` (render ISR order, voice blocks), `digitakt-recorder` (record buffer),
`digitakt-reverse-engineering` (method), `digitakt-hook-bus` (render_in/out hooks).

## Data path, codec -> mixer -> codec
1. **RX ring `0x80001000`, 0x200 B = two halves of 0x100 B** (32 frames x `{L,R}` int32 each). SSI DMA fills it; the render ISR
   `0x40077420` reads the DMA write pointer `0xFC045690` (`- 0x80001000 - 32`, +0x200 if negative -> `fp-84`) and uses
   `(fp-84 + 255-ish) & 0x100` to pick the half that is complete: `d2 = 0x80001000 + that` (code at 0x40078120-0x4007813a).
   TX ring is `0x4BA8F080` (+`fp-88 << 8`, `fp-88` = 0/1 from the TX DMA pointer `0xFC0456C0 == 0x4BA8F180`).
2. **Output stage `0x40071c20(txbuf, rxhalf, a2)`** (called at 0x4007814a with `a2` = the engine param base, `linkw -316`). It is
   not only a writer: it contains the whole master mix. Order inside it:
   - 0x40071c24-0x40071cee: read global mute/solo style words `0x80001a10..a16`, the **recorder-monitor flags**
     (`0x4197bfa0` MON on/off, `0x4197bf98` record source selector, `0x400765d8()` recorder state; see below).
   - Loop 0x40071cf0-0x40071f12 over **10 sources j = 0..9** building ramped Q31 gain tables (coefficient per output bus,
     delta `(new-old)>>5` per sample, so changes are smoothed over 32 frames): tables `0x4199ddd8` (main L), `0x4199de00` (main R),
     `0x4199de28`/`0x4199de50` (next bus pair, FX send), `0x4199de78`... each 10 longs (+0xa0/+0xc8 offsets inside the loop
     address the delay/reverb send rows).
   - 0x40071f16-0x40071f32: **`asll #8` of all 64 words of the RX half, in place.** The codec words are 24-bit sign-extended;
     after this they are full-scale Q31. (This is the "8 bits hotter" fact in `digitakt-firmware-map`.) The recorder reads
     the same half *after* this shift, which is why recordings are Q31 >> 8.
   - 0x40071f34-0x40071f52: `0x40071c0a(dst, src)` copies every other word (de-interleaves L, then R from `src+4`) into
     **`0x80001e18` (IN L block) and `0x80001e98` (IN R block)**, 32 x int32 each. These sit right after the 8 voice blocks
     (`0x80001a18 + 128*v`) so that the 10-source mixer `0x4007197e` treats inputs as sources 8 and 9.
   - Mix calls `0x4007197e(out, 0x80001a18, coeffs, ramp)` per bus: L `0x8000ea70` (coeffs 0x4199ddd8), R `0x8000ea74`
     (0x4199de00), then `0x40073654` (send FX), more mixes, `0x40071b30`, `0x40073c00`, `0x40073b7e`, `0x400735c6`.
   - 0x400721c6-0x40072220: final per-sample combine `out = c0*master(0x8000ea70) + c1*bufA + c2*bufB`, written `>>8` to the TX
     words (24-bit again), bufA at `0x80001f60 + 256*(0x4199e134 & 1)` (a ping-pong; `0x4199e134` flips every block at 0x40078352).
   - returns a pointer in d0 (kept in d4 by the caller; passed to the recorder as the "USB" source bus).
3. After it returns, the render task runs the recorder block function `0x40076650` (see `digitakt-recorder`), then USB audio
   shuffling (`0x80002160` 12-channel bus, `0x400033c6`).

**Ordering consequence (important for mods):** the 8 voice synth call `0x400757fe` (at 0x40077fa6) runs *before* the output
stage copies the RX half into `0x80001e18/e98`. So at the SRC-synth hook the input for this block is still only in the raw RX half
(unshifted 24-bit words), and `0x80001e18/e98` still hold the *previous* block's input. A live-input mod has two options:
- read the RX half directly (compute the half like the ISR does, shift `<<8` yourself, or just use the 24-bit values); or
- read `0x80001e18/e98` and accept one block (32 frames, 0.67 ms) extra latency.

## Input channels as mixer "tracks" 8 and 9
For sources j >= 8 the coefficient loop reads word arrays in the param base `a2` (stride 2 per source, `a5 = a2 + 2j`):
- `a5+936` volume, `a5+940` pan, `a5+944` delay send, `a5+948` reverb send (so for j=8: 952/956/960/964; j=9: 954/958/962/966).
  The values are 8.8-ish words (`-256`, clamp `0..32256`, then a pan/gain curve via `0x4007188c` (gain) and `0x400718c4` (pan law)).
- `a2+968` (word) = **stereo-link flag** (strings "Stereo In Level/Balance/Delay/Reverb" vs "Input L/R Volume/Pan/Delay/Reverb";
  UI names at 0x401cc9be-0x401cca80, `INLR` at 0x401cc9ce). With link on, the two inputs share one set of controls.
- Voices 0..7 use the per-voice 106-byte blocks (`a2 + 106*v`, `+102/+104` level/pan words, `+108` ...).
- Mute/solo style bitmasks come from `0x80001a10/12/14/16` (word reads at the top of the function).
Unverified: exact scaling of each word; which `a2` offsets the SETTINGS/FX menu writes. To find the writers, grep the disassembly for
`#968`/`(968,%a`, and use `SITE_COUNTS` while changing the "Input L Volume" row in digiemu.

## Recorder monitoring ("RECORDER MON TO:" setting)
- Settings object getters (all `a0 = *obj; (*(a0+40))(obj)` thunks): `0x4001f09e` record source, `0x4001f0ce` threshold, `0x4001f06e`
  length-steps, `0x4001f0fe` MON on/off. The audio side mirrors them in `0x4197bf98` (source), `0x4197bf9c` (threshold),
  `0x4197bfa0` (monitor). Only read sites were found in the disassembly; the writer likely uses a computed address.
- Logic at 0x40071c86-0x40071cde: if MON (`0x4197bfa0`) is on and the source is IN L/R/L+R (`0x4197bf98 <= 2`) and the recorder is
  not in state 4 (editing), three flags are set (`fp-269`, `d5`, `d3`) that, inside the loop (0x40071d40-0x40071d60), force
  specific input sources (j = 8, 9) onto the monitor bus path instead of the normal per-input mixer coefficients
  (jumps to 0x400722d0/0x400722d4). Net effect (inferred): "MON" routes the selected input straight to main while recording, bypassing the input
  volume/pan/send controls; with MON off the input is heard only through the normal Audio-in mixer.
  Not verified; test by poking `0x4197bfa0` in digiemu with a sine on RX.

## Hook points for input mods
| Goal | Where |
|---|---|
| Replace/process the input before it is mixed | patch the in-place shift loop 0x40071f16-0x40071f32 or `0x40071c0a` calls at 0x40071f42/f52 (they are `jsr (a3)` with `lea 0x40071c0a`) |
| Inject a mod-generated stereo source into the master | write into `0x80001e18/e98` after 0x40071f52 and before the mix call at 0x40071f76 (the mixer treats them as sources 8/9: input volume/pan/sends then apply) |
| Mute the real input but keep the controls | zero the RX half before 0x40071f16 |
| Grab master/post-FX for resampling | `0x8000ea70/74` after the mix calls; the recorder's own MAIN source uses `0x80001f60 + 256*(0x4199e134&1)` |
| Live-granulate the input | keep a ring in a mod-free SRAM/DDR region (see `digitakt-firmware-map` "Mod-free areas") filled from the RX half each block; read it from the SRC engine at the `0x400757fe` hook |

## Measurements to do first (not done)
1. digiemu: drive RX (`0x80001000` half) with a known sine, dump `0x80001e18` after the output stage, confirm L/R order and the Q31 scale.
2. Confirm the half-selection formula by logging `fp-84` against `0xFC045690` for several blocks.
3. Find which settings-menu action writes `a2+936..968`.
