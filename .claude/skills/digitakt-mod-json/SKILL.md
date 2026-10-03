---
name: digitakt-mod-json
description: Source mod.json schema for elekloader Digitakt mods: fields, subscribe, sites ops, contribute/collections, resources, memory sections. Use when writing or editing mod.json or choosing sections.
---

# mod.json (source format, consumed by `elekloader.sdk.build`)

Authoritative: `../elekloader/elekloader/sdk/build.py` and `docs/FORMAT.md`; template `../elekloader/examples/hello-marker/`. Unknown fields are rejected.

```json
{
 "id": "lucys-granular", "version": "0.0.1",
 "title": "...", "category": "Machines", "author": "...",
 "license": "GPL-2.0-or-later", "description": "...",
 "device": "digitakt-mk1", "os": "1.53",
 "sources": ["granular.c"],
 "subscribe": [{"event": "ev_draw", "fn": "lucys_granular_draw", "order": 60}],
 "requires": ["core"]
}
```

| field | notes |
|---|---|
| `id` | lowercase, unique; prefix of every global symbol |
| `device`/`os` | checked against the stock file |
| `sources` | `.c` (gcc, profile cflags, `-I moddir`) and anything else via `as` |
| `defsym` | `{NAME: value}` passed to `as` only |
| `cflags` | extra gcc flags |
| `name_string` | emits `str_name` = "<name_string> <version>" in `.run` |
| `subscribe` | `{event, fn, order}`; `fn` is a global you define; order default 50, ascending, ties by mod id |
| `sites` | patches to stock (below) |
| `collections` | `{"table": entry_size}` tables you declare (size multiple of 4) |
| `contribute` | `{to, order, data(hex), relocs:[[off,"abs32\|pc32\|pc16","sym:NAME\|sec:NAME\|abs",addend]], claims:[[lo,hi]]}` adds entries to another mod's table; `claims` are image ranges rewritten at run time |
| `weak` | imports that may be missing (resolve to `core_zero`) |
| `copied` | image block the mod copies elsewhere at run time |
| `resources` | `{"names":[...], "regions":[{name,lo,hi}]}` |
| `requires`/`conflicts` | always `requires: ["core"]` |
| `ports` | per-OS overrides (digislicer has a `"1.54"` block) |

## sites
`{"addr":"0x...","stock":"<hex of whole stock insns>","op":...,"target":"sym" | "new":"hex","kind":"code"}`

| op | result |
|---|---|
| `jsr` / `jmp` | `4eb9`/`4ef9` + target, `4e71` nop-padded to stock length (stock must be >= 6 bytes, even) |
| `keep2` | stock opcode word + new 32-bit address (redirect a `jsr.l`/`lea.l`) |
| `ptr` | 4-byte address as data (vtable slot) |
| `bytes` | `new` hex, same length as `stock`; add `"kind":"code"` for instructions |

The SDK checks stock bytes at build time. Your routine must redo the displaced instructions' work and preserve every register the surrounding code relies on. A mod with only `sites` and no sources needs no compiler.

## Sections and budgets
- Only `.run` (code+data+rodata, in RAM), `.fast`, `.bss` (and core's `.boot`). Initialised data in `.run` is fine; `.bss` is zeroed by core at boot.
- RAM: DDR 0x47BE0000-0x47C00000 = **128 KB shared by all mods** (`.run` + tables + `.fast` load images + `.bss`). ~100 KB free with digi mods loaded.
- `.fast` SRAM 0x8000F700-0x80010000 = 2304 B, needs the `fast-audio` mod (`fa_copies`); otherwise use `.run`.
- Other free areas: sram-block 0x80003360-0x80008000 (FAST AUDIO's copy area).
- No printf/malloc/libc. Firmware routines are called through function pointers at fixed addresses (they need no relocation).

## resources.names examples
`sysex:0x7d`, `settings:MY ROW`, `drive:/cfw/mine.bin`, `ui:SRC page:hold YES`, `machine:5`, `param:SLICE PLAY=4`. Core claims `timer:DTIM0`.
