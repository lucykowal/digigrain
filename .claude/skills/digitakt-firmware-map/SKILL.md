---
name: digitakt-firmware-map
description: Reverse-engineered Digitakt mk1 OS 1.53 memory map and routine/data addresses (audio engine, voices, kit/pattern layout, sample table, UI views, FS, MIDI). Use when you need an address or struct layout. OS 1.53 only.
---

# Digitakt mk1 OS 1.53 firmware map

Sources: `../digi1_mods/docs/TECHNICAL_NOTES.md` (1295 lines; 39-165 engine/machines, 568-700 MIDI/load, 702-960 UI, 1024-1295 mods/kit storage), `../digislicer/os153.h|.inc` (hand-curated routine addresses; `os154.*` for 1.54). Treat unverified entries as hints; confirm by disassembly (`objdump -m 5407`, see `digitakt-workflow`).

## CPU / memory
- ColdFire V4e (MCF54418), big-endian. Main OS loads at 0x40000400 (section 3, 2475584 B). SDRAM 0x40000000-0x47ffffff (code, data, samples). Internal SRAM 0x8000xxxx (audio engine state). No MMU.
- Mod-free areas: DDR 0x47BE0000-0x47C00000, SRAM 0x8000F700-0x80010000, 0x80003360-0x80008000.

## Audio engine / render
- Render ISR 0x40077420 (ends `rte`), once per 32-frame block, 1500/s at 48 kHz; saves EMAC state itself. Sequencer clock ISR 0x4007041c posts to the audio queue.
- Voice path entry 0x400777a2; voice start 0x40077a76 (ORs `1<<voice` in d3); post-message loop 0x40077d50; merge point 0x40077d72; smoothing stage 0x40074b9e (called 0x40077e9a); LFO stage 0x400ed53e (called 0x40077eac); mixer 0x40071c20 (half-buffer ISR 0x4007814a); audio tap 0x40078150.
- Master block `0x8000ea70`: 32 frames of `{L,R}` int32, 8 bits hotter than the 24-bit codec words. Master mix hook 0x400721e6. 12-ch USB bus 0x80002160; codec TX 0x4ba8f080; SSI 0xfc0c8000; RX buf 0x80001000.
- **Voice state** `V(v)=0x8000EDC4+94*v`: +4 position (0x8000EDC8), +0x28 on, +0x5C sample slot byte. `0x80001228` bit v = "voice v starts this block". Machine byte per voice `0x800018BC[v]`. Per-voice track levels (16-bit) `0x80002760`; smoothed params `0x80002772+106*v` (slot s at +2s). Engine tables at `0x800014F0`; per-voice param copy `0x80001502+v*0x6a`; 32-bit expanded `0x80002B50+v*0xd4`; `LOADED[v]` = `0x800014f0+4*(0x131+v)`.
- Param plumbing: `0x40077282(ptr,voice)` loads a sound block into a voice; `0x400771e8(value,voice,slot)` writes a knob value (voice 16 = globals); dirty mask `0x4399db14+v*8`; p-lock apply 0x40074b0a. Voice<->track is 1:1 unless msg+8 is changed.
- Messages (0x4c bytes; alloc 0x400ee036, copy 0x400ee0a0, post 0x400ee1bc/0x400ee296): +0 type, +4 on/off(1/2), +8 voice, +0xc id (1 seq, 2 live), +0x14 level, +0x18 note, +0x24 flags, +0x28 sound ptr (`kit+0x20+t*0xa2`), +0x44 p-lock block, **+0x48 next link: never write**.

## Param slots (word s at `sound+0x14+2s`, 53 words; 0..45 saved, 46..52 RAM-only)
1-8 LFO1, 9-16 LFO2, 0x11-0x18 (17-24) the eight SRC-page params (TUNE = 0x11 on all sample machines), 0x19-0x20 FLTR, 0x21-0x25 FLTR2, 0x26-0x2d AMP. Slot 20 (+0x3c runtime) = sample slot, 0 = none. Loads zero all 53 words first.

## Kit / pattern
- Kit objects: UI kit ptr `0x4199dc44`, engine kit ptr `0x800019ac`. Sound block = 0xa2 bytes at `kit+0x20+t*0xa2`: +4..0x13 name, +0x14 params, **machine byte +0x7e**, +0x92..0xa1 sample ref. Level word `kit+0x10+2t`.
- Patterns: 16 tracks at `0x409bac18+t*0x38f` (NOT1-4 arrays +0x280/2c0/300/340; defaults +0x384..0x387). Active track `0x4197b6b4`; mute mask `0x4199e47c`.
- Serialisation: save 0x4007a5a0, load 0x4007a236, tables 0x401ac1d4/0x401ac28c; record header 0xBEEFBACE v3. Persistent spare bytes: `../digi1_mods/src/kitstore.h` (6 B/track used by matrix/poly/eq).

## Samples
- `OS_SMP_TAB 0x403193A0`: 128 slots x 16 B `{PCM ptr, rate, length, ratio}`; PCM valid in 0x40000000-0x50000000, understood as **s16** (digislicer `slice.c`). `OS_REF_TAB 0x421F230C` (+4 content hash). Free sample pool 0x400eb782. Stock slice table 0x402F9380+0x400*slot.
- SLICE window fn 0x40074df2 (per block per SLICE voice): args p(+4: PLAY at +2, SLICE +8, LEN +10, GRID +12 high bytes), note<<16, length, voice; returns start/end in d0/d1. PLAY reads patched at 0x40075282, 0x400759dc, 0x400760ba (inside FAST AUDIO block; absolute only). Resampler delay ~14 samples on direction change.

## UI
- Views: vtable slot 2 consumeKey, 4 draw(this,bmp), 11 tick. Key dispatch 0x400cab06; LED dispatch 0x400ca40a. MainScreenView ctor 0x4002f088, vtable 0x40182f68. TRIG page vtable 0x40184004; SRC key handler 0x4003b272 (vptr 0x401848dc); master view vtable 0x401845d8. Menus: SETTINGS 0x40058800, GLOBAL FX/MIX 0x4004468e (tail 0x40044acc), `ITEM_CTOR 0x400c423c`, `MENU_ADD 0x400c3a72`. Bitmap vtable 0x401b73b4; font `0x40200b0c`. `sprintf 0x40000e82`, `vsprintf 0x400005e0`.
- Machine list items 0x4002a736/0x40022f6a; icons 0x40029e80/0x40029e9c (see `digitakt-machines`).

## Live notes / MIDI
`liveNoteOn 0x400d53dc`, `liveNoteOff 0x400d575e`, live builder 0x40076b3c; MIDI in note-on 0x400d5baa, CC 0x400d4a90, rx-channel table `0x4197b700[16]`, `Brain::processMidiEvent 0x40008c6e`, CC-to-param 0x400d6a58; trig builders 0x4006f4be (audio) / 0x4006f846 (MIDI).

## Filesystem (+Drive)
ekFS: open 0x400cf178, read 0x400ceebe, write 0x400cef1e, close 0x400cf136, mkdir 0x400cde0c, lookup 0x400d0aa4; mutex 0x42685690 (lock 0x40001884/unlock 0x400019b6; 0x400018ec/0x40001a0e in digislicer's names), mounted flag 0x420edc50. Use `/cfw/` paths and claim `drive:/cfw/...`.

## Render path per 32-frame block (traced in Ghidra + `objdump -m 5407`, OS 1.53)
Method: `m68k-elf-objdump -D -b binary -m 5407 --adjust-vma=0x40000400 out/firmware/section_3_MAIN_OS.bin`; Ghidra (GhidraMCP, port 8080) decodes ColdFire/EMAC well but its decompiler fails ("bad instruction data") on EMAC code, so read disassembly. Order of calls in the render ISR (0x40077420), from the `jsr` sites:
1. `0x4007472a(a2)`; param smoothing 0x40074b9e (0x40077e9a), LFO stage 0x400ed53e (0x40077eac) earlier.
2. **Voice 0 synth** `0x40075184` (call at 0x40077f8e) and **voices 1-7** `0x400757fe` (call at 0x40077fa6). Both take `(a2=engine/param base, 0x4199e466, d5, d7, 0x80001f18)`. Per voice (loop head 0x400758b8, voice stride 94 B for V(v), 106 B for param blocks): calls the window fn 0x40074df2 (0x4007527a voice 0, 0x400759d0 others), clamps position V+4 (0x8000edc8) to the window with a 141-sample margin (resampler reach), then runs the resampler.
3. **Resampler** (0x40075f14-0x4007606a): reads **s16 mono PCM** from the sample (`movew (a2)+` into a ring at 0x80001208), 16-iteration polyphase FIR using MAC with 32-bit coefficients, writes 32 samples to scratch **0x8000eb70**; then (0x40076172-0x4007620e) a per-voice stage (state in the voice struct, table 0x401a59c0) writes the voice's **mono block of 32 x int32 to `0x80001a18 + 128*v`** (`lsl #7`). Loop ends at 0x40076234 (`v` = 8).
4. `0x40072478(a2, 0x80001a18)` (call 0x40077fc8): processes the voice blocks in place, voices in pairs (`a5`, `a5+128`), with MAC; reads per-voice params at stride 106 (looks like the multimode filter; role unconfirmed).
5. Loop over 8 voices calling `0x4007266e`/`0x4007269c(voice, 0x80001a18+128*v, params)` (0x40077fe4/0x40078024) when the voice's flag words at +22/+24 say so (role unconfirmed; per-voice effect).
6. `0x400716c0` (call 0x40078078): the mix function (FAST AUDIO's copied block starts here). Inside it, `0x4007197e(0x8000ea70, 0x80001a18 voice blocks, gain table 0x4199ddd8, scratch)` mixes the 8 voice blocks into the **master pair: L at 0x8000ea70, R at 0x8000ea74** (each a 32-word stream; call repeated for R with gains 0x4199de00), then FX/sends via `0x40073654(0x8000e670, 0x8000ea70, a2+900)` etc.
7. `0x40073168`, `0x40073304`, `0x4007234c`, then **`0x40071c20`** (call 0x4007814a): output writer to the DMA ring / codec / USB.
Buffers 0x8000e670/e770/ea70/eb70 are 0x100 bytes apart (32 frames x 8 B). Pre-FX bus roles beyond these are unconfirmed.

### Consequence for adding a machine
Per-voice mono blocks at `0x80001a18 + 128*v` are the cleanest injection point: anything written there before step 4 gets the stock filter/amp/pan/level/mute/FX path for free. A `keep2` site redirecting the `jsr 0x400757fe` at **0x40077fa6** (stock bytes `4eb9400757fe`; ISR body, outside FAST AUDIO's block) can call stock then overwrite the blocks of GRANULAR tracks (`core_track_machine[t] == 6`). Risks: fast-audio may rewrite that call; scale of the int32 samples vs s16 PCM is not yet measured (calibrate in Unicorn with a known sample); stock voice (plays as ONESHOT) still advances V+4 and ends at sample end.

### Mixer and sample table details (traced)
- **Mixer `0x4007197e` / `0x40071a16`** (called from 0x40071f72 etc.): a 32-iteration, 10-input matrix mix with per-sample coefficient ramps. For each output sample n: `out[n] = sum_j coef_j * src_j[n]` (fractional MAC `msacl`), where the 10 sources are contiguous 128-byte blocks starting at `0x80001a18`: **8 voice blocks, then two external-input blocks at 0x80001e18 and 0x80001e98** (the 10 blocks end at 0x80001f18, the address passed to the voice-synth calls). Coefficients (10 per output channel, Q31) live in tables 0x4199ddd8 (L) / 0x4199de00 (R) etc.; they ramp by a per-sample delta (`addl delta,coef` each iteration), so pan/level/mute changes are smoothed. Output pair: L = 0x8000ea70, R = 0x8000ea74 (32 words each, step 8 as the two calls interleave; layout unconfirmed).
- **Voice block format:** 32 x int32 mono, Q31 fractional (MAC fractional mode, `MACSR=0xa0` set before mixing). **Measured in digiemu** (`tests/emu/scale_probe.py`, 48 kHz s16 sine, peak 16384, default sound params, unity pitch): block peak 0x194e57a7 = **s16 x ~25916** (0.395 of s16<<16, about -8 dB). Read at 0x40077fac (after both synth calls).
- **Sample table 0x403193a0, 16 B/slot, valid slots 0..130** (accessors `cmp #130`): +0 PCM pointer (long; default for an empty slot 0x40319bd0), +4 u16 (accessor at 0x40074f94; meaning unknown), +8 length in samples (default 248), +12 ratio Q30 (default 0x40000000 = 1.0, presumably rate relative to 48 kHz). Empty-slot init at 0x40074fd0; the voice loader copies +0, +8, +12 into the voice struct (0x400750b4-0x400750bc).
- **s16 mono confirmed** by the resampler's `movew (a2)+` reads with stride 2 in 0x40075f60.
- **Voice struct (stride 94, base 0x8000edc4)** fields seen: +4 position, +0x28 voice-on byte (cleared at init 0x4007509c), +0x2a/+0x29 flags, +0x5C slot.
- **Window fn args** (0x40074df2): `(sp+4)=param block ptr, +8 note<<16, +12 sample length, +16 voice`. Only called for SLICE-like voices.
- **Measured:** at unity pitch `V+4` advances **32 per block** (sample frames), slot byte at V+0x5c, `on` byte V+0x28 = 1 while playing and 0 after the sample ends (V+4 reaches the sample length, the last blocks fade to ~0); table entry for a 48 kHz sample has ratio 0x40000000, length = frames, PCM in DDR (e.g. 0x4bbaf630).
- **Pitch for a shadow voice:** the stock voice (a new machine that "plays as ONESHOT") keeps advancing V+4 each block by `32 * pitch_ratio` source samples, with TUNE/LFO/glide already included. A granular engine can read `V+4` deltas as its pitch and `V+4` as its playhead instead of reimplementing note->ratio (note->ratio table not located).
