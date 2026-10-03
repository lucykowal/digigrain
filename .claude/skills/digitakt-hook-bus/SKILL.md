---
name: digitakt-hook-bus
description: Core mod's event hook bus (ev_tick/draw/key/enc/settings/render_in/render_out), handler signatures, calling convention, SETTINGS rows, drawing, hook-shim idioms and register pitfalls. Use when writing handlers or patching firmware code.
---

# Hook bus (core 2.0a)

Core owns the shared sites; never patch them, subscribe in `mod.json`. Handlers use the **C ABI**: args on the stack, d0/d1/a0/a1 free, everything else preserved, result in d0. Order ascending (10-90 typical, default 50).

| event | site | signature | notes |
|---|---|---|---|
| `ev_tick` | 0x4000a770 | `void f(void *ctrl)` | 30 Hz UI task; set `*((u8*)ctrl+0x20)=1` to recompose |
| `ev_draw` | 0x4000a7d6 | `void f(void *bmp, void *ctrl)` | after stock drawAll; draws over composed frame |
| `ev_key` | 0x4000b770 | `int f(void *brain, void *ev)` | nonzero = taken (stops chain and stock); `ev+12` key id, `ev+16` flags (1 press, 8 repeat, 2 FUNC) |
| `ev_enc` | 0x4000b7ba | `int f(void *brain, void *ev)` | `ev+12` knob 1-8 (A-H, 9 = LEVEL), `ev+16` delta (16/notch on stock pages) |
| `ev_settings` | 0x40058800 | `void f(void *menu)` | add rows via `core_additem(menu,row)` (import it) |
| `ev_render_in` | 0x40077428 | `void f(void)` | audio ISR, 1500 Hz |
| `ev_render_out` | 0x400784c8 | `void f(void)` | audio ISR exit |

Also core `.boot` at 0x40000538 (copies RAM image, zeroes `.bss`, starts DTIM0). All handlers always run except key/enc chains.

## Render-ISR rules
- 32-frame blocks = 0.67 ms budget; keep short and bounded; no blocking firmware calls; no allocations.
- Core saves d1/a0-a2 around handlers. If you use EMAC: save/restore MACSR/ACC0/ACCEXT01 and clear ACC0 first.
- ColdFire 5475 has no `ff1`/`exg`. ISR stack is the interrupted task's.
- Sites inside the FAST AUDIO block 0x400716c0-0x4007629a must be absolute (no PC-relative, no relative branches).

## Key and key ids
5 "...", 6 SETTINGS, 12 YES, 13 NO, 3/4 PTN/BANK, 20 SRC, 23 LFO (from emulator scripts; verify), 24-39 trig keys, 40-47 knob pushes A-H. Knob turns within ~40 ticks of a push are dropped by the panel driver. Key flags bits: 0 down, 1 FUNC, 2 double, 3 repeat, 4 up, 5 long, 6 longer.

## Drawing
- Screen 128x64, 1 bpp. **y=0 is the bottom row**; the stock 5 px font is upright only that way.
- `FILLRECT(bmp,x0,y0,x1,y1,c)` 0x400c19a6 (c: 0 clear, 1 set, -1 invert); `FRAMERECT` 0x400c178a; `VLINE` 0x400c1040; `PIXEL(bmp,x,y,c)` 0x400c0cf4; `TEXT(bmp,font,x,y,flags,fmt,...)` 0x400c257c with font 0x40200b0c; `BLIT(dst,src,x,y,centre)` 0x400c2960; `INVALIDATE(view)` 0x400c9812.
- Declare firmware calls as function pointers returning `u32` (pointers come back in d0): `#define F ((void(*)(...))0x...)`. `M(m,o)` = `*(volatile int*)((char*)(m)+(o))`.
- Never free firmware-owned buffers (operator delete halts on non-heap pointers). `operator new` = 0x400d4180.

## Full-screen page pattern (digimatrix)
Draw an overlay in `ev_draw`, take keys/knobs in `ev_key`/`ev_enc`, request redraw via `ev_tick`. For stock views: copy the vtable to RAM, repoint slots, set the object's vptrs (digiutils `page.c`). Knob listeners are reached via the `+4` subobject thunk; patch both the primary slot and the thunk.

## SETTINGS row
Row = 4 pointers `{label_fn, select, draw, change}`; pass to `core_additem(menu,row)`. Label fn builds a `std::string` via 0x4017ac20 (copy the `row_label` template from digipoly/digimatrix). select/change get a payload; call `INVALIDATE((char*)*payload+0x38)` to redraw; draw is `(a,b,bmp,x,y)`. Claim `settings:ROW NAME`. Callback conventions are not documented in the loader; copy a working mod.

## Hook-shim idiom (when no event fits)
Shim saves d0-d1/a0-a1 (or d0-d7/a0-a6 around unverified firmware calls), pushes args, calls C, restores, **re-executes the displaced instructions**, then `rts` or `jmp` to the continuation. For a hook mid-function that resumes elsewhere, pop the return address and `jmp`. Use `.balign 2/4`.

## Lessons (from digi1_mods RISKS/notes)
- Hooks must preserve every register the caller relies on; a chord hook missed a4-a6; a callee clobbered a0; a decision in d7 was lost by a restoring `movem`. Test with a stub that junks all scratch registers.
- Never write message `+0x48` (next link) or other firmware scratch; confirm "dead" cave memory is truly unused.
- Calling the conditional-trig functions from inside the trig builder froze the unit: check reentrancy/interrupt context; build a minimal isolated test first.
- Emulator passing is not hardware proof; digi1_mods' elekloader builds are emulator-verified only.
