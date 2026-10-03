---
name: digitakt-resources
description: Manage Digitakt mod resources (settings, kit slots, synth machines)
slug: digitakt-resources
---

# Digitakt Mod Resources

Allocate and manage shared firmware resources: settings UI pages, kit storage slots, and synthesizer machines.

## Resource Types

### 1. Settings Pages

Mods can register custom settings pages shown in the Digitakt settings menu.

```json
"resources": {
  "settings": ["mymod_settings"]
}
```

**Declaration in source** (example):
```c
const struct settings_page mymod_settings = {
  .name = "MYMOD",
  .num_params = 4,
  .params = { ... }
};
```

**Hook handler**:
- Subscribe to `ev_settings` event
- Called when user enters settings menu for your mod
- Handle encoder/key input for parameter adjustment
- Call firmware UI functions to redraw parameter display

**Constraints**:
- One settings page per mod
- Page name max 8 characters
- Up to 16 parameters per page

### 2. Kit Storage Slots

Each of the 16 patterns in a kit can store mod-specific state in "sound slots" (unused Kit storage).

**Digitakt storage layout** (per pattern, per sound):
- Slots 0-51: Official Elektron use (drum machine, sample slot, etc.)
- **Slots 52-63: Available for mods** (12 slots × 8 bytes each = 96 bytes per sound)

```json
"resources": {
  "sound": {
    "slots": [52, 53]  // This mod uses slots 52-53 (16 bytes total)
  }
}
```

**Usage pattern**:
```c
struct mymod_kit {
  u8 param1;
  u8 param2;
  u16 value16;
} __attribute__((packed));  // Must be exact byte size

// Read from kit
struct mymod_kit state;
firmware_read_kit_slot(52, &state, sizeof(state));

// Write to kit
firmware_write_kit_slot(52, &state, sizeof(state));
```

**Constraints**:
- Only 12 slots available (52-63) shared across all mods
- No overlap allowed (declared in mod.json)
- Data persists with pattern/kit
- 8 bytes per slot

### 3. Synthesizer Machines

Mods can register custom synthesizer or drum machine types.

```json
"resources": {
  "sound": {
    "machines": {
      "mysynth": 10
    }
  }
}
```

(Less common; requires synthesizer/drum implementation.)

## Resource Conflict Resolution

**Build-time validation**:
- `elekloader.lint` checks all mod resource claims
- Fails if slots overlap or settings pages duplicate
- Enforced before combining mods

**Declaration order**:
- List all claimed resources in `mod.json`
- SDK prevents combining conflicting mods

## Reference

- **Kit slot usage**: digi1_mods examples (digimatrix, digipoly)
- **Settings UI patterns**: Tone-FX digieq settings handler
- **Firmware address reference**: Stock OS binary dump (elekloader tools)

