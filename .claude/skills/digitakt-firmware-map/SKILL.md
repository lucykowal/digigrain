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
- **Unmapped:** the render's per-sample resample/interpolation loop and per-voice accumulate into the master block.

## UI
- Views: vtable slot 2 consumeKey, 4 draw(this,bmp), 11 tick. Key dispatch 0x400cab06; LED dispatch 0x400ca40a. MainScreenView ctor 0x4002f088, vtable 0x40182f68. TRIG page vtable 0x40184004; SRC key handler 0x4003b272 (vptr 0x401848dc); master view vtable 0x401845d8. Menus: SETTINGS 0x40058800, GLOBAL FX/MIX 0x4004468e (tail 0x40044acc), `ITEM_CTOR 0x400c423c`, `MENU_ADD 0x400c3a72`. Bitmap vtable 0x401b73b4; font `0x40200b0c`. `sprintf 0x40000e82`, `vsprintf 0x400005e0`.
- Machine list items 0x4002a736/0x40022f6a; icons 0x40029e80/0x40029e9c (see `digitakt-machines`).

## Live notes / MIDI
`liveNoteOn 0x400d53dc`, `liveNoteOff 0x400d575e`, live builder 0x40076b3c; MIDI in note-on 0x400d5baa, CC 0x400d4a90, rx-channel table `0x4197b700[16]`, `Brain::processMidiEvent 0x40008c6e`, CC-to-param 0x400d6a58; trig builders 0x4006f4be (audio) / 0x4006f846 (MIDI).

## Filesystem (+Drive)
ekFS: open 0x400cf178, read 0x400ceebe, write 0x400cef1e, close 0x400cf136, mkdir 0x400cde0c, lookup 0x400d0aa4; mutex 0x42685690 (lock 0x40001884/unlock 0x400019b6; 0x400018ec/0x40001a0e in digislicer's names), mounted flag 0x420edc50. Use `/cfw/` paths and claim `drive:/cfw/...`.
