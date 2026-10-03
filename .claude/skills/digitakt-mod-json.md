---
name: digitakt-mod-json
description: Configure mod.json metadata for Digitakt mods
slug: digitakt-mod-json
---

# Digitakt mod.json Configuration

The `mod.json` file declares a mod's metadata, firmware patches, event subscriptions, and resources.

## Required Fields

```json
{
  "id": "mymod",
  "version": "1.0.0",
  "device": "digitakt",
  "target_os": "Digitakt_OS1.53.syx",
  "title": "My Custom Mod",
  "category": "Effect",
  "author": "Your Name",
  "description": "What this mod does",
  "sources": ["src/main.c"],
  "subscribe": [
    {
      "event": "ev_draw",
      "handler": "mymod_on_draw",
      "priority": 0
    }
  ]
}
```

## Field Reference

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Unique identifier (lowercase, alphanumeric, no spaces); used for symbol prefixes |
| `version` | string | Semantic version (e.g., "1.2.3") |
| `device` | string | "digitakt" (or "digitone", "analog4", etc.) |
| `target_os` | string | Stock OS filename; mod is tied to one version (enforced by hash) |
| `title` | string | Human-readable name (shown in loader UI) |
| `category` | string | "Effect", "Tool", "Synth", "Sampler", "Utility" |
| `author` | string | Your name or team |
| `description` | string | 1-2 sentence summary of what it does |

## sources (Array)

List of `.c` and `.s` files to compile. Path relative to mod directory.

```json
"sources": [
  "src/main.c",
  "src/ui.c",
  "asm/startup.s"
]
```

## subscribe (Array)

Event handlers the mod hooks into. Each entry:

```json
{
  "event": "ev_draw",        // "ev_tick", "ev_key", "ev_enc", "ev_settings", "ev_render_in", "ev_render_out"
  "handler": "mymod_on_draw", // Function name in source (no mod prefix needed; SDK adds it)
  "priority": 0               // Execution order (lower runs first; default 0)
}
```

**Available events:**
- `ev_tick` — Audio processing (41.666 kHz, audio interrupt)
- `ev_draw` — Display redraw (~50 Hz, UI interrupt)
- `ev_key` — Key press/release (from pad matrix)
- `ev_enc` — Encoder rotation
- `ev_settings` — Settings menu UI (if mod claims settings resource)
- `ev_render_in` / `ev_render_out` — Audio I/O processing

## sites (Array) [Optional]

Firmware patches. Each patch applies at a specific address.

```json
"sites": [
  {
    "address": "0x80045678",
    "stock": "4E75",           // Expected stock bytes (hex, 6+ bytes minimum)
    "op": "replace",           // "replace", "before", "after", "jsr", "jmp"
    "target": "mymod_handler", // Function to call
    "kind": "code"             // "code", "ptr", "keep2"
  }
]
```

Most mods use **events** instead of sites (cleaner, combinable). Sites are for low-level hooks.

## requires / conflicts (Arrays) [Optional]

```json
"requires": ["core"],           // This mod needs core-2.0a.elemod
"conflicts": ["othermod"]       // Can't run together with othermod
```

Every mod should `requires: ["core"]` (the hook bus and event infrastructure).

## resources (Object) [Optional]

Claim allocations: settings pages, kit slots, sound slots, etc.

```json
"resources": {
  "settings": ["mymod_settings"],  // Settings page names
  "sound": {
    "slots": [52, 53],             // Kit storage slots (0-63 per track)
    "machines": {
      "mymod": 10                  // Synth/drum machine ID (if applicable)
    }
  }
}
```

## Example: Complete mod.json

```json
{
  "id": "digieq",
  "version": "2.0.1",
  "device": "digitakt",
  "target_os": "Digitakt_OS1.53.syx",
  "title": "Digitakt EQ",
  "category": "Effect",
  "author": "Elektron",
  "description": "3-band EQ per track with realtime parameter edit",
  "sources": [
    "src/main.c",
    "src/eq.c",
    "src/ui.c"
  ],
  "subscribe": [
    {"event": "ev_tick", "handler": "digieq_on_tick"},
    {"event": "ev_draw", "handler": "digieq_on_draw"},
    {"event": "ev_enc", "handler": "digieq_on_enc"},
    {"event": "ev_settings", "handler": "digieq_on_settings"}
  ],
  "requires": ["core"],
  "resources": {
    "settings": ["digieq"]
  }
}
```

## Reference

- **Full spec**: elekloader `docs/FORMAT.md`
- **Examples**: `digi1_mods/mods/*/mod.json`
- **Validation**: `python -m elekloader.lint <mod.elemod> --json`

