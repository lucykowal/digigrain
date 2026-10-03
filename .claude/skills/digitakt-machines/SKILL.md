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
   Note: `render == own id` gives the voice an empty window to fill (SLICE-like window function, `digitakt-firmware-map`), which is the natural fit for granular; the render hooks for filling it are still to be worked out.
2. **Patch it yourself (digipoly, id 4; only if core 2.1 is unavailable; conflicts with core 2.1 owning the same sites).** Sites needed so a new id survives:
   - machine->param-id lookup 0x40078f44 (ids >3 return 0; alias 4->0, `digipoly_lookup`); engine copy of machine byte 0x40077272 (alias); getter 0x4002200a (aliases, ~21 callers); setter 0x400225ca (rejects >3; patch 0x400225f0); wrapper 0x4000d9fc.
   - Machine list: ctor 0x4002a736; item vector 0x40022f6a (patch 0x40022fe6 `7004`->`7005`); cursor limits 0x4002a9e8, 0x4002a4ca; page size 6->4 at 0x4002a76e (else 5th row undrawn).
   - Name table 0x401a9a40 (4 entries, no room; name getters 0x4007910c/2c/4c have `cmp #3`); icons: group getter 0x40029e80, draw 0x40029e9c, default exit 0x40029f60, bitmap object `{vtable 0x401b73b4,h 11,w 7,words 1,glyph,mask,0}`.
   - Raw getter sites that must see the real id: 0x4002b754, 0x4003b3fc, 0x4003bd3a.
   - Load-time clamp 0x4007a2d0 `moveq #5,d2` -> 6, else loads map unknown machine to ONESHOT (also what stock does, so kits stay safe on stock).
   - Resource names like `machine:4 POLY`. Reference: `../digi1_mods/mods/digipoly/`.

## "Plays as" strategy
Both references make the new machine behave as a stock machine for the engine and layer behaviour via render hooks. digislicer hooks SLICE's window function (0x40074df2, returns start/end per block) and PLAY reads, and mutates `V+4` position. For granular: alias to ONESHOT/SLICE for the stock voice lifecycle (trig, level, filter, amp, LFO all keep working), then override sample reading.

## Parameter page (8 SRC knobs)
- Params are slots 0x11-0x18; names/ranges come from ROM descriptors at 0x401a9d9c (stride 0x34, ~0xa4 entries) and per-machine 8-param blocks (0x1a0 B each: 0x401ab39c, 0x401ab53c, 0x401ab6dc, 0x401ab87c); RAM table `0x4199e9c4[machine*8+slot-0x11]` built by 0x40078b20.
- Reusing the aliased machine's ids is the easy path (digipoly/digislicer). New names/ranges mean cloning descriptor blocks and formatters (PLAY fmt 0x4005f91c, GRID fmt 0x4005fa2e, range fn 0x40078f0c; see digislicer `dsl_prange`, `play_fmt`, `grid_fmt`) — or draw your own page via `ev_draw`/`ev_key`/`ev_enc` (see `digitakt-hook-bus`).
- Knob values reach the engine via 0x400771e8; smoothed words at `0x80002772+106*v`. Read your 8 params there in the render hook. Spare RAM-only slots 46..52 exist; extra persistent state needs `kitstore.h`-style spare bytes.

## Granular engine v1 (implemented and verified in digiemu)
`mod/grain.c` (pure fixed-point, host-tested against a Python model in `tests/test_grain.py`) + `mod/granular.c` (glue) + `mod/synth.s` (the one site). Verified in the emulator on the real firmware: track 1 set to GRANULAR via FUNC+SRC shows the title "GRANULAR" and the SLICE-style SRC page; a grain's level follows a Hann window up to the source peak (16383 x 25916 = s16 peak 16384, so the gain constant is right) and the audio output carries the 440 Hz pitch. Knob mapping v1 (SLICE page positions, ONESHOT param ids): E (word 21) = grain position, F (word 22) = size, C/BR (word 19) = density, H (word 24) = level (LEV scaling unverified at values other than 100), TUNE = pitch via the shadow voice. Page labels still read SLICE/LEN/GRID until the page layout (0x400657cc, as digineighbor does) is hooked. Not yet verified: audio render margin, other voices/polyphony, behavior at sample end, LEV scaling.

## Granular design (from the traced render path)
- Machine id 6 via core 2.1: `params` = a stock machine for the 8 SRC knobs, `render` = 0 (plays as ONESHOT) so the stock voice runs as a "shadow" (note on/off, sample slot, V+4 playhead/pitch, amp env/filter/pan/FX downstream).
- Hook: `keep2` site at **0x40077fa6** (stock `4eb9400757fe`, the call to voices 1-7's synth) -> `lucys_granular_synth(...)` calls stock `0x400757fe` with the same stack args, then for each voice v with `core_track_machine[v]==6` and the voice on, overwrites the block at `0x80001a18+128*v` with grain output (int32 Q31 mono; scale to calibrate). **Measured in digiemu: `0x400757fe` fills ALL eight voices' blocks (including voice 0, overwriting anything written after the earlier call at 0x40077f8e / `0x40075184`, whose job is something else), so one site suffices.** It is a pass-through wrapper in `mod/synth.s` (repeat the 5 stack args, call stock, then `lucys_granular_render()` for v = 0..7); the loader accepts it (stock bytes match, no overlap with core 2.1's 39 sites).
- Inputs per block: smoothed param words at `0x80002772+106*v` (+2s, slots 0x11-0x18 = the 8 knobs); sample from `V+0x5C` slot -> `0x403193a0[slot]` (ptr, length at +8); trig = bit v of `0x80001228`; playhead/pitch = V+4 and its per-block delta.
- Open: Q31 scale of voice blocks (calibrate in Unicorn or with a known sample on hardware); behaviour when the shadow voice ends at sample end; fast-audio interaction with the 0x40077fa6 site; SRC page names/ranges (knob UI) beyond reusing the params machine's; confirm `0x40072478`/`0x4007269c` roles.

## Other open questions
1. Pitch mapping of note -> sample pitch (avoided by reading V+4 deltas).
2. Voice stealing with p-locked sample slots.
3. Meaning of the sample table's +4 u16.
