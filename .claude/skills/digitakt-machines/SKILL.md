---
name: digitakt-machines
description: How to add a new SRC machine (engine) to the Digitakt mk1: the two registration routes (core 2.1 core_machines vs digipoly-style patching), param pages, plumbing and open questions. Use when designing or implementing a new machine such as the granular engine.
---

# Adding a machine (OS 1.53)

Stock machines: 0 ONESHOT, 1 WERP, 2 REPITCH, 3 SLICE. Machine byte at `sound+0x7e` (stored copy `storage+0x7c`). Many stock bounds assume 0..3.

## Two proven routes
1. **core 2.1 machine slots (recommended; digislicer id 5, NEIGHBOR id 4).** Docs: `../elekloader/docs/ADAPTING.md` "SRC machines"; source `../elekloader/mods/core/machines.s`. Contribute a pointer to a descriptor of six longs to table `core_machines`:
   | off | field |
   |---|---|
   | +0 | id 4-127; stored in kits so fixed forever; claim `machine:<id>` |
   | +4 | long name (10 chars fit; menu + SRC page title) |
   | +8 | short name (4 chars) |
   | +12 | 11x7 Bitmap icon in stock format, or 0 |
   | +16 | params: stock machine 0-3 whose 8 params it takes (defaults, CC 16-23, NRPN 0x80-0x87, Randomize/Reload, SAMP lookup) |
   | +20 | render: stock machine 0-3 it plays as, **or its own id for an empty voice window a mod fills** |
   ```json
   "contribute": [{"to": "core_machines", "order": 50, "data": "00000000",
                   "relocs": [[0, "abs32", "sym:my_machine", 0]]}],
   "resources": {"names": ["machine:6"]}
   ```
   Core lists it after the stock four (by id), the setter accepts it, loaded kits keep it (unknown ids load as ONESHOT, as on stock). `core_machine(id)` returns a descriptor or 0; `core_track_machine[t]` (8 bytes) is each track's machine as the render last took it. Firmware gives any machine >3 SLICE's SRC page; change the layout by hooking 0x400657cc (see digineighbor). Core 2.1 owns ~31 sites (0x40011322, 0x400225f0, 0x40022fe6, 0x4002a76e, 0x40077272, ...; full list in ADAPTING.md): don't patch them. Available in `../elekloader` main / tag v0.4.0 (core `2.1`, builds to `core-2.1.elemod`); 1.54 uses the same addresses except 0x400a1706 -> 0x400a1862.
   Implementation detail (core `machines.s`): `core_mrender` stores the sound's machine in `core_track_machine[t]` and writes the descriptor's `render` into the render's byte table `0x800018bc[t]`; an unknown id there is an empty voice window. `core_mparams` makes the new machine take `params`' 8 parameters; `core_mload` keeps the id on load only if some installed mod adds it. Working stub: `mod/machine.s` (id 6, params 0, render 0 = plays as ONESHOT) + `contribute` in `mod/mod.json`. Icon format: `.long BMP_VT(0x401b73b4), w, h, 1, px, mask, 0`, one word per column with rows in bits 31-25.
   Note: `render == own id` would give the voice an empty window to fill; digigrain does not use it (it plays as ONESHOT and overwrites the voice block after the stock synth, see "Granular engine" below).
2. **Patch it yourself (digipoly, id 4; only if core 2.1 is unavailable; conflicts with core 2.1 owning the same sites).** Sites needed so a new id survives:
   - machine->param-id lookup 0x40078f44 (ids >3 return 0; alias 4->0, `digipoly_lookup`); engine copy of machine byte 0x40077272 (alias); getter 0x4002200a (aliases, ~21 callers); setter 0x400225ca (rejects >3; patch 0x400225f0); wrapper 0x4000d9fc.
   - Machine list: ctor 0x4002a736; item vector 0x40022f6a (patch 0x40022fe6 `7004`->`7005`); cursor limits 0x4002a9e8, 0x4002a4ca; page size 6->4 at 0x4002a76e (else 5th row undrawn).
   - Name table 0x401a9a40 (4 entries, no room; name getters 0x4007910c/2c/4c have `cmp #3`); icons: group getter 0x40029e80, draw 0x40029e9c, default exit 0x40029f60, bitmap object `{vtable 0x401b73b4,h 11,w 7,words 1,glyph,mask,0}`.
   - Raw getter sites that must see the real id: 0x4002b754, 0x4003b3fc, 0x4003bd3a.
   - Load-time clamp 0x4007a2d0 `moveq #5,d2` -> 6, else loads map unknown machine to ONESHOT (also what stock does, so kits stay safe on stock).
   - Resource names like `machine:4 POLY`. Reference: `../digi1_mods/mods/digipoly/`.

## "Plays as" strategy
Both references make the new machine behave as a stock machine for the engine and layer behaviour via render hooks. digislicer hooks SLICE's window function (0x40074df2, returns start/end per block) and PLAY reads, and mutates `V+4` position. digigrain: alias to ONESHOT for the stock voice lifecycle (trig, level, filter, amp, LFO all keep working), then overwrite the voice's block after the synth.

## Parameter page (8 SRC knobs)
- Params are slots 0x11-0x18; names/ranges come from ROM descriptors at 0x401a9d9c (stride 0x34, ~0xa4 entries) and per-machine 8-param blocks (0x1a0 B each: 0x401ab39c, 0x401ab53c, 0x401ab6dc, 0x401ab87c); RAM table `0x4199e9c4[machine*8+slot-0x11]` built by 0x40078b20.
- Reusing the aliased machine's ids is the easy path (digipoly/digislicer). New names/ranges need new descriptors, but the table cannot grow (see "SRC page layout" below): ids 1-3 are the only spare ones. Custom readouts mean formatter functions (PLAY fmt 0x4005f91c, GRID fmt 0x4005fa2e, range fn 0x40078f0c; see digislicer `dsl_prange`, `play_fmt`, `grid_fmt`) — or draw your own page via `ev_draw`/`ev_key`/`ev_enc` (see `digitakt-hook-bus`).
- Knob values reach the engine via 0x400771e8 (engine copy `0x80001502+106*v`, the unsmoothed values); smoothed words at `0x80002772+106*v`. Spare RAM-only slots 46..52 exist; extra persistent state needs `kitstore.h`-style spare bytes.

## Granular engine (digigrain; verified in digiemu, hardware pass done on the previous engine)
Files: `mod/grain.c` (pure fixed-point engine; host-tested bit-exactly against a Python model in `tests/test_grain.py`), `mod/granular.c` (glue), `mod/synth.s` (two synth wrappers), `mod/page.s` (page layout + label hooks), `tools/gen_tables.py` -> `mod/tables.h`, `tools/gen_page_sites.py` -> descriptor sites in `mod/mod.json`.

**Shadow voice.** GRANULAR plays as ONESHOT (core `params` 0, `render` 0), so the stock voice (the "shadow") supplies note on/off, the sample slot, the amp envelope life and the pitch (its `V+4` advance per block, which includes TUNE and the note). We overwrite the shadow's 32 x int32 block at `0x80001a18 + 128*v` after the stock synth, so filter, amp, pan, level and FX still apply. Two `keep2` sites in the render ISR (stock `4eb9...`, wrappers in `mod/synth.s`, 5 stack args copied for each stock call):
- `0x40077f8e` (call to `0x40075184`) -> `digigrain_synth_pre`: runs `digigrain_granular_pre()` first, then the stock call. **`0x40075184` also reads each voice's smoothed PLAY word and decides when a non-looping voice ends**, so the forced PLAY value must be in place before it runs.
- `0x40077fa6` (call to `0x400757fe`) -> `digigrain_synth_all`: stock call, then `digigrain_granular_render()`. `0x400757fe` fills ALL eight blocks (it rewrites voice 0's too), so one render hook after it suffices.
`digigrain_granular_pre()` (per GRANULAR voice, both the 16-bit smoothed copy `0x80002772+106v` and the 32-bit expanded copy `0x80002b50+212v`, word s at +4s, value<<16): POS/STRT word 21 = 0, RTIO/LEN word 22 = 0x7f00, SPRD/LOOP word 23 = 0, and the PLAY word 18 forced to FWD.L (0x0200): the whole sample, forward, looping, so a held note sustains until the amp envelope ends (V+4 wrap jumps are ignored by the rate detector, which only accepts 2 <= |dV+4| <= 512). The real knob values are read from the engine copy `0x80001502+106v`.

**Controls** (words of the 53-word param block; values are word>>8 unless noted): A TUNE (17, stock; pitch only) | B RATE (19, BR's descriptor relabelled; 0..127, noon 64) | C SPRD (23, descriptor 2; noon 64) | D SAMP (20) | E POS (21, STRT's descriptor relabelled; 0..120) | F RTIO (22, descriptor 1; the raw 8.8 word 0x0040..0x0800 = 0.25..8.00) | G ENV (18, descriptor 3; noon 64) | H LEV (24; gain = (LEV/100)^2 x 25916).
- **RATE:** |v-64| <= 1 -> no new grains; v < 64 periodic, v > 64 random intervals (uniform 1..2x mean); kk = |v-64|-1 (0..62), 1/16 Hz units hz16 = 4 + kk*kk/2 (0.25..120 Hz), interval = 768000/hz16 frames. No new grains once the shadow voice is off.
- **RTIO:** grain length = clamp(interval x RTIO >> 8, 16, 65535) *output* frames, independent of pitch (cap 65535 = 1.37 s, the window-phase limit). Periodic overlap is therefore ceil(RTIO) <= 8 whatever TUNE is; random intervals can exceed it transiently, and a full 8-grain pool skips the new grain. The stock readout prints the word/256 with two decimals, so the 8.8 range 0x40..0x800 shows 0.25..8.00 with no formatter.
- **SPRD:** none within 1 of noon; counter-clockwise adds +-(len/4) x amount/64 start-position jitter, clockwise a random +-(amount x 12/64) semitones (`gr_ratio` table); amount = (|v-64|-1) x 64/62.
- **POS:** `pos = (len-2)/120 x min(value,120)`; grains start there and read forward at the shadow's pitch; a grain ends at the sample end.
- **ENV:** shape = (v-64) x 4 in -256..252: sine blended with gate (negative) or quick decay (positive); one live window table per voice, rebuilt only when the shape changes.
- **#19 fix:** each block `next_in` is capped to one interval (two for random mode), and mode 0 zeroes it, so a quick RATE change never leaves a long silence.
- **gr_norm** keeps the summed overlap at or below full scale (uses the real length and the window's mean level).

**Why it is cheap/bounded.** Hardware testing of the previous engine (issue #18) froze the UI at TUNE -12..-24: grains were a fixed 2400 *source* frames, so low pitch made them long, the pool saturated and every voice ran its worst case. Length now depends on the spawn interval, not pitch, and the pool is 8. The new design is expected to fix the freezes but still needs hardware confirmation.
Measured per `digigrain_granular_render` call, one voice (digiemu, `tests/emu/bench.sh`, includes glue): idle 737; 24 Hz RTIO 1: 1,507; 120 Hz RTIO 1: 1,520; RTIO 8 periodic 4,913 (max 5,390); RTIO 8 at TUNE -12 or -24: 7,857 (max ~8.7k) (TUNE assumed 1 unit per semitone around 64; the equal counts, not an audio check, show the pokes took effect); RTIO 8 random 4,832. Engine only (`tests/emu/grain_bench.py`): 24 Hz 1,033, 120 Hz 1,045, RTIO 8 at unity speed 4,453 (integer-step loop), RTIO 8 at non-integer rates about 7.4k (max about 8.4k, interpolating loop). TUNE no longer changes the cost. Stock leaves roughly 38% of the block budget (about 63k cycles); not yet checked cycle-accurately under load.

**Facts that shaped it (measured in digiemu):**
- Bit reduction (BR) is applied inside the synth stage, before our hook, so repurposing its word costs nothing; STRT/LEN/LOOP set the shadow's start/length from the 32-bit expanded copy, not the smoothed words.
- A trig reloads the voice's engine copy from the kit sound (`kit + 0x20 + 0x14 + 2s`, kit ptr at 0x800019ac) for the first blocks: tests that poke params must write both.
- Voice-block scale: s16 x 25916 at LEV 100; LEV is a square law (25/50/100/127 -> 0.0625/0.25/1/1.61).
- PLAY removed means reverse grains are gone; at RATE noon nothing plays (also true of the old DENS).

## SRC page layout (verified in digiemu)
- `0x400657cc(machine)` returns the page's 44-byte layout entry (11 longs: two std::string pointers, **eight parameter ids, one per knob A..H**, 0x0a); stock gives every machine > 3 SLICE's entry (table at 0x4197ced8, 44 bytes per machine 0-3). A `jmp` site there (stock `7203202f0004`) returns ours for machine 6 and otherwise redoes the two replaced instructions and jumps to 0x400657d2. Callers: 0x400325e8 (knob/value overlay) and 0x4003ab02 (knob -> id: `layout[2 + knob]`). Ours (`mod/page.s`): TUNE 0x6c, RATE 0x6e, SPRD 2, SAMP 0x6f, POS 0x70, RTIO 1, ENV 3, LEV 0x73.
- Each parameter id has a 52-byte descriptor at `0x401a9d9c + 52*id` (13 longs): owner machine, slot (the word it edits), min, max, default (8.8), flags, (slot-1)<<16|0xffff, NRPN-like 0x80+slot offset, LFO-destination number, 0xe00, long-name ptr (+0x28), group-name ptr (+0x2c), short-label ptr (+0x30).
- **The table cannot grow:** 44 code sites read it by absolute address and each bounds-checks the id (`cmpi #164`, ids >= 164 collapse to 0), and the per-id formatter objects are a 164-entry RAM array. Only ids 1-3 are spare ("Error" placeholders; id 0 means "no param", REPITCH uses it). `tools/gen_page_sites.py` turns them into RTIO (slot 22, 0x0040..0x0800, default 0x0100), SPRD (slot 23, 0..0x7f00, default 0x4000) and ENV (slot 18, 0..0x7f00, default 0x4000) with `bytes`/`ptr` sites (other fields copied from LEN 0x71, LOOP 0x72, PLAY 0x6d; owner 6 keeps them out of stock Randomize lists). Unknown ids get a default dial and a "%.2f" readout of word/256.
- **RATE and POS reuse the stock BR (0x6e, slot 19, 0..127) and STRT (0x70, slot 21, 0..120) ids** because no more unique ids exist. Their names come from hooks on the two label accessors, `0x4000fe8a(obj, id)` (short label, descriptor +0x30; draws the knob caption) and `0x4000feac(obj, id)` (long name, +0x28; the knob-turn title): `jmp` sites over their first two instructions (`222f0008 0c81000000a4`, 10 bytes). `digigrain_label_short/long` answer only for ids 0x6e/0x70 when the object is the page's param object (vtable 0x4017eb58) whose obj[16] (vtable 0x40181330) -> sound[16] has machine byte (+126) == 6, else redo the replaced instructions (cmpi flags matter: the stock `scs` follows) and resume at 0x4000fe94 / 0x4000feb6. Stock ONESHOT/SLICE pages are unchanged (STRT, BR, LEN...). Other readers of those fields (LFO destination lists, Randomize pages) still show the stock names for ids 0x6e/0x70.
- **Defaults on machine switch:** the stock switch resets the words to the ONESHOT params machine's defaults, not our descriptors' (BR 0, STRT 0, LEN 120, LOOP 0, PLAY 3). `digigrain_granular_tick` (ev_tick, UI task) detects a track newly becoming machine 6 whose words 18/19/21/22/23 equal 0x0300/0/0/0x7800/0 and writes ENV 64, RATE 36, POS 0, RTIO 0x0100, SPRD 64 into the UI kit sound (`*(0x4199dc44) + 0x20 + 0xa2*t`, params at +0x14). Heuristic: a track deliberately saved with exactly those values is re-defaulted once (issue #8).
- **Value readouts (verified in digiemu, screenshots):** two firmware routines turn a parameter word into text, and both are hooked (`mod/page.s`, text in `mod/readout.c`, sites from `tools/gen_page_sites.py`). `0x400657ee(id, word)` returns the global buffer `0x4197ce98` (the knob-turn title, "Grain Rate=..."); `0x4000f324(obj, id, word, char *out)` fills the 16-byte stack buffer of the value drawn under a turning knob. Both look up `0x40065794(id)` = per-id object `0x4197d2f8 + 84*id` whose std::function at +0x14 (manager +8, invoker +12 = the formatter `f(fnobj, word, out)`) makes the text. The hooks answer for SPRD (id 2), ENV (id 3) and, only while the active track (`0x4197b6b4`, long) is GRANULAR, RATE (BR's id 0x6e); else they redo the replaced instructions and run stock code. Text: RATE `OFF` / `23.0Hz` (`~` = random side), SPRD `OFF` / `POSnn%` / `PITnn%`, ENV `SINE` / `GATEnn%` / `DCAYnn%` (at most 7 characters: about what fits under a knob; the title has room). POS and RTIO keep the stock readouts. Not hooked: other readers of ids 2/3/0x6e (e.g. LFO destination or Randomize pages) were not examined.

## Other open questions
1. Voice stealing with p-locked sample slots; eight dense voices at once.
2. Pitch mapping of note -> sample pitch is avoided by reading V+4 deltas.
3. Meaning of the sample table's +4 u16.
