---
name: digitakt-setup
description: Set up a new Digitakt mod project with proper structure
slug: digitakt-setup
---

# Digitakt Mod Setup

Initialize a new Digitakt mod with the correct directory structure, metadata, and toolchain checks.

## Steps

1. **Create mod directory structure**
   - `src/` — C source code files
   - `include/` — Header files (optional, for shared code)
   - `asm/` — m68k assembly stubs (if needed)
   - `.build/` — Intermediate build artifacts (ignored)

2. **Create mod.json metadata file** with:
   - `id`: unique mod identifier (alphanumeric, lowercase, no spaces)
   - `version`: semantic version (e.g., "1.0.0")
   - `device`: "digitakt" (mk1 or mk2)
   - `target_os`: stock OS version by hash (from elekloader)
   - `title`, `category`, `author`, `description`
   - `sources`: array of `.c` and `.s` files to compile
   - `subscribe`: event handlers (ev_draw, ev_tick, ev_key, ev_enc, ev_settings, ev_render_in, ev_render_out)
   - `sites`: firmware patches (address, stock bytes, operation)
   - `requires`: dependencies (usually `["core"]`)
   - `conflicts`: incompatible mods
   - `resources`: claimed allocations (settings pages, kit slots, sound slots)

3. **Create a minimal main source file** (e.g., `src/main.c`):
   - Include firmware headers (m68k structures from elekloader examples)
   - Subscribe to at least one hook event
   - Implement the hook handler function
   - Use mod ID prefix for all global symbols

4. **Verify toolchain**
   - m68k cross-compiler: `m68k-linux-gnu-gcc`, `m68k-linux-gnu-as`, `m68k-linux-gnu-ld`
   - elekloader Python SDK: `python -m elekloader.sdk.build --help`
   - Stock OS file by official hash

5. **Add build script** (optional but recommended):
   - Script that calls `python -m elekloader.sdk.build <moddir> --stock <os.syx>`
   - Validates output `.elemod` file
   - Runs linting: `python -m elekloader.lint <mod.elemod> --stock <os.syx> --with core.elemod`

## Reference

- **Template**: `elekloader/examples/hello-marker/` in the Elektron repo
- **Mod.json spec**: Full format in elekloader `docs/FORMAT.md`
- **Stock OS hash**: Digitakt mk1 = `Digitakt_OS1.53.syx`

