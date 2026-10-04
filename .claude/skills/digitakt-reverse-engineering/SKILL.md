---
name: digitakt-reverse-engineering
description: Playbook for finding things in the Digitakt mk1 OS 1.53 firmware: objdump/Ghidra setup, tracing methods, and the "poke and measure in the emulator" technique. Use when you need an address, a data layout, or to learn which memory a firmware routine really reads.
---

# Reverse engineering the Digitakt mk1 firmware (what worked)

## Get the code
- Extract section 3 (the main OS) with elekloader's reader, never commit it:
  `PYTHONPATH=../elekloader python3 -c "from elekloader import syx; open('out/firmware/section_3_MAIN_OS.bin','wb').write(syx.Syx.load('../Digitakt_OS1.53.syx').section(3))"` (sha256 `4b47a950...c265c5df`, 2,475,584 bytes, loads at 0x40000400).
- Full disassembly to grep: `m68k-elf-objdump -D -b binary -m 5407 --adjust-vma=0x40000400 out/firmware/section_3_MAIN_OS.bin > out/firmware/s3.dis`
  (~850k lines). **`-m 5407` is essential**: `-m 68000` silently emits wrong code for ColdFire insns. Even so
  objdump prints some EMAC (`macl`, `msacl`) forms as `.short`; Ghidra decodes them.
- Everything under `out/` is git-ignored.

## Ghidra (+ MCP)
- `brew install ghidra` (the cask no longer exists; the formula pulls openjdk@21). GhidraMCP 1.4 loads in Ghidra 12.1.4.
- Import the section as a raw binary, big-endian, base `0x40000400`. Prefer language **`68000:BE:32:ColdfireEMAC`**
  (digiemumac's notes: the stock ColdFire language stops decoding at `movclr`, i.e. inside the audio ISR;
  not re-verified here). Run Auto Analyze; check that `FUN_40077420` (the render ISR) exists.
- The decompiler fails ("bad instruction data") on EMAC-heavy code with the stock language. Read disassembly there.
- GhidraMCP bridge needs `mcp>=1.2,<2` (mcp 2.x renamed FastMCP and crashes the bridge) in its own venv. A running
  Claude session does NOT hot-load MCP servers; either restart it or call the plugin's REST API (default
  `http://127.0.0.1:8080/`): `get_current_address`, `list_functions?limit=`, `get_function_by_address?address=`,
  `disassemble_function?address=`, `decompile_function?address=`, `xrefs_to?address=`, `segments`. `.mcp.json` holds
  absolute paths and is git-ignored.
- Ghidra's analysis fragments functions (the render ISR "ends" at 0x40077479). Use it for xrefs and names; use objdump
  + grep for tracing.

## Tracing methods that worked
1. **Grep the disassembly for addresses.** A buffer or table is found by who references it
   (`grep -n "8000ea70" s3.dis`), then read the surrounding code. Histogram the SRAM addresses (0x8000xxxx) a
   region touches to find its buffers (buffers 0x100 bytes apart = 32 frames x 8 B).
2. **List the calls in a big routine** (`jsr`/`bsr` in the ISR's address range) to get its stage order; the stage
   boundaries are where hooks go. The render ISR order is in the firmware-map skill.
3. **Stack argument layouts** come from the caller: count the `pea`/`move.l x,-(sp)` before the `jsr`.
4. **Struct strides** show up as `lsl #7` (128), `mulu #94`, `moveq #106`, `lea (36,%a0)` etc.
5. **Poke and measure in digiemu** (`tests/emu/scale_probe.py`, env `POKE`, `MEMDUMP`, `TRACE_GR`, `MEASURE`).
   This answered what static reading could not: which of three parameter copies the synth actually reads
   (zeroing the 16-bit smoothed copy did nothing; the 32-bit expanded copy at `0x80002B50 + 212*v` mattered),
   where bit reduction acts (block values collapse to a constant at BR=127, so it is inside the synth),
   the LEV law (a square), the block scale (s16 x 25916), and that the call at `0x40077fa6` rewrites voice 0
   too (so the earlier call `0x40075184` is not "voice 0"). When a hook "does nothing", dump the block at the
   hook's entry and after the stock call to see who overwrites it.
6. **Instruction counts** between a function's entry and its return give cost; a UC_HOOK_CODE over the mod's
   address range gated to a few blocks keeps it fast.
7. **Descriptor/table decoding:** dump the table from the section binary (it is static ROM data, e.g. the 164
   parameter descriptors at `0x401a9d9c`) and decode fields by comparing entries that differ in one known way.
   RAM-initialised structures (like the page layouts at `0x4197ced8`) are not in the image: dump them from the
   emulator (`MEMDUMP="4197ced8:192"`).
8. **Count executions of every reader of a table during a UI action.** To find which of the 44 descriptor-table readers
   draws the SRC page captions (instead of reading all 44 by hand), put `UC_HOOK_CODE` counters on each reader address
   (`SITE_COUNTS="addr,..."` in `tests/emu/scale_probe.py`; addresses come from `grep -n "401a 9d9c" s3.dis`), drive the
   page (view it, then turn a knob) and print the hit counts per phase: only 2 accessors fired for the captions/titles,
   `0x4000fe8a` and `0x4000feac`. Then log their arguments (`ARG_TRACE="addr,..."` prints the entry address, arg1's high
   half, arg1's vtable and arg2) to learn the signature `(param object, descriptor id)` and what the object is.

9. **Find a feature from its UI strings, then walk out.** Scan the section for printable strings (`RECORDER`, `Stereo In`, `Save recording`), take the
   class typeinfo name (`11SamplerView`), find the typeinfo then the vtable by searching for the 32-bit pointers (slot 2 consumeKey, 4 draw, 11 tick), then
   follow the globals the draw/key functions touch. This is how the recorder (`digitakt-recorder`) and its 33 s buffer were found in an hour.
   Ghidra's decompiler is good on this non-EMAC UI/glue code (`decompile_function_by_address`); read EMAC mixers in objdump.
10. **Constants name things**: `1584000` (= 33 s x 48 kHz), `0x82` slot, `5760000`, `#32768`, `#2097152` pool sizes; grep for them in the disassembly.
11. In a background/worktree session, don't prefix commands with `PYTHONPATH=...` (the harness refuses); do `sys.path.insert` inside the python snippet and use
    absolute paths for sibling checkouts (`/Users/.../elektron/elekloader`). `out/` is per-worktree: regenerate section 3 and `s3.dis` there.

## Cross-checks
- Treat any single source (digislicer notes, digi1_mods TECHNICAL_NOTES, a subagent's report) as a hint until a
  disassembly read or an emulator measurement confirms it. Several early assumptions (digiemu's location, which
  synth call covers voice 0, defaults on machine switch) were wrong.
- A verified mod build proves a well-formed file, not working code; emulation is the first real test.
- **An earlier call may also read what you force.** Forcing the shadow voice's PLAY word to FWD.L inside the hook around
  `0x400757fe` did nothing: the call before it (`0x40075184`) also reads the smoothed PLAY word and decides when a
  non-looping voice ends. Check every reader of a parameter (SITE_COUNTS/WATCH on its address) and put the override
  before the first one.
- Record each finding with how it was verified (see "Measured in digiemu" notes in the other skills).

## Sibling repos worth knowing (read only what you need)
`../elekloader` (loader, core sources `mods/core`, docs/ADAPTING.md), `../digislicer` (a real SRC machine: `glue.s`,
`slice.c`, `os153.inc/.h` address maps, `os154.*` for 1.54), `../digi1_mods` (`docs/TECHNICAL_NOTES.md`, mods,
tests), `../digiemumac` (the emulator), `../elektron-firmware-tool` (container/SysEx only).
