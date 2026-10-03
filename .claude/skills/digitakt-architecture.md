---
name: digitakt-architecture
description: Understand Digitakt mod architecture and design patterns
slug: digitakt-architecture
---

# Digitakt Mod Architecture

High-level design patterns and constraints for Digitakt mods.

## Hook-Based Event System

Digitakt firmware invokes hooks at key events. A mod subscribes to events via `mod.json`:

```json
"subscribe": [
  {"event": "ev_tick", "handler": "mymod_on_tick"},
  {"event": "ev_draw", "handler": "mymod_on_draw"}
]
```

**Event Types** (in execution order):

| Event | Frequency | Purpose | Context |
|-------|-----------|---------|---------|
| `ev_render_in` | 41.666 kHz | Pre-process audio input (before synthesis) | Audio interrupt, real-time |
| `ev_tick` | 41.666 kHz | Main audio processing (synthesis, effects) | Audio interrupt, real-time |
| `ev_render_out` | 41.666 kHz | Post-process audio output | Audio interrupt, real-time |
| `ev_draw` | ~50 Hz | Redraw display (LCD updates) | UI interrupt |
| `ev_key` | On keypress | Handle pad/key input | UI interrupt |
| `ev_enc` | On rotation | Handle encoder rotation | UI interrupt |
| `ev_settings` | User menu | Settings UI (if mod claims settings resource) | UI interrupt |

## Memory Model

**RAM Budget** (128 KB total on Digitakt mk1):
- Core firmware: ~80 KB
- Available for mods: ~48 KB shared
- Fast SRAM: 2304 bytes (for critical audio code)

**Memory Sections**:
- `.run` — Normal RAM (paged in from ROM at boot)
- `.fast` — Fast SRAM (stays resident, copied at startup)
- `.bss` — Zero-initialized RAM (allocated at link time)
- `.boot` — Core mod only (hook bus infrastructure)

**No dynamic allocation** — No malloc/free. All memory pre-allocated via linker.

## Core Mod (Hook Bus)

Every mod set requires `core.elemod`, which provides:
- Hook infrastructure (event dispatch table)
- Shared firmware interface layer
- Symbol definitions for all firmware functions
- Resource registry (settings pages, kit slots, machines)

Mods declare `"requires": ["core"]` in mod.json.

## Firmware Interface

No libc. Call firmware routines by address through function pointers or inline asm.

**Pattern**:
```c
// Firmware function signature (from elekloader headers)
typedef void (*fw_draw_text)(const char *str, u16 x, u16 y);
extern fw_draw_text firmware_draw_text;

// Usage
firmware_draw_text("HELLO", 10, 20);
```

Firmware addresses are OS-version-specific (hash-verified in mod.json).

## Symbol Naming Conventions

All global symbols must be prefixed with mod ID to avoid conflicts:

```c
// Mod ID: "mymod"
static u8 mymod_state;           // Private: static
static void mymod_init(void);    // Private handler
void mymod_on_draw(void);        // Public: event handler
```

**Rules**:
- Prefix all globals with mod ID (auto-done by SDK)
- Make internals static (scope them locally)
- Public names: event handlers, exported functions

## Patch Sites (Alternative to Events)

Some low-level hooks use direct firmware patches instead of events:

```json
"sites": [
  {
    "address": "0x80012345",
    "stock": "4A80",              // Expected stock bytes (minimum 6)
    "op": "jsr",                  // Jump to subroutine
    "target": "mymod_handler",    // Your function
    "kind": "code"
  }
]
```

**When to use patches**:
- Intercept very low-level firmware calls
- Need to hook before event system
- Overriding core behavior

**When to use events**:
- Most cases (cleaner, composable)
- Multiple mods on same event
- Standard integration points

## Dependencies & Conflicts

Declare what your mod needs and what it can't coexist with:

```json
"requires": ["core"],
"conflicts": ["digipoly", "dt8poly"]  // Two poly engines; pick one
```

This is enforced at build time by elekloader.

## Design Constraints

1. **No fixed addresses**: Use symbols, let linker place code
2. **Patch alignment**: Patches must replace whole instructions (6+ bytes)
3. **No byte overlap**: Each byte of firmware patched by at most one mod
4. **Resource isolation**: Settings pages and kit slots don't overlap
5. **Event-driven**: Don't poll or busy-wait; hook into events
6. **Real-time safe**: Audio hooks (ev_tick) must not block or allocate
7. **One stock OS version**: Tied by hash (for safety and reproducibility)

## Mod Composition

Format 2 mods (recommended) can be combined safely:

```bash
python -m elekloader.patch --stock <os.syx> \
  --mod core.elemod \
  --mod digieq.elemod \
  --mod digipoly.elemod \
  --out test.syx
```

- Linker places each mod's code without overlap
- Events from multiple mods all fire (in priority order)
- Resources coordinated (no duplicate settings pages, kit slots)
- Conflicts detected and rejected

## Reference

- **Hook specs**: elekloader `docs/ADAPTING.md` (hook signatures, frequencies)
- **Format details**: elekloader `docs/FORMAT.md` (patch operations, relocation types)
- **Examples**: 
  - Simple: `elekloader/examples/hello-marker/`
  - Multi-hook: `digi1_mods/mods/digieq/` (settings + audio)
  - Complex: `digi1_mods/mods/digipoly/` (resource allocation, conflicts)

