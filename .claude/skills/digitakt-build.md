---
name: digitakt-build
description: Build and compile a Digitakt mod using the elekloader SDK
slug: digitakt-build
---

# Digitakt Mod Build

Compile a Digitakt mod from source into an `.elemod` linkable binary.

## Build Pipeline

1. **Compile C and assembly sources**
   - m68k cross-compiler invoked by elekloader SDK
   - No need to invoke m68k tools directly (SDK handles it)
   - Symbols automatically prefixed with mod ID

2. **Run elekloader SDK build**
   ```bash
   python -m elekloader.sdk.build <mod-directory> --stock <Digitakt_OS1.53.syx> [--output <name.elemod>]
   ```
   - Input: mod directory with `mod.json` and source files
   - Output: `<modid>-<version>.elemod` (default) or specified name
   - Validates: stock bytes match, no compilation errors

3. **Lint the output** (recommended)
   ```bash
   python -m elekloader.lint <mod.elemod> --stock <Digitakt_OS1.53.syx> --with core.elemod --json
   ```
   - Checks: no resource conflicts, patch sites valid, dependencies met
   - Output: JSON report of warnings/errors

4. **Test build locally** (optional)
   ```bash
   python -m elekloader.patch --stock <stock.syx> --mod core.elemod --mod <your-mod.elemod> --out test.syx
   ```
   - Combines stock OS + core + your mod
   - Output: test.syx ready to flash or test in emulator

## Key Rules

- **Stock OS hash must match**: Mod is tied to one stock OS version (enforced in mod.json)
- **Patch site validation**: SDK verifies stock bytes before patching
- **No hard-coded addresses**: Let the linker place all code (use relocatable references)
- **Symbol prefixes**: Automatic (e.g., `mymod_` prefix for mod ID `mymod`)
- **Event subscriptions**: Declare in `mod.json` → SDK generates hook registrations

## Troubleshooting Build Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "stock bytes don't match" | Stock OS version mismatch | Use correct Digitakt_OS1.53.syx |
| "symbol already defined" | Duplicate global in mod.json sources | Check sources list, remove duplicates |
| "patch site overlap" | Patch claims already-used firmware address | Check mod.json sites, adjust addresses |
| "relocation type not allowed" | Used absolute address instead of symbol | Use relocatable references only |

## Reference

- **SDK commands**: `python -m elekloader.sdk.build --help`
- **Error reference**: elekloader `docs/ADAPTING.md` (refusal mappings, fix recipes)
- **Format spec**: elekloader `docs/FORMAT.md`

